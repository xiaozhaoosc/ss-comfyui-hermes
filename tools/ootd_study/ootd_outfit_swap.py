#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OOTD 换装 -> 视频链路（同一人物基准图 + 服装参考图 真实换装）

修复旧链路"4 张 Flux 独立文生图 + 逐图独立 I2V"导致的人物/服装不一致、
无服装参考、成片闪烁严重的问题：改为**同一人物基准图**逐套服装走
Qwen-Image-2.1 双图参考编辑（真实换装，人物脸/发型/姿势/背景完整保留）
-> 换装图逐张 H3 I2V -> 硬切合并成片，并对成片做"帧间灰度差 x4 下采样"
量化，验证闪烁（纹理沸腾）是否下降。

阶段（--stage）：
  swap   逐服装：base/garment 拷入 input -> 注入 qwen_outfit_swap_api.json
         -> 校验 -> 提交 -> 等待 -> PNG 验收（非黑 + 尺寸=base）-> 归档 swap/g<i>a_*.png
         每套可选 2 段（--shots-per-outfit 2）：第 2 段以第 1 段换装图为新人物输入，
         同一条换装工作流生成"走近/半身"变体 -> 归档 swap/g<i>b_*.png
  video  逐换装图（g1a,g1b,g2a,g2b,... 顺序）-> H3 I2V（736x1088，length=align(seg-len)）
         -> 预检 -> 提交/等待 -> 验收 -> 段落地 s<i>_*.mp4 -> 转场合并 -> 视配置压 BGM
         -> <project>_merged.mp4
  all    swap + video（默认）

卡点节奏：每套连续 2 段（3.0417s/段），转场默认 fadeblack 0.3s；
--bgm-auto 时按"每段所含拍数最接近整数"自动选曲并对齐相位。

归档：
  换装图 output/<date>/<project>/swap/<key>a_*.png
         （key：JSON 对象项=id；字符串项=g<idx>；旧命名 g<i>_*.png 兼容复用）
  第2段   output/<date>/<project>/swap/<key>b_*.png
  进度   output/<date>/<project>/swap_progress.json
  分段   output/<date>/<project>/s<i>_*.mp4
  成片   output/<date>/<project>/<project>_merged.mp4（含 BGM 时为其混音版，
         中间无 BGM 版为 <project>_merged_raw.mp4）
  报告   output/<date>/<project>/outfit_swap_report.json

仅新建本文件；复用 tools/h3_fast_submit.py、tools/h3_fast_segmented.py、
tools/ootd_study/ootd_pipeline.py 的既有函数（未修改它们）；
转场合并与 BGM 混音均在本工具内实现（未改共享文件）。

用法:
  python tools/ootd_study/ootd_outfit_swap.py --dry-run
  python tools/ootd_study/ootd_outfit_swap.py --stage swap
  python tools/ootd_study/ootd_outfit_swap.py --stage video
  python tools/ootd_study/ootd_outfit_swap.py --stage video --merge-only
  python tools/ootd_study/ootd_outfit_swap.py --stage all --project outfit_swap_beat `
      --shots-per-outfit 2 --transition fadeblack --xfade 0.3 --bgm-auto
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import date as _date

# --- sys.path: 同时含 tools/ 与 tools/ootd_study/ ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.dirname(_THIS_DIR)
for _p in (_TOOLS_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import h3_fast_submit as base          # noqa: E402
import h3_fast_segmented as seg        # noqa: E402
import ootd_pipeline as pipe           # noqa: E402  (复用 ROOT/run_prechecks/_ascii_slug 等)

ROOT = pipe.ROOT
INPUT_ROOT = pipe.INPUT_ROOT
OUTPUT_ROOT = pipe.OUTPUT_ROOT

SWAP_WORKFLOW = os.path.join(_THIS_DIR, "workflows", "v5", "qwen_outfit_swap_api.json")
I2V_WORKFLOW = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")

DEFAULT_BASE = os.path.join("output", "2026-10-02", "ootd_blue_shirt", "img",
                            "03_full_standing_00001_.png")
DEFAULT_GARMENTS = [
    "vton_garment_beige_dress.png",
    "vton_garment_navy_dress.png",
    "vton_garment_red_slip.png",
    "vton_garment_sailor.png",
]

# 已验证的换装指令（人物/姿势/背景不变 + 服装忠实还原）
DEFAULT_GARMENT_PROMPT = (
    "The woman in the first image is now wearing the [garment description] "
    "from the second image. Faithfully reproduce the garment from image 2 "
    "(design/color/material/hem). Keep her face, hairstyle, skin tone, body "
    "proportions, pose and the background completely unchanged."
)
# 默认运动提示词（全身、平稳，避免特写纹理沸腾）
DEFAULT_MOTION = (
    "she gently shifts her weight and turns slightly to show the outfit, "
    "calm natural movement, fabric sways softly, steady full-body camera, "
    "soft indoor lighting"
)
# 第 2 段（走近/半身）默认提示词：同人同衣同背景，仅景别拉近
DEFAULT_SECOND_SHOT_PROMPT = (
    "The same woman in the same hallway wearing the same outfit as image 1, "
    "but she has taken one step closer to the mirror: medium shot framed from "
    "the waist up, showing the garment detail clearly. Keep her face, hairstyle, "
    "the outfit design, and the background completely unchanged."
)

GARMENT_TOKEN = "[garment description]"
MIN_BRIGHTNESS = 3.0
FPS = 24.0
SEG_SECONDS = 73.0 / 24.0                     # 3.0417

# BGM 原创素材目录（可商用）
BGM_DIR = os.path.join(INPUT_ROOT, "ken4", "face", "bgm原创")

# --transition -> ffmpeg xfade transition 名（cut 走 concat 硬切，无 xfade）
XFADE_MAP = {
    "crossfade": "fade",
    "fade": "fade",
    "fadeblack": "fadeblack",
    "fadewhite": "fadewhite",
    "wipeleft": "wipeleft",
    "slideright": "slideright",
}
TRANSITION_CHOICES = ["cut", "crossfade", "fadeblack", "fadewhite",
                      "fade", "wipeleft", "slideright"]

# 旧链路客观基线（帧间灰度差 x4 下采样）
BASELINE = {
    "segment_means": [4.00, 4.57, 4.22, 8.17],
    "boundaries": [43.21, 45.24, 47.57],
    "note": "旧链路：4 张 Flux 各自独立文生图 + 逐图独立 I2V；段内均值 4.00/4.57/4.22/8.17，"
            "段间硬切处 43.21/45.24/47.57",
}


# =============================== 小工具 ===============================

def latest_glob(pattern):
    cands = [p for p in glob.glob(pattern) if os.path.exists(p)]
    return max(cands, key=os.path.getmtime) if cands else None


def resolve_path(p):
    """绝对路径原样返回；相对路径优先相对 cwd，其次相对 ROOT。"""
    if os.path.isabs(p):
        return os.path.normpath(p)
    if os.path.exists(p):
        return os.path.abspath(p)
    return os.path.normpath(os.path.join(ROOT, p))


def resolve_input(name):
    """input 下的文件名 -> 绝对路径。"""
    if os.path.isabs(name):
        return os.path.normpath(name)
    ip = os.path.join(INPUT_ROOT, name)
    if os.path.exists(ip):
        return os.path.abspath(ip)
    if os.path.exists(name):
        return os.path.abspath(name)
    return None


def garment_desc(path):
    """由文件名推导服装描述（vton_garment_beige_dress -> beige dress）。"""
    b = os.path.splitext(os.path.basename(path))[0]
    for pre in ("vton_garment_", "vton_", "garment_"):
        if b.startswith(pre):
            b = b[len(pre):]
            break
    b = b.replace("_", " ").strip()
    return b or "garment"


def image_size(png):
    import av
    with av.open(png) as c:
        s = c.streams.video[0]
        return int(s.width), int(s.height)


# FluxKontextImageScale 的优选分辨率桶（与 comfy_extras/nodes_flux.py 一致）
KONTEXT_BUCKETS = [
    (672, 1568), (688, 1504), (720, 1456), (752, 1392), (800, 1328),
    (832, 1248), (880, 1184), (944, 1104), (1024, 1024), (1104, 944),
    (1184, 880), (1248, 832), (1328, 800), (1392, 752), (1456, 720),
    (1504, 688), (1568, 672),
]


def expected_swap_size(w, h):
    """换装模板输出尺寸 = FluxKontextImageScale(基准图) 的最近宽高比桶。

    模板节点 5 会把人物图规整到 Kontext 优选分辨率，故输出尺寸跟随的是
    "基准图 -> 最近比例桶"，而非基准图原尺寸（二者可能相同也可能差 1 桶）。
    """
    ar = w / float(h)
    return min(KONTEXT_BUCKETS, key=lambda b: abs(ar - b[0] / float(b[1])))


def probe_audio_codec(mp4):
    ff = seg.ffprobe_exe()
    r = subprocess.run([ff, "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=codec_name",
                        "-of", "default=noprint_wrappers=1:nokey=1", mp4],
                       capture_output=True, text=True)
    return r.stdout.strip() or None


def submit(wf):
    r = base._post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    if r.get("node_errors"):
        raise RuntimeError("node_errors: "
                           + json.dumps(r["node_errors"], ensure_ascii=False)[:1200])
    pid = r.get("prompt_id")
    if not pid:
        raise RuntimeError("提交未返回 prompt_id: "
                           + json.dumps(r, ensure_ascii=False)[:400])
    return pid


def copy_to_input(src, name):
    os.makedirs(INPUT_ROOT, exist_ok=True)
    shutil.copy2(src, os.path.join(INPUT_ROOT, name))
    return name


def validate_nodes(wf):
    """逐节点校验；先清 LoadImage 的动态文件枚举缓存，避免复制新图后误判"非法枚举"。"""
    base._INFO_CACHE.pop("LoadImage", None)
    return base.validate_workflow(wf)


# =============================== 帧间差 / 清晰度 ===============================

def _gray4(f):
    import numpy as np
    g = f.astype(np.float32).mean(axis=2)
    return g[::4, ::4]


def _absdiff4(a, b):
    import numpy as np
    return float(np.abs(_gray4(a) - _gray4(b)).mean())


def frame_diff_stats(frames):
    """逐帧灰度 x4 下采样后相邻帧平均绝对差 -> mean/p95/max。"""
    import numpy as np
    if len(frames) < 2:
        return {"n": 0, "mean": None, "p95": None, "max": None}
    diffs = [_absdiff4(frames[i], frames[i - 1]) for i in range(1, len(frames))]
    arr = np.array(diffs)
    return {"n": int(len(diffs)),
            "mean": round(float(arr.mean()), 3),
            "p95": round(float(np.percentile(arr, 95)), 3),
            "max": round(float(arr.max()), 3)}


def boundary_diffs(frames_list):
    """跨段边界差：上段末帧 vs 下段首帧（灰度 x4 下采样）。"""
    out = []
    for i in range(len(frames_list) - 1):
        out.append(round(_absdiff4(frames_list[i][-1], frames_list[i + 1][0]), 3))
    return out


def merged_boundary_diffs(merged_frames, counts):
    """合并片在累计边界帧处的帧间差。"""
    out, idx = [], 0
    for c in counts[:-1]:
        idx += c
        if 0 < idx < len(merged_frames):
            out.append(round(_absdiff4(merged_frames[idx - 1], merged_frames[idx]), 3))
    return out


def sharpness(frames, max_frames=24):
    """Laplacian 方差（越大越锐利）；下采样帧子集求均值。"""
    import numpy as np
    if not frames:
        return None
    step = max(1, len(frames) // max_frames)
    vals = []
    for f in frames[::step]:
        g = f.astype(np.float32).mean(axis=2)
        lap = (-4.0 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1]
               + g[1:-1, :-2] + g[1:-1, 2:])
        vals.append(float(lap.var()))
    return round(sum(vals) / len(vals), 2) if vals else None


def smooth_video(in_mp4, out_mp4, mode="light"):
    """仅时域轻平滑（ffmpeg）。light = tmix 2 帧等权时域平均，音频直通。"""
    ff = base.resolve_ffmpeg()
    if not ff:
        return False, "未找到 ffmpeg"
    vf = {"light": "tmix=frames=2"}.get(mode)
    if not vf:
        return False, f"未知平滑模式 {mode}"
    cmd = [ff, "-y", "-i", in_mp4, "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out_mp4)
    return ok, (r.stderr or "")[-500:]


# =============================== 转场合并（本工具内实现） ===============================

def merge_with_transition(seg_files, out_path, transition="fadeblack", xfade=0.3):
    """转场合并：视频 xfade 链（或 cut=concat）+ 音频 acrossfade 链（或 concat）。

    transition 取值：cut / crossfade / fade / fadeblack / fadewhite / wipeleft / slideright。
    思路与 h3_fast_segmented.merge_segments 一致（未修改该文件）：
      xfade 逐段累积 offset，总时长 = Σdur − (N−1)×xfade；音频与视频同步淡接。
    返回 (ok, err)。
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    ff = base.resolve_ffmpeg()
    if not ff:
        return False, "未找到 ffmpeg"
    n = len(seg_files)
    if n == 0:
        return False, "没有可拼接的分段"
    fps = seg.probe_fps(seg_files[0])
    durs = [seg.probe_duration(p) for p in seg_files]
    all_have_audio = all(seg.has_audio(p) for p in seg_files)

    vparts, aparts = [], []
    hard_cut = (transition == "cut") or n == 1
    if hard_cut:
        vin = "".join("[%d:v]" % i for i in range(n))
        vparts.append(vin + "concat=n=%d:v=1:a=0[vc]" % n)
        vlast = "vc"
    else:
        tname = XFADE_MAP.get(transition, "fade")
        prev, acc = "0:v", durs[0]
        for i in range(1, n):
            off = max(0.0, acc - xfade)
            out = "vx%d" % i
            vparts.append("[%s][%d:v]xfade=transition=%s:duration=%s:offset=%.3f[%s]"
                          % (prev, i, tname, xfade, off, out))
            prev, acc = out, acc + durs[i] - xfade
        vlast = prev

    alast = None
    if all_have_audio:
        if hard_cut:
            ain = "".join("[%d:a]" % i for i in range(n))
            aparts.append(ain + "concat=n=%d:v=0:a=1[ac]" % n)
            alast = "ac"
        else:
            prev = "0:a"
            for i in range(1, n):
                out = "ax%d" % i
                aparts.append("[%s][%d:a]acrossfade=d=%s:c1=tri:c2=tri[%s]"
                              % (prev, i, xfade, out))
                prev = out
            alast = prev

    fc = ";".join(vparts)
    fc += ";[" + vlast + "]format=yuv420p[vout]"
    if aparts:
        fc += ";" + ";".join(aparts)
    maps = ["-map", "[vout]"] + (["-map", "[%s]" % alast] if alast else [])
    cmd = [ff, "-y"]
    for p in seg_files:
        cmd += ["-i", p]
    cmd += ["-filter_complex", fc] + maps + [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "%g" % fps]
    if alast:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out_path)
    return ok, (r.stderr or "")[-800:]


# =============================== BGM：节拍估计 / 选曲 / 混音 ===============================

def load_audio_mono(path):
    """解码音频为单声道 float32 + 采样率；失败返回 (None, None)。"""
    import av
    import numpy as np
    try:
        with av.open(path) as c:
            if not c.streams.audio:
                return None, None
            st = c.streams.audio[0]
            sr = int(st.rate)
            chunks = []
            for fr in c.decode(st):
                a = fr.to_ndarray()
                if a.ndim == 1:
                    a = a[None, :]
                chunks.append(a)
            if not chunks:
                return None, sr
            data = np.concatenate(chunks, axis=1).astype(np.float32)
            return data.mean(axis=0), sr
    except Exception:
        return None, None


def _phase_seconds(onset, lag, fps):
    """在 0..lag-1 内取使拍点覆盖能量最大者，返回相位（秒，∈[0,period)）。"""
    import numpy as np
    best_p, best_v = 0, -1.0
    for p in range(int(lag)):
        idx = np.arange(p, len(onset), lag)
        if idx.size == 0:
            continue
        v = float(onset[idx].sum())
        if v > best_v:
            best_v, best_p = v, p
    return float(best_p) / fps


def estimate_tempo(sig, sr, hop=512, bpm_lo=60.0, bpm_hi=200.0):
    """简单节拍估计：能量起始包络（半波整流差分）自相关求主周期 -> BPM。

    返回 dict(bpm, fps, lag, strength, phase) 或 None。best-effort，不强保证准确。
    """
    import numpy as np
    n = len(sig)
    nf = n // hop
    if nf < 64:
        return None
    s = sig[:nf * hop].reshape(nf, hop).astype(np.float64)
    env = np.sqrt((s ** 2).mean(axis=1))
    onset = np.diff(env)
    onset[onset < 0] = 0.0
    if onset.size == 0 or onset.max() <= 0:
        return None
    x = onset - onset.mean()
    ac = np.correlate(x, x, mode="full")[len(x) - 1:]
    fps = sr / float(hop)
    lag_min = max(1, int(round(fps * 60.0 / bpm_hi)))
    lag_max = min(len(ac) - 1, int(round(fps * 60.0 / bpm_lo)))
    if lag_max <= lag_min:
        return None
    seg_ac = ac[lag_min:lag_max + 1]
    lag = lag_min + int(np.argmax(seg_ac))
    strength = float(ac[lag] / (ac[0] + 1e-9))
    bpm = 60.0 * fps / lag
    # 折叠到 [70,180]，便于与"每段拍数"整数对齐
    while bpm < 70.0:
        bpm *= 2.0
    while bpm > 180.0:
        bpm /= 2.0
    phase = _phase_seconds(onset, lag, fps) % (60.0 / bpm)
    return {"bpm": bpm, "fps": fps, "lag": lag,
            "strength": strength, "phase": phase}


def analyze_track(path):
    """对单首 BGM 估计 BPM / 每段拍数 / 相位；返回 dict。

    节拍存在倍频歧义，这里在 [60,220] 内取 0.5x/1x/2x 三个倍频变体中
    "每段拍数最接近整数"者作为该曲代表 BPM。
    """
    sig, sr = load_audio_mono(path)
    if sig is None:
        return {"path": path, "bpm": None, "beats_per_shot": None,
                "distance": None, "phase": None, "reliable": False,
                "error": "decode failed"}
    est = estimate_tempo(sig, sr)
    if est is None:
        return {"path": path, "bpm": None, "beats_per_shot": None,
                "distance": None, "phase": None, "reliable": False,
                "error": "tempo estimate failed"}
    best = None
    for mult in (0.5, 1.0, 2.0):
        v = est["bpm"] * mult
        if not (60.0 <= v <= 220.0):
            continue
        beats = SEG_SECONDS * v / 60.0
        d = abs(beats - round(beats))
        if best is None or d < best[0]:
            best = (d, v, beats)
    if best is None:
        v = est["bpm"]
        beats = SEG_SECONDS * v / 60.0
        best = (abs(beats - round(beats)), v, beats)
    distance, bpm, beats = best
    # 相位按代表 BPM 的周期折算（倍频时周期减半）
    period = 60.0 / bpm
    phase = est["phase"] % period
    reliable = bool(est["strength"] >= 0.15 and 60.0 <= bpm <= 220.0)
    return {"path": path, "bpm": round(bpm, 2), "beats_per_shot": round(beats, 3),
            "distance": round(distance, 4), "phase": round(phase, 4),
            "strength": round(est["strength"], 4), "reliable": reliable}


def discover_bgm(bgm_dir):
    """枚举 BGM 目录下 *.mp3，按去重键（去掉 ' (1)' 后缀）保留首现，稳定排序。"""
    cands = sorted(glob.glob(os.path.join(bgm_dir, "*.mp3")))
    seen, out = set(), []
    for p in cands:
        base_name = os.path.splitext(os.path.basename(p))[0]
        key = re.sub(r"\s*\(\d+\)\s*$", "", base_name).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def auto_select_bgm(bgm_dir, n_switch, xfade, align=True):
    """自动选曲：每段所含拍数最接近整数者胜出；并估相位对齐（best-effort）。

    若"最贴合的曲目"节拍估计不可靠，则在距离最佳值 +0.05 容差内的可靠曲目中
    取最贴合者（以便相位对齐可落地）；否则保持最小距离者。
    """
    tracks = discover_bgm(bgm_dir)
    analyzed = [analyze_track(p) for p in tracks]
    valid = [r for r in analyzed if r.get("distance") is not None]
    if not valid:
        return None, analyzed, 0.0, "无可估计节拍的曲目"
    valid.sort(key=lambda r: r["distance"])
    best_d = valid[0]["distance"]
    near = [r for r in valid if r["distance"] <= best_d + 0.05]
    reliable_near = [r for r in near if r.get("reliable")]
    chosen = min(reliable_near or near, key=lambda r: r["distance"])
    tie_note = ""
    if reliable_near and chosen is not valid[0]:
        tie_note = (f"；最佳距离曲目 {os.path.basename(valid[0]['path'])} 不可靠"
                    f"（strength={valid[0].get('strength')}），容差内改选可靠曲目")

    phase_align = 0.0
    reason = ""
    if align and chosen.get("reliable") and chosen.get("bpm"):
        period = 60.0 / chosen["bpm"]
        # 切换点取转场中点：t_k = k*(seg - xfade) + xfade/2
        switch = [(k * (SEG_SECONDS - xfade)) + xfade / 2.0
                  for k in range(1, n_switch + 1)]
        if switch:
            s0 = switch[0]
            phase_align = (chosen["phase"] - (s0 % period)) % period
            reason = ("拍点相位 %.3fs 对齐切换点 %.3fs（周期 %.3fs，1–%d 处）"
                      % (chosen["phase"], s0, period, n_switch) + tie_note)
    else:
        reason = ("节拍估计不可靠或未启用对齐 -> 相位对齐为 0" + tie_note) \
            if align else ("未启用相位对齐" + tie_note)
    return chosen, analyzed, round(phase_align, 3), reason


def mix_bgm(base_mp4, bgm_path, out_mp4, bgm_volume=1.0, ambient_volume=0.2,
            start_offset=0.0):
    """把 BGM（循环/裁剪）与成片原生环境音混音，输出含 BGM 的最终成片。

    环境音 volume=ambient_volume（压低 H3 原生声），BGM volume=bgm_volume；
    BGM 以 atrim=start=start_offset 做相位对齐，-stream_loop -1 循环补足时长。
    """
    ff = base.resolve_ffmpeg()
    if not ff:
        return False, "未找到 ffmpeg"
    has_amb = seg.has_audio(base_mp4)
    parts, maps = [], ["-map", "0:v"]
    if has_amb:
        parts.append("[0:a]volume=%.4f[amb]" % ambient_volume)
    parts.append("[1:a]volume=%.4f,atrim=start=%.4f,asetpts=PTS-STARTPTS[bg]"
                 % (bgm_volume, max(0.0, start_offset)))
    if has_amb:
        parts.append("[amb][bg]amix=inputs=2:duration=first:dropout_transition=0:"
                     "normalize=0[aout]")
    else:
        parts[-1] = parts[-1].replace("[bg]", "[aout]")
    maps += ["-map", "[aout]"]
    base_dur = seg.probe_duration(base_mp4)
    cmd = [ff, "-y", "-i", base_mp4, "-stream_loop", "-1", "-i", bgm_path,
           "-filter_complex", ";".join(parts)] + maps + [
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", "%.3f" % base_dur, "-movflags", "+faststart", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out_mp4)
    return ok, (r.stderr or "")[-800:]


def probe_volume_stats(mp4):
    """用 ffmpeg volumedetect 取 mean/max 音量（用于核对确含音频）。"""
    ff = base.resolve_ffmpeg()
    if not ff:
        return None
    r = subprocess.run([ff, "-hide_banner", "-i", mp4, "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    out = (r.stderr or "")
    stats = {}
    for key in ("mean_volume", "max_volume"):
        m = re.search(key + r":\s*(-?[\d.]+)\s*dB", out)
        if m:
            stats[key] = float(m.group(1))
    return stats or None


# =============================== swap_progress ===============================

def swap_progress_path(date, project):
    return os.path.join(OUTPUT_ROOT, date, project, "swap_progress.json")


def load_progress(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            d.setdefault("completed", [])
            d.setdefault("results", {})
            return d
        except Exception:
            pass
    return {"completed": [], "results": {}, "updated": None}


def save_progress(path, prog):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prog["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


# =============================== 服装清单 ===============================

def read_garments_file(path):
    """读取服装清单文件 -> [(raw, prompt_override, explicit_id), ...]。

    兼容两种格式：
      - 纯文本：每行一个路径（"#" 开头忽略）—— 与旧行为一致；
      - JSON 数组：元素可为字符串（同纯文本）或对象
        {"id": "c1", "garment": "服装/demo_clean.jpg", "prompt": "..."}。
        id 用于归档/段命名（swap/<id>a_*.png、段顺序）；prompt 覆盖 a 段换装提示词。
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    if text.lstrip().startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"服装清单 JSON 解析失败: {e}")
        if not isinstance(data, list):
            raise ValueError("服装清单 JSON 根节点必须是数组")
        out = []
        for it in data:
            if isinstance(it, str):
                out.append((it.strip(), None, None))
            elif isinstance(it, dict):
                g = it.get("garment") or it.get("path")
                if not g:
                    raise ValueError(f"服装对象缺少 garment/path 字段: {it}")
                out.append((str(g), it.get("prompt"), it.get("id")))
            else:
                raise ValueError(f"不支持的服装项类型: {type(it).__name__}")
        return out
    out = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            out.append((ln, None, None))
    return out


def resolve_garments(args):
    """解析服装清单 -> [{index, id, key, path, desc, prompt}, ...]。

    - --garments（逗号分隔）或 --garments-file 纯文本行：向后兼容，
      key=g<idx>，prompt 用默认模板（prompt=None 表示走模板）。
    - --garments-file JSON 数组：对象项的 id 决定 key（归档/段命名），
      prompt 覆盖默认 --garment-prompt-template（a 段）。
    """
    if args.garments:
        items = [(x.strip(), None, None)
                 for x in args.garments.split(",") if x.strip()]
    elif args.garments_file:
        items = read_garments_file(args.garments_file)
    else:
        items = [(x, None, None) for x in DEFAULT_GARMENTS]
    resolved = []
    for idx, (raw, prompt, gid) in enumerate(items, 1):
        p = resolve_input(raw) or resolve_path(raw)
        if not os.path.exists(p):
            print(f"[警告] 服装参考图不存在: {raw} -> {p}")
        resolved.append({"index": idx, "id": gid, "key": gid or f"g{idx}",
                         "path": p, "desc": garment_desc(p), "prompt": prompt})
    return resolved


# =============================== dry-run ===============================

def run_dry_run(args, date, project, slug, base_img, garments):
    print("\n=== dry-run：两阶段注入 + 逐节点校验 + 预检（不提交）===")
    print(f"[参数] shots_per_outfit={args.shots_per_outfit} transition={args.transition} "
          f"xfade={args.xfade} bgm_auto={args.bgm_auto}")
    ok_all = True
    shots = args.shots_per_outfit

    # ---- swap 阶段 ----
    if not os.path.exists(SWAP_WORKFLOW):
        print(f"[失败] 换装工作流不存在: {SWAP_WORKFLOW}")
        return 1
    with open(SWAP_WORKFLOW, "r", encoding="utf-8") as f:
        swap_tpl = json.load(f)
    base_in = f"swap_{slug}_base.png"
    if os.path.exists(base_img):
        copy_to_input(base_img, base_in)
    print(f"\n[swap] 模板={os.path.basename(SWAP_WORKFLOW)}  base={base_in}  "
          f"每套 {shots} 段")
    for idx, it in enumerate(garments, 1):
        if args.limit and idx > args.limit:
            break
        g = it["path"]
        kp = it["key"]
        garment_in = f"swap_{slug}_{kp}.png"
        if os.path.exists(g):
            copy_to_input(g, garment_in)
        desc = it["desc"]
        for shot in ["a", "b"][:shots]:
            key = f"{kp}{shot}"
            if shot == "a":
                person_in = base_in
                prompt = (it["prompt"] if it["prompt"]
                          else args.garment_prompt_template.replace(GARMENT_TOKEN, desc))
                seed = args.seed + idx
                extra = f"desc={desc!r} prompt_src={'custom' if it['prompt'] else 'template'}"
            else:
                # 以第 1 段换装图为新人物输入（存在则用，否则退回 base 仅做节点校验）
                a_png = latest_glob(os.path.join(OUTPUT_ROOT, date, project,
                                                 "swap", f"{kp}a_*.png"))
                if a_png is None:
                    a_png = latest_glob(os.path.join(OUTPUT_ROOT, date, project,
                                                     "swap", f"{kp}_*.png"))
                person_in = copy_to_input(a_png, f"swap_{slug}_{kp}a.png") \
                    if a_png else base_in
                prompt = args.second_shot_prompt
                seed = args.seed + 1000 + idx
                extra = f"second_shot person={os.path.basename(person_in)}"
            wf = base.inject_placeholders(swap_tpl, {
                "image": person_in, "garment": garment_in, "prompt": prompt,
                "seed": seed, "output": f"{date}/{project}/swap/{key}"})
            wf["13"]["inputs"]["steps"] = args.steps
            wf["13"]["inputs"]["cfg"] = args.cfg
            print(f"\n[swap {key}] image={person_in!r} garment={garment_in!r} "
                  f"{extra} seed={seed} steps={args.steps} cfg={args.cfg}")
            errors, lines = validate_nodes(wf)
            for ln in lines:
                print(ln)
            if errors:
                ok_all = False
                print(f"[swap {key}] 校验失败（{len(errors)} 项）:")
                for e in errors:
                    print("  - " + e)
            else:
                print(f"[swap {key}] 校验 OK（{len(wf)} 节点）")

    # ---- video 阶段 ----
    if not os.path.exists(I2V_WORKFLOW):
        print(f"[失败] I2V 工作流不存在: {I2V_WORKFLOW}")
        return 1
    with open(I2V_WORKFLOW, "r", encoding="utf-8") as f:
        i2v_tpl = json.load(f)
    length = base.align_length(args.seg_len)
    n_outfits = len(garments)
    if args.limit:
        n_outfits = min(n_outfits, args.limit)
    n_seg = n_outfits * shots
    print(f"\n[video] 模板={os.path.basename(I2V_WORKFLOW)}  "
          f"{args.width}x{args.height} length={length} 套数={n_outfits} 段数={n_seg}")
    sample = None
    seq = 0
    for idx, it in enumerate(garments[:n_outfits], 1):
        kp = it["key"]
        for shot in ["a", "b"][:shots]:
            seq += 1
            swap_png = latest_glob(os.path.join(OUTPUT_ROOT, date, project,
                                                "swap", f"{kp}{shot}_*.png"))
            if swap_png is None and shot == "a":
                swap_png = latest_glob(os.path.join(OUTPUT_ROOT, date, project,
                                                    "swap", f"{kp}_*.png"))
            ff_name = base_in
            if swap_png:
                ff_name = copy_to_input(swap_png, f"swap_{slug}_first{seq}.png")
            wf = base.inject_placeholders(i2v_tpl, {
                "first_frame": ff_name, "prompt": args.motion_prompt,
                "width": args.width, "height": args.height, "length": length,
                "seed": args.seed + seq, "filename_prefix": f"{date}/{project}/s{seq}"})
            if sample is None:
                sample = wf
            print(f"\n[段{seq} {kp}{shot}] first_frame={ff_name!r} "
                  f"seed={args.seed + seq} prompt[:60]={args.motion_prompt[:60]!r}")
            errors, lines = validate_nodes(wf)
            for ln in lines:
                print(ln)
            if errors:
                ok_all = False
                print(f"[段{seq}] 校验失败（{len(errors)} 项）:")
                for e in errors:
                    print("  - " + e)
            else:
                print(f"[段{seq}] 校验 OK（{len(wf)} 节点）")

    if sample is not None and not pipe.run_prechecks(sample):
        ok_all = False

    if ok_all:
        print("\n[通过] dry-run：两阶段注入 + 逐节点校验 + 预检 全部通过（未提交）")
        return 0
    print("\n[失败] dry-run 存在问题（未提交）")
    return 1


# =============================== swap 阶段 ===============================

def find_existing_swap(swap_dir, prefix, shot):
    """定位某套某段的换装图；shot=='a' 时兼容旧命名 <prefix>_*.png（如 g1_*.png）。"""
    p = latest_glob(os.path.join(swap_dir, f"{prefix}{shot}_*.png"))
    if p is None and shot == "a":
        p = latest_glob(os.path.join(swap_dir, f"{prefix}_*.png"))
    return p


def accept_swap_png(png, exp_size):
    """换装图验收：非黑（亮度>=阈值）+ 尺寸==预期。返回 (ok, brightness, size)。"""
    b = base.mean_brightness(png)
    try:
        sz = image_size(png)
    except Exception:
        sz = None
    ok_b = b is not None and b >= MIN_BRIGHTNESS
    ok_s = sz is not None and tuple(sz) == tuple(exp_size)
    return bool(ok_b and ok_s), b, sz


def stage_swap(args, date, project, slug, base_img, garments, report):
    shots = args.shots_per_outfit
    print(f"\n=== swap 阶段（Qwen-Image-2.1 双图参考换装，{len(garments)} 套 × "
          f"{shots} 段 = {len(garments) * shots} 张）===")
    if not os.path.exists(SWAP_WORKFLOW):
        print(f"[失败] 换装工作流不存在: {SWAP_WORKFLOW}")
        return 1
    if not os.path.exists(base_img):
        print(f"[失败] 基准图不存在: {base_img}")
        return 1
    with open(SWAP_WORKFLOW, "r", encoding="utf-8") as f:
        swap_tpl = json.load(f)

    swap_dir = os.path.join(OUTPUT_ROOT, date, project, "swap")
    os.makedirs(swap_dir, exist_ok=True)
    prog_path = swap_progress_path(date, project)
    prog = load_progress(prog_path)
    if args.resume:
        print(f"[进度] {prog_path}（已完成 {len(prog['completed'])}）")

    base_in = copy_to_input(base_img, f"swap_{slug}_base.png")
    try:
        base_size = image_size(base_img)
    except Exception as e:
        print(f"[失败] 读取基准图尺寸失败: {e}")
        return 1
    exp_size_a = expected_swap_size(*base_size)
    exp_size_b = expected_swap_size(*exp_size_a)   # g<i>a 已是桶尺寸 -> 自映射同桶
    print(f"[基准] {base_img}  尺寸={base_size[0]}x{base_size[1]} -> input/{base_in}")
    print(f"[基准] <key>a 预期输出尺寸（Kontext 桶）= {exp_size_a[0]}x{exp_size_a[1]}；"
          f"<key>b（以 <key>a 为输入）预期 = {exp_size_b[0]}x{exp_size_b[1]}")
    report["base_size"] = list(base_size)
    report["expected_swap_size"] = list(exp_size_a)
    report["shots_per_outfit"] = shots

    n_fail = 0

    def add_swap(key, idx, shot, g, desc, png, b, sz, reused, pid, secs, accepted, err=None):
        rec = {"index": idx, "shot": shot, "key": key, "garment": g, "desc": desc,
               "png": png, "brightness": round(float(b), 3) if b is not None else None,
               "size": list(sz) if sz else None, "reused": reused, "pid": pid,
               "seconds": secs, "accepted": accepted}
        if err:
            rec["error"] = err
        report["swaps"].append(rec)

    for idx, it in enumerate(garments, 1):
        if args.limit and idx > args.limit:
            print(f"[提示] --limit {args.limit}：跳过 {it['key']} 及之后")
            break
        g = it["path"]
        kp = it["key"]
        desc = it["desc"]
        garment_in = copy_to_input(g, f"swap_{slug}_{kp}.png")
        g1a_png = find_existing_swap(swap_dir, kp, "a")

        for shot in ["a", "b"][:shots]:
            key = f"{kp}{shot}"
            exp_size = exp_size_a if shot == "a" else exp_size_b
            out_prefix = f"{date}/{project}/swap/{key}"
            t0 = time.time()
            existing = find_existing_swap(swap_dir, kp, shot)

            # ---- 复用 ----
            if (existing and not args.force) or (args.resume and key in prog["completed"]):
                accepted, b, sz = accept_swap_png(existing, exp_size)
                print(f"[swap {key}] [复用] {os.path.basename(existing)}  亮度="
                      f"{b:.2f}  尺寸={sz}（期望 {exp_size}）-> "
                      f"{'通过' if accepted else '未通过'}")
                add_swap(key, idx, shot, g, desc, existing, b, sz, True, None, None, accepted)
                if accepted:
                    prog["results"][key] = {"file": existing, "brightness": b,
                                            "width": sz[0] if sz else None,
                                            "height": sz[1] if sz else None}
                    if key not in prog["completed"]:
                        prog["completed"].append(key)
                    save_progress(prog_path, prog)
                    if shot == "a":
                        g1a_png = existing
                else:
                    n_fail += 1
                continue

            # ---- 组装人物/服装输入 ----
            if shot == "a":
                person_in = base_in
                prompt = (it["prompt"] if it["prompt"]
                          else args.garment_prompt_template.replace(GARMENT_TOKEN, desc))
                seed = args.seed + idx
            else:
                if g1a_png is None:
                    g1a_png = find_existing_swap(swap_dir, kp, "a")
                if g1a_png is None:
                    n_fail += 1
                    print(f"[swap {key}] 缺少第 1 段换装图（{kp}a），跳过")
                    add_swap(key, idx, shot, g, desc, None, None, None, False, None,
                             None, False, err="missing %sa" % kp)
                    continue
                person_in = copy_to_input(g1a_png, f"swap_{slug}_{kp}a.png")
                prompt = args.second_shot_prompt
                seed = args.seed + 1000 + idx

            wf = base.inject_placeholders(swap_tpl, {
                "image": person_in, "garment": garment_in, "prompt": prompt,
                "seed": seed, "output": out_prefix})
            wf["13"]["inputs"]["steps"] = args.steps
            wf["13"]["inputs"]["cfg"] = args.cfg

            errors, _ = validate_nodes(wf)
            if errors:
                n_fail += 1
                print(f"[swap {key}] 校验失败（{len(errors)} 项），跳过:")
                for e in errors:
                    print("  - " + e)
                add_swap(key, idx, shot, g, desc, None, None, None, False, None, None,
                         False, err="validate: " + "; ".join(errors[:3]))
                continue

            print(f"[swap {key}] 提交（person={os.path.basename(person_in)} "
                  f"garment={os.path.basename(g)} shot={shot} seed={seed}）…", flush=True)
            try:
                pid = submit(wf)
            except Exception as e:
                n_fail += 1
                print(f"[swap {key}] 提交异常: {e}")
                add_swap(key, idx, shot, g, desc, None, None, None, False, None, None,
                         False, err=f"submit: {e}")
                continue
            print(f"[swap {key}] pid={pid}，等待完成…", flush=True)
            rec = base.wait_done(pid)
            if not rec:
                n_fail += 1
                print(f"[swap {key}] 执行失败/超时（pid={pid}）")
                add_swap(key, idx, shot, g, desc, None, None, None, False, pid,
                         round(time.time() - t0, 1), False, err="wait_done None")
                continue
            files = base.find_output_files(rec)
            png = None
            for p in files:
                if p.lower().endswith(".png") and os.path.exists(p):
                    png = p
            if not png:
                n_fail += 1
                print(f"[swap {key}] outputs 中未定位到 PNG（{files}）")
                add_swap(key, idx, shot, g, desc, None, None, None, False, pid,
                         round(time.time() - t0, 1), False, err="no png")
                continue

            accepted, b, sz = accept_swap_png(png, exp_size)
            ok_b = b is not None and b >= MIN_BRIGHTNESS
            ok_s = sz is not None and tuple(sz) == tuple(exp_size)
            print(f"[swap {key}] 产物: {png}")
            print(f"[swap {key}] 亮度={b:.2f}（阈>={MIN_BRIGHTNESS}）-> "
                  f"{'通过' if ok_b else '未通过'}")
            print(f"[swap {key}] 尺寸={sz}（预期 {exp_size}）-> "
                  f"{'通过' if ok_s else '未通过'}  本段 {time.time() - t0:.0f}s", flush=True)
            add_swap(key, idx, shot, g, desc, png, b, sz, False, pid,
                     round(time.time() - t0, 1), accepted)
            if accepted:
                prog["results"][key] = {"file": png, "brightness": b,
                                        "width": sz[0] if sz else None,
                                        "height": sz[1] if sz else None}
                if key not in prog["completed"]:
                    prog["completed"].append(key)
                save_progress(prog_path, prog)
                if shot == "a":
                    g1a_png = png
            else:
                n_fail += 1
                if shot == "a":
                    g1a_png = g1a_png or png   # 尽量仍让 b 段可用
    print(f"\n[swap] 完成 {sum(1 for s in report['swaps'] if s.get('accepted'))} / "
          f"失败 {n_fail}")
    return 0 if n_fail == 0 else 1


# =============================== video 阶段 ===============================

def collect_swap_images(date, project, shots_per_outfit, garments, limit=0):
    """按服装清单顺序收集换装图（<key>a,<key>b, 逐套）。

    key = 对象 id 或 g<idx>（字符串项）；shot a 兼容旧命名 <key>_*.png。
    limit = 套数上限（>0 时仅保留前 limit 套的所有段）。
    """
    swap_dir = os.path.join(OUTPUT_ROOT, date, project, "swap")
    items = []
    for idx, it in enumerate(garments, 1):
        if limit and idx > limit:
            break
        kp = it["key"]
        for shot in ["a", "b"][:shots_per_outfit]:
            p = latest_glob(os.path.join(swap_dir, f"{kp}{shot}_*.png"))
            if p is None and shot == "a":
                p = latest_glob(os.path.join(swap_dir, f"{kp}_*.png"))
            if p is None:
                continue
            items.append({"index": idx, "shot": shot, "key": f"{kp}{shot}", "png": p})
    return items


def find_existing_segment(seg_dir, i):
    return latest_glob(os.path.join(seg_dir, f"s{i}_*.mp4"))


def _merge_and_bgm(args, seg_files, seg_dir, date, project, report, length):
    """转场合并 +（可选）BGM 混音，写入 report["merged"]/["bgm"]。返回退出码。"""
    n = len(seg_files)
    tr = args.transition
    use_bgm = bool(args.bgm) or args.bgm_auto
    final_out = os.path.join(seg_dir, f"{project}_merged.mp4")
    raw_out = os.path.join(seg_dir, f"{project}_merged_raw.mp4") if use_bgm else final_out

    print(f"\n=== 转场合并（transition={tr}, xfade={args.xfade}s, {n} 段）===")
    ok, err = merge_with_transition(seg_files, raw_out, tr, args.xfade)
    if not ok:
        print("[失败] 合并失败:\n" + err)
        return 1
    total = seg.probe_duration(raw_out)
    has_a = seg.has_audio(raw_out)
    codec = probe_audio_codec(raw_out)
    if tr == "cut" or n == 1:
        expected = n * length / FPS
    else:
        expected = n * length / FPS - (n - 1) * args.xfade
    dur_ok = abs(total - expected) <= 0.5
    print(f"[完成] 合并片: {raw_out}")
    print(f"       总时长 {total:.3f}s（期望 ≈{expected:.3f}s = {n}×{length}/24"
          f" − {max(0, n - 1)}×{args.xfade}，容差±0.5s）-> {'通过' if dur_ok else '未通过'}")
    print(f"       含音轨={has_a}  音频 codec={codec}")

    merged_path = raw_out
    bgm_report = {"applied": False, "path": None, "bpm_estimate": None,
                  "beats_per_shot": None, "phase_align_sec": 0.0,
                  "bgm_volume": args.bgm_volume, "ambient_volume": args.ambient_volume,
                  "candidates": [],
                  "reason": "未启用 BGM（--no-bgm-auto 且未传 --bgm）"}

    if use_bgm:
        n_switch = n - 1
        ch, analyzed, phase_align, reason = None, [], 0.0, ""
        if args.bgm:
            bp = resolve_path(args.bgm)
            if os.path.exists(bp):
                ch = analyze_track(bp)
                analyzed = [ch]
                if args.bgm_align and ch.get("reliable") and ch.get("bpm"):
                    period = 60.0 / ch["bpm"]
                    s0 = (SEG_SECONDS - args.xfade) + args.xfade / 2.0
                    phase_align = (ch["phase"] - (s0 % period)) % period
                    reason = ("显式 --bgm；拍点相位 %.3fs 对齐切换点 %.3fs"
                              % (ch["phase"], s0))
                else:
                    reason = "显式 --bgm（未对齐）"
            else:
                reason = f"--bgm 文件不存在: {bp}"
        else:
            ch, analyzed, phase_align, reason = auto_select_bgm(
                args.bgm_dir, n_switch, args.xfade, align=args.bgm_align)

        cand_out = [{"path": a.get("path"), "name": os.path.basename(a.get("path") or ""),
                     "bpm": a.get("bpm"), "beats_per_shot": a.get("beats_per_shot"),
                     "distance": a.get("distance"), "strength": a.get("strength"),
                     "reliable": a.get("reliable"), "phase": a.get("phase"),
                     "error": a.get("error")} for a in analyzed]

        if ch is not None:
            print(f"[BGM] 选曲: {os.path.basename(ch['path'])}  BPM≈{ch.get('bpm')}  "
                  f"每段拍数≈{ch.get('beats_per_shot')}  相位对齐={phase_align:.3f}s"
                  f"（{reason}）")
            okm, errm = mix_bgm(raw_out, ch["path"], final_out,
                                args.bgm_volume, args.ambient_volume, phase_align)
            if not okm:
                print("[警告] BGM 混音失败，回退为无 BGM 版:\n" + errm)
                shutil.copy2(raw_out, final_out)
            else:
                merged_path = final_out
            bgm_report = {"applied": bool(okm), "path": ch["path"],
                          "name": os.path.basename(ch["path"]),
                          "bpm_estimate": ch.get("bpm"),
                          "beats_per_shot": ch.get("beats_per_shot"),
                          "phase_align_sec": round(phase_align, 3),
                          "align_reason": reason, "bgm_volume": args.bgm_volume,
                          "ambient_volume": args.ambient_volume, "candidates": cand_out}
        else:
            print(f"[警告] 未能选定 BGM：{reason}，回退为无 BGM 版")
            shutil.copy2(raw_out, final_out)
            bgm_report = {"applied": False, "path": None, "bpm_estimate": None,
                          "beats_per_shot": None, "phase_align_sec": 0.0,
                          "reason": reason, "candidates": cand_out,
                          "bgm_volume": args.bgm_volume,
                          "ambient_volume": args.ambient_volume}

    f_total = seg.probe_duration(merged_path)
    f_has = seg.has_audio(merged_path)
    f_codec = probe_audio_codec(merged_path)
    vol = probe_volume_stats(merged_path) if f_has else None
    print(f"[最终] 成片: {merged_path}")
    print(f"       时长 {f_total:.3f}s  含音轨={f_has}  音频 codec={f_codec}  音量={vol}")

    report["merged"] = {"path": merged_path, "duration": round(f_total, 3),
                        "has_audio": f_has, "audio_codec": f_codec,
                        "expected_duration": round(expected, 3), "duration_ok": dur_ok,
                        "n_segments": n, "seg_len": length, "transition": tr,
                        "xfade": args.xfade, "bgm_applied": bgm_report.get("applied", False),
                        "raw_path": raw_out if use_bgm else None,
                        "volume_stats": vol, "seconds": None}
    report["bgm"] = bgm_report
    report["segment_files"] = seg_files
    return 0


def stage_video(args, date, project, slug, garments, report):
    print(f"\n=== video 阶段（H3 I2V -> 转场合并）===")
    seg_dir = os.path.join(OUTPUT_ROOT, date, project)
    os.makedirs(seg_dir, exist_ok=True)
    length = base.align_length(args.seg_len)
    if length != args.seg_len:
        print(f"[对齐] seg-len {args.seg_len} -> {length}（17k+5）")
    for nm, v in (("width", args.width), ("height", args.height)):
        if v % 32 != 0:
            print(f"[警告] {nm}={v} 不是 32 的倍数")
    if not os.path.exists(I2V_WORKFLOW):
        print(f"[失败] I2V 工作流不存在: {I2V_WORKFLOW}")
        return 1
    with open(I2V_WORKFLOW, "r", encoding="utf-8") as f:
        i2v_tpl = json.load(f)

    images = collect_swap_images(date, project, args.shots_per_outfit, garments, args.limit)
    if not images:
        print(f"[失败] 未发现换装图: {os.path.join(seg_dir, 'swap', '<key>[ab]_*.png')}"
              f"（请先跑 --stage swap）")
        return 1
    print(f"[发现] 换装图 {len(images)} 张（出片顺序 "
          f"{', '.join(it['key'] for it in images)}）:")

    # 拷贝换装图到 input 稳定名（I2V LoadImage 从 input 读取）
    for it in images:
        it["input_name"] = copy_to_input(it["png"],
                                         f"swap_{slug}_first_{it['key']}.png")
        print(f"  - {it['key']}: {os.path.basename(it['png'])} -> input/{it['input_name']}")

    sample = base.inject_placeholders(i2v_tpl, {
        "first_frame": images[0]["input_name"], "prompt": args.motion_prompt,
        "width": args.width, "height": args.height, "length": length,
        "seed": args.seed + 1, "filename_prefix": f"{date}/{project}/s1"})
    if not pipe.run_prechecks(sample):
        return 1

    n_fail = 0
    seg_files = []
    for seq, it in enumerate(images, start=1):
        t0 = time.time()
        existing = find_existing_segment(seg_dir, seq)
        if existing and not args.force:
            dur = seg.probe_duration(existing)
            print(f"\n[段{seq} {it['key']}] [复用] {os.path.basename(existing)}  {dur:.3f}s  "
                  f"audio={seg.has_audio(existing)}", flush=True)
            okb = base.acceptance(existing, length, FPS)
            seg_files.append(existing)
            report["segments"].append({"index": seq, "key": it["key"], "path": existing,
                                       "duration": round(dur, 3), "reused": True,
                                       "accepted": okb, "pid": None,
                                       "seconds": round(time.time() - t0, 1)})
            if okb is False:
                n_fail += 1
            continue

        wf = base.inject_placeholders(i2v_tpl, {
            "first_frame": it["input_name"], "prompt": args.motion_prompt,
            "width": args.width, "height": args.height, "length": length,
            "seed": args.seed + seq, "filename_prefix": f"{date}/{project}/s{seq}"})
        try:
            pid = submit(wf)
        except Exception as e:
            n_fail += 1
            print(f"[段{seq}] 提交异常: {e}")
            report["segments"].append({"index": seq, "key": it["key"], "path": None,
                                       "duration": None, "reused": False, "accepted": False,
                                       "pid": None, "seconds": None, "error": f"submit: {e}"})
            continue
        print(f"\n[段{seq}/{len(images)} {it['key']}] 已提交 pid={pid} "
              f"first={it['input_name']}", flush=True)
        rec = base.wait_done(pid)
        if not rec:
            n_fail += 1
            print(f"[段{seq}] 执行失败/超时（pid={pid}），中止")
            report["segments"].append({"index": seq, "key": it["key"], "path": None,
                                       "duration": None, "reused": False, "accepted": False,
                                       "pid": pid, "seconds": round(time.time() - t0, 1),
                                       "error": "wait_done None"})
            return 1
        files = base.find_output_files(rec)
        mp4s = [p for p in files if p.lower().endswith(".mp4") and os.path.exists(p)]
        if not mp4s:
            n_fail += 1
            print(f"[段{seq}] 未定位到输出 MP4（{files}），中止")
            return 1
        mp4 = mp4s[-1]
        seg_files.append(mp4)
        dur = seg.probe_duration(mp4)
        print(f"[段{seq}] 完成 {os.path.basename(mp4)}  执行 "
              f"{base.exec_seconds(rec.get('status', {})) or 0:.0f}s  "
              f"本段 {time.time() - t0:.0f}s", flush=True)
        okb = base.acceptance(mp4, length, FPS)
        report["segments"].append({"index": seq, "key": it["key"], "path": mp4,
                                   "duration": round(dur, 3), "reused": False,
                                   "accepted": okb, "pid": pid,
                                   "seconds": round(time.time() - t0, 1)})
        if okb is False:
            n_fail += 1

    if not seg_files:
        print("[失败] 没有可拼接的分段文件")
        return 1
    if n_fail:
        print(f"[警告] 有 {n_fail} 段验收/提交异常，仍继续合并（保留现场）")
    return _merge_and_bgm(args, seg_files, seg_dir, date, project, report, length)


# =============================== merge-only ===============================

def stage_merge_only(args, date, project, report):
    print(f"\n=== merge-only：重拼已存在分段 ===")
    seg_dir = os.path.join(OUTPUT_ROOT, date, project)
    length = base.align_length(args.seg_len)
    files = seg.discover_segments(f"{date}/{project}")
    if not files:
        print(f"[失败] 未找到分段: {os.path.join(seg_dir, 's*_*.mp4')}")
        return 1
    print(f"[重拼] {len(files)} 段:")
    for i, p in enumerate(files, start=1):
        dur = seg.probe_duration(p)
        print(f"  - {os.path.basename(p)}  {dur:.3f}s  audio={seg.has_audio(p)}")
        okb = base.acceptance(p, length, FPS)
        report["segments"].append({"index": i, "path": p, "duration": round(dur, 3),
                                   "reused": True, "accepted": okb, "pid": None,
                                   "seconds": None})
    return _merge_and_bgm(args, files, seg_dir, date, project, report, length)


# =============================== 报告收口 ===============================

def finalize_report(args, date, project, report):
    """计算每段/合并片的帧间差统计与边界差，并写入 outfit_swap_report.json。"""
    print("\n=== 帧间差量化（灰度 x4 下采样）===")
    frames_list = []
    counts = []
    for s in report.get("segments", []):
        p = s.get("path")
        if not p or not os.path.exists(p):
            continue
        fr = seg.read_frames(p)
        st = frame_diff_stats(fr)
        s["frame_diff"] = st
        s["frames"] = len(fr)
        frames_list.append(fr)
        counts.append(len(fr))
        print(f"  段{s['index']}: mean={st['mean']} p95={st['p95']} max={st['max']} "
              f"({st['n']} 帧差)")
    report["boundary_diffs"] = boundary_diffs(frames_list) if frames_list else []

    mg = report.get("merged")
    if mg and mg.get("path") and os.path.exists(mg["path"]):
        mf = seg.read_frames(mg["path"])
        mg["frame_diff"] = frame_diff_stats(mf)
        mg["frames"] = len(mf)
        mg["boundary_diffs"] = merged_boundary_diffs(mf, counts) if counts else []
        print(f"  合并片: mean={mg['frame_diff']['mean']} p95={mg['frame_diff']['p95']} "
              f"max={mg['frame_diff']['max']}  边界={mg['boundary_diffs']}")

        # ---- 可选：仅时域轻平滑 ----
        if args.smooth != "off":
            out = os.path.join(os.path.dirname(mg["path"]),
                               os.path.splitext(os.path.basename(mg["path"]))[0] + "_smooth.mp4")
            print(f"\n=== 平滑（{args.smooth}）-> {os.path.basename(out)} ===")
            ok, err = smooth_video(mg["path"], out, args.smooth)
            if not ok:
                print("[警告] 平滑失败:\n" + err)
                report["smooth"] = {"mode": args.smooth, "ok": False, "error": err[-300:]}
            else:
                sf = seg.read_frames(out)
                sst = frame_diff_stats(sf)
                sharp_before = sharpness(mf)
                sharp_after = sharpness(sf)
                report["smooth"] = {"mode": args.smooth, "ok": True, "path": out,
                                    "frame_diff": sst, "frames": len(sf),
                                    "sharpness_before": sharp_before,
                                    "sharpness_after": sharp_after}
                print(f"  平滑前 mean={mg['frame_diff']['mean']} 清晰度={sharp_before}")
                print(f"  平滑后 mean={sst['mean']} 清晰度={sharp_after}")
                verdict = (f"帧间差 {mg['frame_diff']['mean']} -> {sst['mean']}；"
                           f"清晰度 {sharp_before} -> {sharp_after}")
                report["smooth"]["verdict"] = verdict
                print(f"  结论: {verdict}")

    report["baseline"] = BASELINE
    report["report_path"] = os.path.join(OUTPUT_ROOT, date, project, "outfit_swap_report.json")
    write_report(date, project, report)


def write_report(date, project, report):
    report["date"] = date
    report["project"] = project
    report["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path = os.path.join(OUTPUT_ROOT, date, project, "outfit_swap_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report.pop("segment_files", None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[报告] {path}")
    return path


# =============================== main ===============================

def main():
    global SWAP_WORKFLOW, I2V_WORKFLOW
    ap = argparse.ArgumentParser(
        description="OOTD 换装 -> 视频链路（Qwen 双图参考换装 + H3 I2V）")
    ap.add_argument("--base", default=DEFAULT_BASE, help="人物基准图路径")
    ap.add_argument("--garments", default=None, help="服装参考图，逗号分隔")
    ap.add_argument("--garments-file", default=None,
                    help="服装清单文件：纯文本每行一个路径，或 JSON 数组"
                         "（元素可为路径字符串或 {\"id\",\"garment\",\"prompt\"} 对象；"
                         "id 决定归档/段命名 <id>a/<id>b，prompt 覆盖 a 段换装提示词）")
    ap.add_argument("--project", default="outfit_swap")
    ap.add_argument("--date", default=None, help="归档日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--stage", choices=["swap", "video", "all"], default="all")
    ap.add_argument("--skip-swap", action="store_true", help="跳过 swap 阶段（复用已有换装图）")
    ap.add_argument("--merge-only", action="store_true", help="跳过生成，仅重拼已存在分段")
    ap.add_argument("--dry-run", action="store_true", help="只注入+逐节点校验+预检，不提交")
    ap.add_argument("--force", action="store_true", help="强制重跑已存在的换装图/分段")
    ap.add_argument("--resume", action="store_true", help="按 swap_progress.json 跳过已完成")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 套（0=全部）")
    ap.add_argument("--smooth", choices=["off", "light"], default="off",
                    help="合并后仅时域轻平滑（默认 off）")
    ap.add_argument("--shots-per-outfit", type=int, choices=[1, 2], default=2,
                    help="每套出片段数（默认 2：远端全身 + 走近半身，形成卡点节奏）")
    # 视频参数
    ap.add_argument("--width", type=int, default=736)
    ap.add_argument("--height", type=int, default=1088)
    ap.add_argument("--seg-len", type=int, default=73)
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--transition", choices=TRANSITION_CHOICES, default="fadeblack",
                    help="转场：cut/crossfade/fade/fadeblack/fadewhite/wipeleft/slideright"
                         "（默认 fadeblack，卡点切换瑕疵更小）")
    ap.add_argument("--xfade", type=float, default=0.3)
    ap.add_argument("--motion-prompt", default=DEFAULT_MOTION)
    # BGM 参数
    ap.add_argument("--bgm", default=None, help="显式指定 BGM 文件（mp3/wav）")
    ap.add_argument("--bgm-volume", type=float, default=1.0, help="BGM 音量（默认 1.0）")
    ap.add_argument("--ambient-volume", type=float, default=0.2,
                    help="H3 原生环境音音量（默认 0.2，压低）")
    ap.add_argument("--bgm-auto", dest="bgm_auto", action="store_true", default=True,
                    help="自动从 BGM 目录选曲（默认开）")
    ap.add_argument("--no-bgm-auto", dest="bgm_auto", action="store_false",
                    help="关闭自动选曲")
    ap.add_argument("--bgm-align", dest="bgm_align", action="store_true", default=True,
                    help="估计节拍相位并对齐切换点（默认开）")
    ap.add_argument("--no-bgm-align", dest="bgm_align", action="store_false",
                    help="关闭相位对齐")
    ap.add_argument("--bgm-dir", default=BGM_DIR, help="BGM 素材目录（自动选曲用）")
    # 换装参数
    ap.add_argument("--garment-prompt-template", default=DEFAULT_GARMENT_PROMPT)
    ap.add_argument("--second-shot-prompt", default=DEFAULT_SECOND_SHOT_PROMPT,
                    help="第 2 段（走近/半身）提示词")
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--cfg", type=float, default=3.0)
    ap.add_argument("--swap-workflow", default=SWAP_WORKFLOW)
    ap.add_argument("--i2v-workflow", default=I2V_WORKFLOW)
    args = ap.parse_args()

    SWAP_WORKFLOW = args.swap_workflow
    I2V_WORKFLOW = args.i2v_workflow

    date = args.date or _date.today().isoformat()
    project = args.project
    slug = pipe._ascii_slug(project)
    base_img = resolve_path(args.base)
    garments = resolve_garments(args)

    print(f"[配置] project={project}（slug={slug}） date={date} stage={args.stage} "
          f"smooth={args.smooth} shots/套={args.shots_per_outfit}")
    print(f"[基准] {base_img}（存在={os.path.exists(base_img)}）")
    print(f"[服装] {len(garments)} 套: "
          + ", ".join(f"{os.path.basename(it['path'])}[{it['key']}]"
                      f"{'(custom prompt)' if it['prompt'] else ''}" for it in garments))
    print(f"[视频] {args.width}x{args.height} seg-len={args.seg_len} seed={args.seed} "
          f"transition={args.transition} xfade={args.xfade}")
    print(f"[BGM ] auto={args.bgm_auto} align={args.bgm_align} bgm={args.bgm} "
          f"vol={args.bgm_volume} ambient={args.ambient_volume} dir={args.bgm_dir}")

    # ---- dry-run ----
    if args.dry_run:
        return run_dry_run(args, date, project, slug, base_img, garments)

    report = {
        "base": base_img,
        "garments": [{"id": it["id"], "key": it["key"], "path": it["path"],
                      "desc": it["desc"], "prompt": it["prompt"]} for it in garments],
        "shots_per_outfit": args.shots_per_outfit,
        "transition": args.transition,
        "xfade": args.xfade,
        "swaps": [],
        "segments": [],
        "merged": None,
        "bgm": None,
        "smooth": {"mode": args.smooth, "ok": None},
        "params": {
            "stage": args.stage, "project": project, "date": date,
            "width": args.width, "height": args.height, "seg_len": args.seg_len,
            "seed": args.seed, "transition": args.transition, "xfade": args.xfade,
            "shots_per_outfit": args.shots_per_outfit,
            "steps": args.steps, "cfg": args.cfg, "limit": args.limit,
            "smooth": args.smooth, "motion_prompt": args.motion_prompt,
            "second_shot_prompt": args.second_shot_prompt,
            "bgm_auto": args.bgm_auto, "bgm_align": args.bgm_align,
            "bgm": args.bgm, "bgm_volume": args.bgm_volume,
            "ambient_volume": args.ambient_volume, "bgm_dir": args.bgm_dir,
            "swap_workflow": os.path.basename(SWAP_WORKFLOW),
            "i2v_workflow": os.path.basename(I2V_WORKFLOW),
        },
    }
    t_all = time.time()

    # ---- 阶段调度 ----
    if args.merge_only:
        rc = stage_merge_only(args, date, project, report)
    else:
        rc = 0
        if args.stage in ("all", "swap") and not args.skip_swap:
            rc = stage_swap(args, date, project, slug, base_img, garments, report)
        elif args.skip_swap:
            print("[跳过] swap 阶段（--skip-swap）")
        if rc == 0 and args.stage in ("all", "video"):
            rc = stage_video(args, date, project, slug, garments, report)

    finalize_report(args, date, project, report)
    print(f"\n[结束] 总耗时 {(time.time() - t_all) / 60:.1f} min  退出码={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())