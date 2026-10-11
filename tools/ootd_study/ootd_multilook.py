#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OOTD 多版本同步渲染引擎（Wan2.2 Animate 9:16 共享驱动）

用「一条驱动表演视频 + N 张换装参考图」逐套服装渲染出**与驱动逐帧同步**的竖屏版本：
驱动视频先规范化为 16fps，再按块长（默认 49 帧）切块；逐 look 逐块注入
`workflows/v5/wan_animate_9x16_api.json`（派生自 move 工作流）校验并提交；
全部块按序硬切拼接为 `versions/v<k>_full16.mp4`，并以驱动整段音频重新封装；
可选经 `h3_enhance_submit.py`（RIFE）补帧到 30fps -> `versions/v<k>_30fps.mp4`。
`compose` 阶段懒加载转发给 Task 3 提供的 `multilook_compose.run_compose`。

阶段（--stage）：
  render   驱动 16fps 规范化 -> 切块 -> 逐 look 逐块渲染 -> 块验收 -> 拼接 + 音频重封装
           ->（默认）RIFE 补帧；进度/断点见 render_progress.json
  compose  懒加载 multilook_compose.run_compose（Task 3 提供），按接口契约组装 cfg 转发
  all      render 后 compose，并把 render 段与 compose 返回报告合并写 multilook_report.json

归档（output/<date>/<project>/）：
  drv16.mp4                       驱动 16fps 规范化视频
  versions/<k>_chunk<i>_*.mp4     逐 look 逐块产物
  versions/v<k>_full16.mp4        逐 look 整版本（块硬切拼接 + 驱动整段音频）
  versions/v<k>_30fps.mp4         RIFE 补帧产物（--skip-enhance 时不生成）
  render_progress.json            逐 look 逐块进度（pid/状态/耗时/产物）
  multilook_report.json           render（+compose）汇总报告
  input/<slug>_drv_chunk<i>.mp4   驱动分块（供 LoadVideo 读取）
  input/<slug>_look<k>.png        换装参考图（供 LoadImage 读取）

复用（不修改）：tools/h3_fast_submit.py、tools/h3_fast_segmented.py、
tools/ootd_study/ootd_pipeline.py、tools/h3_enhance_submit.py。

用法:
  # 干跑：文件检查 + 逐块工作流校验 + 块计划（不提交）
  python tools/ootd_study/ootd_multilook.py --dry-run --driving input/ootd_target.mp4 \
      --looks looks.json
  # 只渲染（默认等待完成）
  python tools/ootd_study/ootd_multilook.py --stage render --driving ootd_target.mp4 \
      --looks looks.json --project ootd_multilook_poc
  # 只提交不等待（记录 pid，供后台等待）
  python tools/ootd_study/ootd_multilook.py --stage render --no-wait --looks looks.json
  # 渲染 + 合成
  python tools/ootd_study/ootd_multilook.py --stage all --looks looks.json
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
import ootd_pipeline as pipe           # noqa: E402  (复用 ROOT/INPUT_ROOT/OUTPUT_ROOT/_ascii_slug)

ROOT = pipe.ROOT
INPUT_ROOT = pipe.INPUT_ROOT
OUTPUT_ROOT = pipe.OUTPUT_ROOT

WORKFLOW = os.path.join(_THIS_DIR, "workflows", "v5", "wan_animate_9x16_api.json")
ENHANCE_SCRIPT = os.path.join(_TOOLS_DIR, "h3_enhance_submit.py")
ENHANCE_WORKFLOW = os.path.join(ROOT, "workflows", "v5", "h3_enhance_v5_api.json")
PYTHON_ABS = r"C:\Users\kenzhao\anaconda3\python.exe"
FFPROBE_ABS = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"

FPS = 16.0                       # 驱动规范化帧率（定值）
DEFAULT_PROJECT = "ootd_multilook_poc"
DEFAULT_DRIVING = "ootd_target.mp4"
WAN_LEN_MIN = 5                  # Wan 潜空间最短块长（4k+1）
WAN_LEN_MAX = 49                 # 块长上限（49 = 4*12+1）
MIN_BRIGHTNESS = 3.0

# ---- 驱动角落遮罩（消除 DWPose 对"贴纸拼贴型驱动"四角小人的误检测）----
# 背景：Move 模式下驱动 RGB 不直接喂模型，仅用于 DWPose 提取 pose_video/face_video。
# 若驱动本身是"主人物居中 + 四角各 1 个其他服装小人"的贴纸拼贴视频（如 v08/ootd_target），
# DWPose 会把四角小人也检测出来，导致生成结果里多出 4 个畸变"洋娃娃"。遮罩仅作用于
# pose/face 提取用的驱动帧，**不会出现在成片里**（成片背景/内容来自模型生成）。
REF_ANALYSIS_STRUCTURE = os.path.join(OUTPUT_ROOT, "2026-10-02", "ref_analysis", "structure.json")
MASK_CORNER_PAD = 12             # 结构图 tile rect 向外扩张像素（合并进已验证 rect）
# 已验证默认角落 rect（1080×1920 坐标，已含安全外扩，最终直接使用）。
# 覆盖对象：'贴纸拼贴型驱动'（如 v08/ootd_target.mp4，主人物居中 + 四角各 1 个抠像小人）。
# 说明：structure.json 的 tile_geometry.per_frame.v8.tiles rect 为"角标窗口"包围盒、
# 明显不足包住发光/外溢的贴纸小人（实测覆盖失败，详见 output/2026-10-02/
# ootd_multilook_maskcheck/mask_fix_report.json）；此处的 4 个 rect 是在真实驱动帧
# （1080×1920，t=1..13s）上目视标定、经验证可完整盖住四角小人且不遮挡主人物躯干。
DEFAULT_CORNER_RECTS = [
    [45, 40, 340, 665],     # top_left
    [690, 40, 365, 665],    # top_right
    [5, 1200, 405, 665],    # bottom_left
    [695, 1295, 330, 570],  # bottom_right
]


# =============================== 小工具 ===============================

def resolve_path(p):
    """绝对路径原样返回；相对路径优先相对 cwd，其次相对 ROOT。"""
    if os.path.isabs(p):
        return os.path.normpath(p)
    if os.path.exists(p):
        return os.path.abspath(p)
    return os.path.normpath(os.path.join(ROOT, p))


def resolve_input(name):
    """input 下的文件名 / 相对路径 -> 绝对路径。"""
    if os.path.isabs(name):
        return os.path.normpath(name)
    ip = os.path.join(INPUT_ROOT, name)
    if os.path.exists(ip):
        return os.path.abspath(ip)
    if os.path.exists(name):
        return os.path.abspath(name)
    return None


def copy_to_input(src, name):
    os.makedirs(INPUT_ROOT, exist_ok=True)
    dst = os.path.join(INPUT_ROOT, name)
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copy2(src, dst)
    return name


def ffprobe_exe():
    if os.path.exists(FFPROBE_ABS):
        return FFPROBE_ABS
    return shutil.which("ffprobe")


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


def validate_nodes(wf):
    """逐节点校验；先清 LoadImage/LoadVideo 动态文件枚举缓存（避免复制新文件后误判）。"""
    base._INFO_CACHE.pop("LoadImage", None)
    base._INFO_CACHE.pop("LoadVideo", None)
    return base.validate_workflow(wf)


# =============================== 帧长 / 切块 ===============================

def align_wan_length(n, lo=WAN_LEN_MIN, hi=WAN_LEN_MAX):
    """把块长对齐到 Wan 潜空间 4k+1（向上取整，钳制在 [lo, hi]）。

    末块帧数可能不满足 4k+1，此时向上取整到最近的 4k+1（不足帧用末帧复制补齐），
    以保证生成视频时长 ≈ 驱动时长（避免向下取整造成的时长偏短）。
    """
    n = int(n)
    if n <= lo:
        return lo
    if n >= hi:
        return hi
    r = (n - 1) % 4
    if r == 0:
        return n
    return min(n + (4 - r), hi)


def plan_chunks(total_frames, chunk_len, max_chunks=0):
    """切块计划 -> [(start, raw, length), ...]。

    非末块 length=chunk_len（须为 4k+1）；末块 raw 不足 chunk_len 时 length=align_wan_length(raw)。
    max_chunks>0 时只保留前 max_chunks 块（冒烟/PoC 部分跑用）。
    """
    chunks = []
    i = 0
    while i * chunk_len < total_frames:
        start = i * chunk_len
        raw = min(chunk_len, total_frames - start)
        length = chunk_len if raw == chunk_len else align_wan_length(raw)
        chunks.append((start, raw, length))
        i += 1
        if max_chunks and len(chunks) >= max_chunks:
            break
    return chunks


# =============================== 驱动规范化 / 分块导出 ===============================

def probe_nb_frames(mp4):
    """取视频流帧数（nb_frames）；缺失时退回 round(时长 × 帧率)。"""
    ff = ffprobe_exe()
    if not ff:
        return 0
    r = subprocess.run([ff, "-v", "error", "-select_streams", "v",
                        "-show_entries", "stream=nb_frames",
                        "-of", "default=noprint_wrappers=1:nokey=1", mp4],
                       capture_output=True, text=True)
    try:
        n = int(r.stdout.strip())
        if n > 0:
            return n
    except Exception:
        pass
    return int(round(seg.probe_duration(mp4) * seg.probe_fps(mp4)))


def normalize_driving(src, out_mp4, fps=FPS, mask_rects=None):
    """驱动视频规范化为固定 fps（ffmpeg -vf fps=16）并在同一次编码内施加角落遮罩，保留音频。

    角落遮罩（mask_rects: [[x,y,w,h], ...]，1080×1920 坐标）用 drawbox 填充灰色实心块。
    Move 模式下驱动 RGB 不直接进模型，仅用于 DWPose 提取 pose_video/face_video；遮罩只为
    消除四角小人对 DWPose 的误导，**不会出现在成片里**。返回 (ok, err)。
    """
    ff = base.resolve_ffmpeg()
    if not ff:
        return False, "未找到 ffmpeg"
    vf = "fps=%g" % fps
    for (x, y, w, h) in (mask_rects or []):
        vf += ",drawbox=x=%d:y=%d:w=%d:h=%d:color=gray@1:t=fill" % (x, y, w, h)
    cmd = [ff, "-y", "-i", src, "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-r", "%g" % fps]
    if seg.has_audio(src):
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out_mp4)
    return ok, (r.stderr or "")[-800:]


def export_chunk(norm_mp4, start, raw, length, out_mp4, fps=FPS):
    """由 16fps 规范化视频导出第 start..start+raw 帧块，长度为 length（不足用末帧复制补齐）。

    - 视频：trim(精确帧范围) + setpts +（末块）tpad clone 补齐到 length 帧
    - 音频：atrim 同段（真实帧范围）
    """
    ff = base.resolve_ffmpeg()
    if not ff:
        return False, "未找到 ffmpeg"
    vf = "trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS" % (start, start + raw)
    pad = length - raw
    if pad > 0:
        vf += ",tpad=stop=%d:stop_mode=clone" % pad
    cmd = [ff, "-y", "-i", norm_mp4, "-vf", vf]
    if seg.has_audio(norm_mp4):
        cmd += ["-af", "atrim=start=%.6f:end=%.6f,asetpts=PTS-STARTPTS"
                % (start / fps, (start + raw) / fps),
                "-c:a", "aac", "-b:a", "128k", "-ac", "2"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "%g" % fps, "-movflags", "+faststart", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out_mp4)
    return ok, (r.stderr or "")[-800:]


# =============================== 进度 ===============================

def progress_path(date, project):
    return os.path.join(OUTPUT_ROOT, date, project, "render_progress.json")


def load_progress(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            d.setdefault("completed", [])
            d.setdefault("chunks", {})
            return d
        except Exception:
            pass
    return {"completed": [], "chunks": {}, "updated": None}


def save_progress(path, prog):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prog["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False, indent=2)


# =============================== looks 清单 ===============================

def read_looks(path):
    """读取 looks.json -> [{index, id, key, path}]。

    兼容两种写法：
      - 字符串数组：["a.png", "b.png"]（id 缺省 g1/g2…）
      - 对象数组：[{"id":"g1","image":"a.png"}, ...]（也接受 path/png 字段）
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"looks JSON 解析失败: {e}")
    if not isinstance(data, list) or not data:
        raise ValueError("looks JSON 根节点必须是非空数组")
    raw = []
    for it in data:
        if isinstance(it, str):
            raw.append({"id": None, "image": it.strip()})
        elif isinstance(it, dict):
            img = it.get("image") or it.get("path") or it.get("png")
            if not img:
                raise ValueError(f"look 对象缺少 image/path 字段: {it}")
            raw.append({"id": it.get("id"), "image": str(img)})
        else:
            raise ValueError(f"不支持的 look 项类型: {type(it).__name__}")
    out = []
    for idx, it in enumerate(raw, 1):
        p = resolve_input(it["image"]) or resolve_path(it["image"])
        out.append({"index": idx, "id": it["id"] or f"g{idx}",
                    "key": it["id"] or f"g{idx}", "path": p})
    return out


def resolve_driving(name):
    p = resolve_input(name) or resolve_path(name)
    return p


# =============================== 角落遮罩（rect 解析/来源） ===============================

def parse_rects(s):
    """解析 "x,y,w,h;x,y,w,h;..." -> [[x,y,w,h], ...]（1080×1920 坐标系）。"""
    rects = []
    for part in str(s).split(";"):
        part = part.strip()
        if not part:
            continue
        nums = [int(float(v)) for v in part.replace(",", " ").split()]
        if len(nums) != 4:
            raise ValueError(f"rect 需为 x,y,w,h 四项，收到 {part!r}")
        if nums[2] <= 0 or nums[3] <= 0:
            raise ValueError(f"rect 宽高必须为正，收到 {part!r}")
        rects.append(nums)
    if not rects:
        raise ValueError("未解析到任何 rect")
    return rects


def expand_rect(r, pad):
    x, y, w, h = r
    return [max(0, x - pad), max(0, y - pad), w + 2 * pad, h + 2 * pad]


def union_rects(a, b):
    """两 rect 的并集包围盒（用于把结构图 tile rect 与已验证 rect 合并，保证覆盖）。"""
    x0 = min(a[0], b[0])
    y0 = min(a[1], b[1])
    x1 = max(a[0] + a[2], b[0] + b[2])
    y1 = max(a[1] + a[3], b[1] + b[3])
    return [x0, y0, x1 - x0, y1 - y0]


def _structure_rects_for(driving_abs):
    """从 ref_analysis/structure.json 按驱动映射取角标 rects -> (rects|None, ref_label|None)。

    映射优先级：文件名与 videos[].file 完全一致 -> 文件名含 ref_label（如 xxx_v8_xxx）
    -> 时长匹配（±0.05s，能覆盖 ootd_target.mp4 与 v8 同为 14.048s 的情况）。
    """
    if not os.path.exists(REF_ANALYSIS_STRUCTURE):
        return None, None
    try:
        with open(REF_ANALYSIS_STRUCTURE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        return None, None
    videos = data.get("videos") or []
    base = os.path.basename(driving_abs)
    ref = None
    for v in videos:                                   # 1) 文件名完全一致
        if base == v.get("file"):
            ref = v.get("ref_label")
            break
    if ref is None:                                    # 2) 文件名含 ref_label
        for v in videos:
            lab = v.get("ref_label")
            if lab and (f"_{lab}_" in base or f"_{lab}." in base or base.startswith(f"{lab}_")):
                ref = lab
                break
    if ref is None:                                    # 3) 时长匹配
        try:
            drv_dur = seg.probe_duration(driving_abs)
        except Exception:
            drv_dur = 0.0
        best = None
        for v in videos:
            d = v.get("duration_s")
            if d is None or not drv_dur:
                continue
            diff = abs(float(d) - drv_dur)
            if diff <= 0.05 and (best is None or diff < best[0]):
                best = (diff, v.get("ref_label"))
        if best:
            ref = best[1]
    if ref is None:
        return None, None
    pf = ((data.get("tile_geometry") or {}).get("per_frame") or {}).get(ref) or {}
    rects = [t.get("rect") for t in (pf.get("tiles") or []) if t.get("rect")]
    return (rects or None), ref


def resolve_mask_rects(arg, driving_abs):
    """解析 --mask-corners -> (rects, info)。

    - "off"            : 不遮罩，行为与改造前一致
    - "auto"（默认）    : 读 structure.json 按驱动映射取角标 rects，并与已验证默认 rect 取
                         并集（结构图 tile rect 不足覆盖外溢贴纸小人，故取并保底）；无匹配时
                         直接用已验证默认 rect。
    - "<rects>"        : 显式 "x,y,w,h;..."（按原值使用，不额外扩 pad）
    """
    if arg == "off":
        return [], {"mode": "off", "source": "off", "rects": []}
    if arg and arg != "auto":
        rects = parse_rects(arg)
        return rects, {"mode": "explicit", "source": "cli:<rects>", "rects": rects}
    rects, ref = _structure_rects_for(driving_abs)
    if rects:
        sr = [expand_rect(r, MASK_CORNER_PAD) for r in rects]
        n = min(len(sr), len(DEFAULT_CORNER_RECTS))
        merged = [union_rects(sr[i], DEFAULT_CORNER_RECTS[i]) for i in range(n)]
        merged += sr[n:]
        return merged, {"mode": "auto",
                        "source": f"structure.json tile_geometry.per_frame.{ref}.tiles(+pad "
                                  f"{MASK_CORNER_PAD}) ∪ verified default",
                        "ref_label": ref, "rects": merged}
    return [list(r) for r in DEFAULT_CORNER_RECTS], {
        "mode": "auto",
        "source": "verified default（真实驱动帧 1080x1920 标定；针对贴纸拼贴型驱动）",
        "rects": [list(r) for r in DEFAULT_CORNER_RECTS]}


# =============================== 拼接 + 音频重封装 ===============================

def normalize_chunk_for_concat(src_mp4, dst_mp4, expected, fps=FPS):
    """把单块产物裁剪/补齐到 planned 帧数（expected），供无损拼接。

    WanAnimateToVideo 在 length=N 时实际解码输出 N+4 帧：**多出的 4 帧是前置的
    "reference/trim 潜帧"块（第 0–3 帧，第 0 帧≈换装参考图）**，其后 N 帧才对应
    驱动帧。故裁剪 = **丢弃前 (actual-expected) 帧、保留其后 expected 帧**。
    若实际帧数少于 expected（末块 4k+1 对齐等），末帧复制补齐。
    丢弃分块音轨（整版本音轨由驱动整段音频重封装）。
    """
    ff = base.resolve_ffmpeg()
    if not ff:
        return False, "未找到 ffmpeg", {}
    actual = probe_nb_frames(src_mp4)
    front = max(0, actual - expected)      # 前置 reference/trim 帧数
    pad = max(0, expected - actual)        # 帧数不足时末帧补齐
    keep = min(actual, expected)
    vf = "trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS" % (front, front + keep)
    if pad > 0:
        vf += ",tpad=stop=%d:stop_mode=clone" % pad
    r = subprocess.run([ff, "-y", "-i", src_mp4, "-vf", vf, "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-r", "%g" % fps,
                        "-movflags", "+faststart", dst_mp4],
                       capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(dst_mp4)
    return ok, (r.stderr or "")[-800:], {"actual": actual, "front_trim": front,
                                         "tail_pad": pad, "kept": keep}


def concat_full16(chunk_files, out_path, driving_abs, expected_lengths,
                  driving_frames=0, fps=FPS):
    """块裁剪后硬切拼接 -> 补齐到驱动帧数 -> 以驱动整段音频重新封装。

    - expected_lengths: 与 chunk_files 一一对应的计划帧数（非末块=chunk_len，末块=align）。
      每块先由 normalize_chunk_for_concat 丢弃前置 reference/trim 帧（+末帧补齐）。
    - driving_frames>0 且拼接帧数与它相差 ≤4 帧时，用 tpad 把总帧数补齐到驱动帧数。
    返回 (ok, err, info)。
    """
    ff = base.resolve_ffmpeg()
    if not ff:
        return False, "未找到 ffmpeg", {}
    n = len(chunk_files)
    if n == 0:
        return False, "没有可拼接的分块", {}
    if len(expected_lengths) != n:
        return False, "expected_lengths 与 chunk_files 数量不一致", {}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp_dir = out_path + ".tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    info = {"chunks": []}

    # ---- 1. 逐块裁剪/补齐（丢弃分块音轨）----
    norm_files = []
    for i, (src, exp) in enumerate(zip(chunk_files, expected_lengths)):
        dst = os.path.join(tmp_dir, "norm_%02d.mp4" % i)
        ok, err, meta = normalize_chunk_for_concat(src, dst, exp, fps)
        meta.update({"src": src, "expected": exp})
        info["chunks"].append(meta)
        print("  [块%d] actual=%d -> expected=%d（丢弃前置 %d 帧，末帧补齐 %d）"
              % (i, meta.get("actual", -1), exp, meta.get("front_trim", 0),
                 meta.get("tail_pad", 0)))
        if not ok:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False, "块%d 裁剪失败:\n%s" % (i, err), info
        norm_files.append(dst)

    # ---- 2. 硬切拼接（-c copy，无音轨）----
    list_file = os.path.join(tmp_dir, "concat.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in norm_files:
            f.write("file '%s'\n" % os.path.abspath(p).replace("\\", "/").replace("'", "'\\''"))
    concat_video = os.path.join(tmp_dir, "concat.mp4")
    r = subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", list_file,
                        "-an", "-c:v", "copy", "-movflags", "+faststart", concat_video],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(concat_video):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False, "视频拼接失败:\n" + (r.stderr or "")[-800:], info
    n_c = probe_nb_frames(concat_video)

    # ---- 3. 帧数补齐到驱动帧数（相差 ≤4 帧才补齐；>4 视为部分渲染不补）----
    target = sum(expected_lengths)
    if driving_frames and 0 <= (driving_frames - n_c) <= 4:
        target = driving_frames
    info["concat_frames"] = n_c
    info["target_frames"] = target
    info["driving_frames"] = driving_frames
    tmp_video = concat_video
    if n_c != target:
        if n_c > target:
            vf2 = "trim=start_frame=0:end_frame=%d,setpts=PTS-STARTPTS" % target
        else:
            vf2 = "tpad=stop=%d:stop_mode=clone" % (target - n_c)
        padded = os.path.join(tmp_dir, "padded.mp4")
        r = subprocess.run([ff, "-y", "-i", concat_video, "-vf", vf2, "-frames:v", str(target),
                            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-r", "%g" % fps,
                            "-movflags", "+faststart", padded],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(padded):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False, "帧数补齐失败:\n" + (r.stderr or "")[-800:], info
        tmp_video = padded
        print("  [补齐] 拼接 %d 帧 -> %d 帧（tpad clone / trim）" % (n_c, target))
    info["final_frames"] = target

    # ---- 4. 以驱动整段音频重新封装；音频不足用 apad 填充到视频时长 ----
    dur = target / fps
    if driving_abs and os.path.exists(driving_abs) and seg.has_audio(driving_abs):
        cmd = [ff, "-y", "-i", tmp_video, "-i", driving_abs,
               "-map", "0:v", "-map", "1:a", "-c:v", "copy",
               "-c:a", "aac", "-b:a", "192k", "-af", "apad",
               "-t", "%.6f" % dur, "-movflags", "+faststart", out_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out_path):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return False, "音频重封装失败:\n" + (r.stderr or "")[-800:], info
    else:
        shutil.copy2(tmp_video, out_path)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return True, "", info


def verify_version(mp4, driving_abs, width, height, driving_frames=0, fps=FPS, tol=0.1):
    """整版本验收：帧数==驱动帧数(±1) / 尺寸 / 时长≈驱动 / 含音轨 / 抽帧非黑。返回 dict。"""
    res = {"path": mp4, "exists": os.path.exists(mp4)}
    if not res["exists"]:
        res["ok"] = False
        res["reasons"] = ["产物不存在"]
        return res
    p = probe_nb_frames(mp4)
    dur = seg.probe_duration(mp4)
    drv_dur = seg.probe_duration(driving_abs) if os.path.exists(driving_abs) else 0.0
    has_a = seg.has_audio(mp4)
    # 尺寸
    ff = ffprobe_exe()
    w = h = None
    if ff:
        r = subprocess.run([ff, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", mp4], capture_output=True, text=True)
        try:
            w, h = [int(x) for x in r.stdout.strip().split(",")[:2]]
        except Exception:
            pass
    frame_ok = (driving_frames == 0) or (abs(p - driving_frames) <= 1)
    dur_ok = (drv_dur == 0.0) or (abs(dur - drv_dur) <= tol)
    size_ok = (w == width and h == height)
    bright = base.acceptance(mp4, p, fps) if p else None
    reasons = []
    if not frame_ok:
        reasons.append(f"帧数 {p} != 驱动 {driving_frames}（±1）")
    if not dur_ok:
        reasons.append(f"时长 {dur:.4f}s 与驱动 {drv_dur:.4f}s 差 {abs(dur - drv_dur):.4f}s > {tol}s")
    if not size_ok:
        reasons.append(f"尺寸 {w}x{h} != {width}x{height}")
    if not has_a:
        reasons.append("缺音轨")
    if bright is False:
        reasons.append("抽帧亮度未通过（疑似黑屏）")
    res.update({"frames": p, "driving_frames": driving_frames,
                "frame_delta": (p - driving_frames) if driving_frames else None,
                "fps": fps, "duration": round(dur, 4),
                "driving_duration": round(drv_dur, 4), "size": [w, h],
                "has_audio": has_a, "frame_ok": frame_ok, "duration_ok": dur_ok,
                "size_ok": size_ok, "brightness_ok": bright, "reasons": reasons})
    res["ok"] = bool(frame_ok and dur_ok and size_ok and has_a and (bright is not False))
    return res


# =============================== RIFE 补帧（子进程复用 h3_enhance_submit） ===============================

def enhance_version(src_mp4, prefix, out_size, target_fps, work_dir):
    """子进程调用 h3_enhance_submit.py 做 RIFE 补帧（16 -> target_fps）。

    h3_enhance_submit.py 的默认 RIFE 工作流 source_fps 固定 24.0，对 16fps 源不正确；
    这里由共享模板派生一份 source_fps=实际源帧率的临时工作流，经 --workflow 传入
    （不改动共享文件）。out_size=[w,h] 缺省与源一致（ESRGAN 前置降采样由该脚本内部处理）。
    """
    if not os.path.exists(ENHANCE_SCRIPT):
        return False, f"未找到 {ENHANCE_SCRIPT}", None
    if not os.path.exists(ENHANCE_WORKFLOW):
        return False, f"未找到 {ENHANCE_WORKFLOW}", None
    with open(ENHANCE_WORKFLOW, "r", encoding="utf-8") as f:
        tpl = json.load(f)
    src_fps = seg.probe_fps(src_mp4) or FPS
    for _nid, node in tpl.items():
        if node.get("class_type") == "RIFEInterpolation":
            node["inputs"]["source_fps"] = float(src_fps)
    os.makedirs(work_dir, exist_ok=True)
    tmp_wf = os.path.join(work_dir, "enhance_%gfps_api.json" % src_fps)
    with open(tmp_wf, "w", encoding="utf-8") as f:
        json.dump(tpl, f, ensure_ascii=False, indent=2)

    w, h = out_size
    py = PYTHON_ABS if os.path.exists(PYTHON_ABS) else sys.executable
    cmd = [py, ENHANCE_SCRIPT, "--workflow", tmp_wf, "--source", src_mp4,
           "--target-fps", "%g" % target_fps,
           "--out-width", str(w), "--out-height", str(h),
           "--prefix", prefix]
    print("  [enhance] " + " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    print(out[-2000:])
    return (r.returncode == 0), out[-2000:], None


# =============================== render 阶段 ===============================

def render_stage(args, date, project, slug, driving_abs, looks, report):
    out_dir = os.path.join(OUTPUT_ROOT, date, project)
    versions_dir = os.path.join(out_dir, "versions")
    os.makedirs(versions_dir, exist_ok=True)
    prog_file = progress_path(date, project)
    prog = load_progress(prog_file)
    if args.resume:
        print(f"[进度] {prog_file}（已完成 {len(prog['completed'])} 块）")

    # ---- 1. 驱动 16fps 规范化 + 角落遮罩 ----
    norm_mp4 = os.path.join(out_dir, "drv16.mp4")
    try:
        mask_rects, mask_info = resolve_mask_rects(args.mask_corners, driving_abs)
    except ValueError as e:
        print(f"[失败] --mask-corners 解析失败: {e}")
        return 1
    report["mask_corners"] = mask_info
    if mask_rects:
        print(f"[遮罩] 已遮罩 {len(mask_rects)} 个角落 rect（来源: {mask_info['source']}）:")
        for i, (x, y, w, h) in enumerate(mask_rects):
            print(f"    rect{i}: x={x} y={y} w={w} h={h}")
        print("       注：Move 模式驱动 RGB 不直接喂模型，仅用于 DWPose 取 pose/face，"
              "遮罩不会出现在成片里")
    else:
        print("[遮罩] --mask-corners off：不遮罩（与改造前行为一致）")
    print(f"\n[驱动] 规范化 16fps: {driving_abs} -> {norm_mp4}")
    ok, err = normalize_driving(driving_abs, norm_mp4, mask_rects=mask_rects)
    if not ok:
        print("[失败] 驱动规范化失败:\n" + err)
        return 1
    total = probe_nb_frames(norm_mp4)
    drv_dur = seg.probe_duration(driving_abs)
    print(f"[驱动] 规范化后 {total} 帧 @ {seg.probe_fps(norm_mp4)}fps "
          f"（源时长 {drv_dur:.3f}s，含音轨={seg.has_audio(norm_mp4)}）")

    # ---- 2. 切块计划 + 导出分块 mp4 ----
    chunk_len = args.chunk_len
    if (chunk_len - 1) % 4 != 0:
        chunk_len = align_wan_length(chunk_len)
        print(f"[对齐] chunk-len {args.chunk_len} -> {chunk_len}（4k+1）")
    chunks = plan_chunks(total, chunk_len, args.max_chunks)
    print(f"[切块] 块长={chunk_len} 共 {len(chunks)} 块" +
          (f"（--max-chunks {args.max_chunks}）" if args.max_chunks else "") + ":")
    chunk_in_names = []
    for i, (start, raw, length) in enumerate(chunks):
        name = f"{slug}_drv_chunk{i}.mp4"
        dst = os.path.join(INPUT_ROOT, name)
        uneven = "（末块补齐到 %d 帧）" % length if length != raw else ""
        print(f"  chunk{i}: 起始帧={start} 可用={raw} 生成长度={length} "
              f"t={start / FPS:.2f}s{uneven}")
        ok, err = export_chunk(norm_mp4, start, raw, length, dst)
        if not ok:
            print(f"[失败] 分块导出失败 chunk{i}:\n" + err)
            return 1
        chunk_in_names.append(name)

    # ---- 3. 加载工作流模板 + 拷贝参考图 ----
    wf_path = getattr(args, "workflow", None) or WORKFLOW
    if not os.path.exists(wf_path):
        print(f"[失败] 工作流不存在: {wf_path}")
        return 1
    with open(wf_path, "r", encoding="utf-8") as f:
        tpl = json.load(f)
    for it in looks:
        if not os.path.exists(it["path"]):
            print(f"[失败] 换装参考图不存在: {it['path']}")
            return 1
        it["input_name"] = copy_to_input(it["path"], f"{slug}_look{it['index']}.png")
    print("[参考图] " + ", ".join(f"{it['key']}->input/{it['input_name']}" for it in looks))

    # ---- 4. dry-run：逐块注入 + 校验，不提交 ----
    if args.dry_run:
        print("\n=== dry-run 逐块注入 + 逐节点校验（不会 POST /prompt）===")
        errors_all = []
        for it in looks:
            for i, (start, raw, length) in enumerate(chunks):
                wf = base.inject_placeholders(tpl, {
                    "reference_image": it["input_name"],
                    "driving_video": chunk_in_names[i],
                    "width": args.width, "height": args.height,
                    "length": length, "frame_offset": 0,
                    "seed": args.seed + it["index"] * 1000 + i,
                    "output": f"{date}/{project}/versions/{it['index']}_chunk{i}"})
                print(f"\n[look {it['key']} chunk{i}] length={length} "
                      f"frame_offset=0 seed={args.seed + it['index'] * 1000 + i}")
                errors, lines = validate_nodes(wf)
                for ln in lines:
                    print(ln)
                if errors:
                    errors_all.extend(f"[{it['key']}#{i}] {e}" for e in errors)
                    print(f"[look {it['key']} chunk{i}] 校验失败（{len(errors)} 项）:")
                    for e in errors:
                        print("  - " + e)
                else:
                    print(f"[look {it['key']} chunk{i}] 校验 OK（{len(wf)} 节点）")
        if errors_all:
            print(f"\n[失败] 校验发现 {len(errors_all)} 个问题（dry-run 结束，未提交）")
            for e in errors_all:
                print("  - " + e)
            return 1
        print(f"\n[通过] {len(looks)}×{len(chunks)} 块全部校验通过（dry-run 结束，未提交）")
        return 0

    # ---- 5. 提交前预检（单实例硬检查；内存仅告警不拦截）----
    print("\n=== 预检（提交前）===")
    for name, fn, soft in (("单实例", base.check_single_instance, False),
                           ("可用内存", lambda: base.check_memory(8.0), True)):
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"检查异常: {e}"
        tag = "通过" if ok else ("警告" if soft else "失败")
        print(f"  [{tag}] {name}: {msg}" + ("（仅告警，不拦截）" if (not ok and soft) else ""))
        if not ok and not soft:
            print("[失败] 预检未通过，终止（未提交）。")
            return 1

    # ---- 6. 逐 look 逐块提交/等待 ----
    n_fail = 0
    for it in looks:
        k = it["index"]
        for i, (start, raw, length) in enumerate(chunks):
            key = f"{k}_{i}"
            out_prefix = f"{date}/{project}/versions/{key}"
            t0 = time.time()

            # --resume：已完成且产物在 -> 跳过
            if args.resume and key in prog["completed"]:
                rec_out = (prog["chunks"].get(key) or {}).get("output")
                if rec_out and os.path.exists(rec_out):
                    print(f"[look {it['key']} chunk{i}] [resume 跳过] "
                          f"{os.path.basename(rec_out)}", flush=True)
                    it.setdefault("chunk_outputs", {})[i] = rec_out
                    continue

            wf = base.inject_placeholders(tpl, {
                "reference_image": it["input_name"],
                "driving_video": chunk_in_names[i],
                "width": args.width, "height": args.height,
                "length": length, "frame_offset": 0,
                "seed": args.seed + k * 1000 + i,
                "output": out_prefix})
            errors, _ = validate_nodes(wf)
            if errors:
                n_fail += 1
                print(f"[look {it['key']} chunk{i}] 校验失败（{len(errors)} 项），跳过:")
                for e in errors:
                    print("  - " + e)
                prog["chunks"][key] = {"look_index": k, "look_id": it["id"], "chunk": i,
                                       "pid": None, "status": "validate_failed",
                                       "seconds": None, "output": None,
                                       "length": length, "frame_offset": 0,
                                       "error": "; ".join(errors[:3])}
                save_progress(prog_file, prog)
                continue

            try:
                pid = submit(wf)
            except Exception as e:
                n_fail += 1
                print(f"[look {it['key']} chunk{i}] 提交异常: {e}")
                prog["chunks"][key] = {"look_index": k, "look_id": it["id"], "chunk": i,
                                       "pid": None, "status": "submit_failed",
                                       "seconds": None, "output": None,
                                       "length": length, "frame_offset": 0,
                                       "error": f"submit: {e}"}
                save_progress(prog_file, prog)
                continue

            print(f"[look {it['key']} chunk{i}] 已提交 pid={pid} "
                  f"（{args.width}x{args.height} length={length}）", flush=True)

            if args.no_wait:
                prog["chunks"][key] = {"look_index": k, "look_id": it["id"], "chunk": i,
                                       "pid": pid, "status": "submitted",
                                       "seconds": None, "output": None,
                                       "length": length, "frame_offset": 0}
                save_progress(prog_file, prog)
                continue

            rec = base.wait_done(pid)
            if not rec:
                n_fail += 1
                print(f"[look {it['key']} chunk{i}] 执行失败/超时（pid={pid}）")
                prog["chunks"][key] = {"look_index": k, "look_id": it["id"], "chunk": i,
                                       "pid": pid, "status": "failed",
                                       "seconds": round(time.time() - t0, 1),
                                       "output": None, "length": length,
                                       "frame_offset": 0, "error": "wait_done None"}
                save_progress(prog_file, prog)
                continue
            files = [p for p in base.find_output_files(rec)
                     if p.lower().endswith(".mp4") and os.path.exists(p)]
            if not files:
                n_fail += 1
                print(f"[look {it['key']} chunk{i}] 未定位到输出 MP4")
                prog["chunks"][key] = {"look_index": k, "look_id": it["id"], "chunk": i,
                                       "pid": pid, "status": "no_output",
                                       "seconds": round(time.time() - t0, 1),
                                       "output": None, "length": length,
                                       "frame_offset": 0}
                save_progress(prog_file, prog)
                continue
            mp4 = files[-1]
            secs = round(time.time() - t0, 1)
            print(f"[look {it['key']} chunk{i}] 完成 {os.path.basename(mp4)}  "
                  f"执行 {base.exec_seconds(rec.get('status', {})) or 0:.0f}s  本块 {secs}s",
                  flush=True)
            print(f"[look {it['key']} chunk{i}] 块验收（抽首/中/尾帧算亮度）:")
            okb = base.acceptance(mp4, length, FPS)
            status = "done" if okb is not False else "accept_failed"
            if okb is False:
                n_fail += 1
            prog["chunks"][key] = {"look_index": k, "look_id": it["id"], "chunk": i,
                                   "pid": pid, "status": status, "seconds": secs,
                                   "output": mp4, "length": length,
                                   "frame_offset": 0, "accepted": okb}
            if status == "done":
                if key not in prog["completed"]:
                    prog["completed"].append(key)
                it.setdefault("chunk_outputs", {})[i] = mp4
            else:
                it.setdefault("chunk_outputs", {})[i] = mp4   # 尽量仍拼接
            save_progress(prog_file, prog)

    # ---- 7. no-wait：不拼接 ----
    if args.no_wait:
        print(f"\n[提示] --no-wait：已提交（未等待、未拼接）。等待完成后可用同一命令"
              f"（去掉 --no-wait）或 --stage render 重跑以拼接/补帧。")
        report["no_wait"] = True
        return 0

    # ---- 8. 逐 look 拼接 + 音频重封装 + 整版本验收 ----
    print("\n=== 逐 look 拼接（块裁剪 + 硬切 + 帧数补齐到驱动帧数 + 驱动整段音频）===")
    print(f"[驱动] 16fps 规范化帧数 = {total}（整版本帧数验收目标 ±1）")
    report["driving_frames16"] = total
    for it in looks:
        k = it["index"]
        chunk_out = it.get("chunk_outputs") or {}
        idxs = sorted(chunk_out.keys())
        files = [chunk_out[i] for i in idxs if os.path.exists(chunk_out[i])]
        exps = [chunks[i][2] for i, p in zip(idxs, files)]
        if not files:
            print(f"[look {it['key']}] 无可拼接分块，跳过")
            n_fail += 1
            continue
        full16 = os.path.join(versions_dir, f"v{k}_full16.mp4")
        t0 = time.time()
        ok, err, cinfo = concat_full16(files, full16, driving_abs, exps, total)
        if not ok:
            print(f"[look {it['key']}] 拼接失败:\n" + err)
            n_fail += 1
            continue
        print(f"[look {it['key']}] 整版本: {full16}")
        v = verify_version(full16, driving_abs, args.width, args.height, total)
        v["seconds"] = round(time.time() - t0, 1)
        report["versions"].append({"id": it["id"], "index": k, "full16": full16,
                                   "concat": cinfo, "full16_verify": v})
        print(f"[look {it['key']}] 验收: 帧数={v.get('frames')}（驱动 {total}，±1）"
              f" 尺寸={v.get('size')}（期望 {[args.width, args.height]}）"
              f" 时长={v.get('duration')}s（驱动 {v.get('driving_duration')}s）"
              f" 音轨={v.get('has_audio')} 亮度={v.get('brightness_ok')} -> "
              f"{'通过' if v.get('ok') else '未通过'}")
        if not v.get("ok"):
            n_fail += 1
            print(f"[look {it['key']}] 验收未通过原因: " + "；".join(v.get("reasons") or []))

        # ---- 9. RIFE 补帧（可选）----
        if args.skip_enhance:
            print(f"[look {it['key']}] --skip-enhance：跳过补帧")
            continue
        out_w, out_h = (args.enhance_size if args.enhance_size else (args.width, args.height))
        prefix = f"{date}/{project}/versions/v{k}_%g" % int(args.enhance_target_fps)
        ok_e, _, _ = enhance_version(full16, prefix, [out_w, out_h],
                                     args.enhance_target_fps,
                                     os.path.join(out_dir, "enhance"))
        if not ok_e:
            n_fail += 1
            print(f"[look {it['key']}] 补帧失败（保留 full16）")
            continue
        cands = glob.glob(os.path.join(versions_dir, f"v{k}_%g_*.mp4" % int(args.enhance_target_fps)))
        cands += glob.glob(os.path.join(OUTPUT_ROOT, date, project, "versions",
                                        f"v{k}_%g_*.mp4" % int(args.enhance_target_fps)))
        if cands:
            e30 = max(cands, key=os.path.getmtime)
            print(f"[look {it['key']}] 补帧产物: {e30}")
            report["versions"][-1]["enhanced"] = e30
            report["versions"][-1]["enhanced_verify"] = {
                "size": [out_w, out_h], "target_fps": args.enhance_target_fps,
                "duration": round(seg.probe_duration(e30), 4),
                "has_audio": seg.has_audio(e30)}
        else:
            print(f"[warning] 补帧完成但未定位到产物（prefix={prefix}）")

    print(f"\n[render] 完成，失败块/版本数 = {n_fail}")
    return 0 if n_fail == 0 else 1


# =============================== compose 转发 ===============================

def compose_stage(args, date, project, slug, driving_abs, looks, report, versions):
    """懒加载转发 multilook_compose.run_compose（由 Task 3 提供）。返回 (rc, result)。"""
    try:
        from multilook_compose import run_compose
    except Exception as e:
        print(f"[失败] 未能加载合成器模块 multilook_compose（由 Task 3 提供）: {e}")
        print("       请先完成 Task 3（生成 tools/ootd_study/multilook_compose.py）后重试。")
        return 1, None
    out_dir = os.path.abspath(os.path.join(OUTPUT_ROOT, date, project))
    plate = None
    if getattr(args, "plate", None):
        plate = resolve_path(args.plate)
        if not os.path.exists(plate):
            print(f"[失败] --plate 指定的底板不存在: {plate}")
            return 1, None
        print(f"[plate] 使用外部底板: {plate}（合成器 cover 缩放到 1080x1920）")
    else:
        print("[plate] 未指定 --plate，由合成器按驱动逐像素中值自行合成底板"
              "（贴纸拼贴型驱动会被 5 个人物污染，建议改用 --plate）")
    cfg = {
        "project": project,
        "date": date,
        "slug": slug,
        "out_dir": out_dir,
        "out_path": os.path.join(
            out_dir, f"{project}_collage"
            + (("_" + args.out_tag) if getattr(args, "out_tag", None) else "") + ".mp4"),
        "driving": os.path.abspath(driving_abs),
        "versions": versions,
        "looks": [os.path.abspath(it["path"]) for it in looks],
        "plate": plate,
        "cuts": None,
        "bgm": None,
        "bgm_auto": bool(args.bgm_auto),
        "audio": "driving",
        "tile_defs": None,
        "main_def": None,
        "dash": None,
        "dash_main": bool(getattr(args, "dash_main", True)),
        "tiles_mode": ("ref" if getattr(args, "tiles_ref", False)
                       else ("off" if getattr(args, "tiles_off", False) else "video")),
        "frame_border": None,
        "matte_dir": os.path.join(out_dir, "matte"),
        "no_gpu": bool(args.no_gpu),
        "synth_alpha": bool(args.synth_alpha),
        "text": None,
        "size": [1080, 1920],
        "fps": 30,
    }
    print("\n=== compose 阶段（转发 multilook_compose.run_compose）===")
    print(f"  versions={[v['id'] for v in versions]}  out_dir={out_dir}")
    try:
        result = run_compose(cfg)
    except Exception as e:
        print(f"[失败] run_compose 异常: {e}")
        return 1, None
    print(f"[compose] 返回: {json.dumps(result, ensure_ascii=False)[:800]}")
    return 0, result


def collect_versions(date, project, looks):
    """按 look 收集已渲染版本（优先 30fps 补帧产物，否则 full16）-> [{id, video}]。"""
    versions_dir = os.path.join(OUTPUT_ROOT, date, project, "versions")
    out = []
    for it in looks:
        k = it["index"]
        cands = [p for p in glob.glob(os.path.join(versions_dir, f"v{k}_*.mp4"))
                 if "_full16" not in os.path.basename(p)]
        full16 = os.path.join(versions_dir, f"v{k}_full16.mp4")
        if cands:
            out.append({"id": it["id"], "video": max(cands, key=os.path.getmtime)})
        elif os.path.exists(full16):
            out.append({"id": it["id"], "video": full16})
    return out


# =============================== 报告 ===============================

def write_report(date, project, report):
    report["date"] = date
    report["project"] = project
    report["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path = os.path.join(OUTPUT_ROOT, date, project, "multilook_report.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[报告] {path}")
    return path


# =============================== main ===============================

def main():
    ap = argparse.ArgumentParser(description="OOTD 多版本同步渲染引擎（Wan2.2 Animate 9:16）")
    ap.add_argument("--stage", choices=["render", "compose", "all"], default="all")
    ap.add_argument("--driving", default=DEFAULT_DRIVING, help="驱动视频（input 下相对名或绝对路径）")
    ap.add_argument("--looks", default=None, help="换装参考图清单 JSON（字符串数组或对象数组）")
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--date", default=None, help="归档日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--height", type=int, default=832)
    ap.add_argument("--chunk-len", type=int, default=49, help="分块帧数（4k+1，默认 49）")
    ap.add_argument("--max-chunks", type=int, default=0, help="只处理前 N 块（0=全部；冒烟/PoC 用）")
    ap.add_argument("--seed", type=int, default=20261002)
    ap.add_argument("--mask-corners", default="auto",
                    help="驱动角落遮罩（消除 DWPose 对贴纸拼贴驱动四角小人的误检测）："
                         "auto（默认，读 ref_analysis/structure.json 映射，无匹配用内置 v8 默认 rect）"
                         "| off | \"x,y,w,h;x,y,w,h;...\"（1080x1920 坐标）")
    ap.add_argument("--resume", action="store_true", help="按 render_progress.json 跳过已完成块")
    ap.add_argument("--plate", default=None,
                    help="合成底板 PNG（空房间无人物；合成器 cover 缩放到 1080x1920）。"
                         "不传则由合成器按驱动中值自行合成（贴纸拼贴型驱动会残留四角鬼影）")
    ap.add_argument("--no-wait", action="store_true", help="只提交不等待、不拼接")
    ap.add_argument("--dry-run", action="store_true", help="只文件检查+逐块校验+打印块计划，不提交")
    ap.add_argument("--skip-enhance", action="store_true", help="跳过 RIFE 补帧")
    ap.add_argument("--enhance-target-fps", type=float, default=30.0)
    ap.add_argument("--enhance-size", default=None,
                    help="补帧输出尺寸 WxH（默认与源一致），如 480x832")
    # compose 转发参数
    ap.add_argument("--bgm-auto", dest="bgm_auto", action="store_true", default=True)
    ap.add_argument("--no-bgm-auto", dest="bgm_auto", action="store_false")
    ap.add_argument("--no-gpu", action="store_true", help="合成阶段禁用 GPU（转发 compose）")
    ap.add_argument("--tiles-off", action="store_true",
                    help="合成阶段不显示四角对比小窗（仅主画面轮换）")
    ap.add_argument("--tiles-ref", action="store_true",
                    help="合成阶段角标改为静态参考图卡片（队列轮转，不抠像）")
    ap.add_argument("--out-tag", default=None,
                    help="输出文件名后缀（预览用，如 ref_tiles -> *_collage_ref_tiles.mp4）")
    ap.add_argument("--no-main-dash", dest="dash_main", action="store_false", default=True,
                    help="合成阶段主画面人物不描虚线（角标虚线保留）")
    ap.add_argument("--synth-alpha", action="store_true", help="合成阶段用合成 alpha（仅调试）")
    ap.add_argument("--workflow", default=WORKFLOW)
    args = ap.parse_args()

    if args.enhance_size:
        try:
            w, h = args.enhance_size.lower().split("x")
            args.enhance_size = [int(w), int(h)]
        except Exception:
            print(f"[失败] --enhance-size 格式应为 WxH，收到 {args.enhance_size!r}")
            return 1

    date = args.date or _date.today().isoformat()
    project = args.project
    slug = pipe._ascii_slug(project)
    driving_abs = resolve_driving(args.driving)

    print(f"[配置] project={project}（slug={slug}） date={date} stage={args.stage} "
          f"size={args.width}x{args.height} chunk-len={args.chunk_len} seed={args.seed} "
          f"skip-enhance={args.skip_enhance} mask-corners={args.mask_corners} "
          f"plate={args.plate}")

    looks = []
    if args.stage in ("render", "all", "compose"):
        if not args.looks:
            print("[失败] 需要 --looks <json>（换装参考图清单）")
            return 1
        try:
            looks = read_looks(args.looks)
        except ValueError as e:
            print(f"[失败] {e}")
            return 1
        print(f"[looks] {len(looks)} 套: "
              + ", ".join(f"{it['key']}={os.path.basename(it['path'])}" for it in looks))

    if os.path.exists(driving_abs):
        print(f"[驱动] {driving_abs}  时长={seg.probe_duration(driving_abs):.3f}s "
              f"帧率={seg.probe_fps(driving_abs)} 含音轨={seg.has_audio(driving_abs)}")
    else:
        print(f"[失败] 驱动视频不存在: {driving_abs}")
        return 1

    report = {
        "driving": driving_abs, "project": project, "date": date,
        "looks": [{"id": it["id"], "path": it["path"]} for it in looks],
        "params": {"width": args.width, "height": args.height,
                   "chunk_len": args.chunk_len, "max_chunks": args.max_chunks,
                   "seed": args.seed, "fps": FPS,
                   "mask_corners": args.mask_corners,
                   "plate": args.plate,
                   "skip_enhance": args.skip_enhance,
                   "enhance_target_fps": args.enhance_target_fps,
                   "enhance_size": args.enhance_size,
                   "workflow": os.path.basename(args.workflow)},
        "versions": [], "compose": None,
    }
    t_all = time.time()

    rc_render = 0
    compose_result = None

    if args.stage in ("render", "all"):
        rc_render = render_stage(args, date, project, slug, driving_abs, looks, report)
        if args.dry_run:
            report["seconds"] = round(time.time() - t_all, 1)
            write_report(date, project, report)
            return rc_render
    if args.stage in ("compose", "all"):
        if args.stage == "all" and rc_render != 0:
            print("[提示] render 阶段有失败，仍尝试 compose（保留现场）")
        rc_compose = 0
        versions = collect_versions(date, project, looks)
        if not versions:
            print("[失败] 未发现可合成的版本（先跑 --stage render）")
            rc_compose = 1
        else:
            rc_compose, compose_result = compose_stage(args, date, project, slug, driving_abs,
                                                       looks, report, versions)
            report["compose"] = compose_result
        report["seconds"] = round(time.time() - t_all, 1)
        write_report(date, project, report)
        if args.stage == "compose":
            return rc_compose
        return rc_render if rc_render != 0 else rc_compose

    report["seconds"] = round(time.time() - t_all, 1)
    write_report(date, project, report)
    return rc_render


if __name__ == "__main__":
    sys.exit(main())