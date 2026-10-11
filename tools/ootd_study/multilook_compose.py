#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「贴纸多版本」合成器：多版本同步视频 -> 主画面 + 角标对比成片。

接口（供 Task 2 的 ootd_multilook.py 复用，严格保持签名/返回键）:
    from multilook_compose import run_compose
    result = run_compose(cfg: dict) -> dict

cfg 键（全部 dict 接入）:
    project, date, slug, out_dir(绝对), out_path, driving(绝对 mp4),
    versions=[{"id","video","shift"?}(绝对)], looks=[png 绝对](仅记录),
    cuts(秒数组或 None -> 每 3.0s), bgm(None), bgm_auto(bool),
    audio("driving"|路径|None), tile_defs(可 None), main_def(可 None),
    dash(可 None), frame_border(可 None),
    matte_dir(绝对; alpha 序列查找 <matte_dir>/<id>/00001.png),
    no_gpu(bool), synth_alpha(bool 调试), text(None),
    size=[1080,1920], fps=30, dry_run(bool, 可选)

返回:
    {"out_path","layout_timeline":[{t0,t1,main,slots}],"cuts","plate",
     "matte":{id:dir},"acceptance":{...},"elapsed_s"}

样式对齐参考 output/2026-10-02/ref_analysis/full_v1_1s.jpg：
人物贴纸白色虚线描边（marching ants）、圆角角标小窗（同一房间底板 +
该 look 抠像人物）、卡点硬切轮换主画面。

复用（不修改）：tools/ootd_study/ootd_outfit_swap.py 的
merge_with_transition / auto_select_bgm / analyze_track / mix_bgm /
probe_audio_codec；tools/h3_fast_submit.py 的 inject_placeholders /
validate_workflow / wait_done / find_output_files；tools/h3_fast_segmented.py
的 ffprobe 封装。

仅新建本文件 + workflows/v5/birefnet_matte_video_api.json。
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

import cv2
import numpy as np

# --- sys.path: 同时含 tools/ 与 tools/ootd_study/ ---
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.dirname(_THIS_DIR)
for _p in (_TOOLS_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import h3_fast_submit as base            # noqa: E402
import h3_fast_segmented as seg          # noqa: E402
import ootd_outfit_swap as swap          # noqa: E402  (只读复用 BGM/卡点函数)

ROOT = base.ROOT
INPUT_ROOT = base.INPUT_ROOT
OUTPUT_ROOT = base.OUTPUT_ROOT
MATTE_WORKFLOW = os.path.join(_THIS_DIR, "workflows", "v5",
                              "birefnet_matte_video_api.json")
BGM_DIR = swap.BGM_DIR
FFMPEG_ABS = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"

# ---------------- 样式兜底默认值（structure.json 存在时优先覆盖） ----------------
DEFAULT_TILES = [
    {"x": 30, "y": 60, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
    {"x": 750, "y": 60, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
    {"x": 30, "y": 1300, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
    {"x": 750, "y": 1300, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
]
DEFAULT_DASH = {"width": 6, "dash": 18, "gap": 12, "speed": 6.0,
                "animate": True, "color": [255, 255, 255]}
DEFAULT_BORDER = {"width": 5, "color": [255, 255, 255], "radius": 48}
DEFAULT_SIZE = [1080, 1920]
DEFAULT_FPS = 30
DEFAULT_CUT_INTERVAL = 3.0


# =============================== 通用小工具 ===============================

def _log(msg):
    print(msg, flush=True)


def _resolve(path):
    if not path:
        return path
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(ROOT, path))


def _resize(img, w, h):
    interp = cv2.INTER_AREA if (img.shape[1] > w or img.shape[0] > h) else cv2.INTER_LINEAR
    return cv2.resize(img, (int(w), int(h)), interpolation=interp)


def _resize_cover(img, w, h):
    """等比缩放到覆盖 (w,h) 后居中裁剪（保持比例、无拉伸）。"""
    fh, fw = img.shape[:2]
    s = max(w / float(fw), h / float(fh))
    nw, nh = int(round(fw * s)), int(round(fh * s))
    r = cv2.resize(img, (nw, nh),
                   interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return r[y0:y0 + h, x0:x0 + w]


def _ffmpeg():
    if os.path.exists(FFMPEG_ABS):
        return FFMPEG_ABS
    return base.resolve_ffmpeg()


def probe_video(path):
    """返回 dict(w,h,n,fps,dur,has_audio)。"""
    import cv2
    cap = cv2.VideoCapture(path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    cap.release()
    if not fps or fps <= 0:
        fps = seg.probe_fps(path)
    if not n:
        n = seg.probe_nb_frames(path)
    dur = seg.probe_duration(path)
    return {"w": w, "h": h, "n": n, "fps": float(fps), "dur": float(dur),
            "has_audio": seg.has_audio(path)}


class SeqReader:
    """单调递增帧访问器（避免把整段视频读进内存）。"""

    def __init__(self, path):
        import cv2
        self.cap = cv2.VideoCapture(path)
        self.pos = -1
        self.last = None

    def get(self, idx):
        import cv2
        if idx < 0:
            idx = 0
        if self.pos > idx:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            self.pos = int(idx) - 1
        while self.pos < idx:
            ok, fr = self.cap.read()
            if not ok or fr is None:
                break
            self.pos += 1
            self.last = fr
        if self.last is None:
            ok, fr = self.cap.read()
            if ok and fr is not None:
                self.pos = 0
                self.last = fr
        return self.last

    def release(self):
        try:
            self.cap.release()
        except Exception:
            pass


class MatteReader:
    """读取 <matte_dir>/<id>/00001.png 形式的 alpha 序列（随机访问，单张缓存）。"""

    def __init__(self, matte_dir, vid):
        self.dir = os.path.join(matte_dir, vid)
        self.files = sorted(glob.glob(os.path.join(self.dir, "*.png")))
        self._cache = (None, None)

    def __len__(self):
        return len(self.files)

    def get(self, idx):
        idx = max(0, min(idx, len(self.files) - 1)) if self.files else 0
        if not self.files:
            return None
        if self._cache[0] == idx:
            return self._cache[1]
        m = cv2.imread(self.files[idx], cv2.IMREAD_GRAYSCALE)
        if m is None:
            m = np.zeros((1, 1), np.uint8)
        self._cache = (idx, m)
        return m


# =============================== 样式读取 ===============================

def load_structure(date):
    """读取并行任务产出的 ref_analysis/structure.json（不存在则 {}）。"""
    if not date:
        return {}
    p = os.path.join(OUTPUT_ROOT, date, "ref_analysis", "structure.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                return json.load(f) or {}
        except Exception as e:
            _log(f"[警告] structure.json 解析失败，改用兜底样式: {e}")
    return {}


def _norm_tile(t):
    d = {"x": 40, "y": 40, "w": 340, "h": 600, "offset": 0.0}
    if isinstance(t, (list, tuple)) and len(t) >= 4:
        d.update({"x": int(t[0]), "y": int(t[1]), "w": int(t[2]), "h": int(t[3])})
        if len(t) >= 5:
            d["offset"] = float(t[4])
    elif isinstance(t, dict):
        d.update({k: t[k] for k in t if k in d})
        # border/radius 仅在显式给出时保留（否则跟随全局 frame_border）
        if "border" in t:
            d["border"] = t["border"]
        if "radius" in t:
            d["radius"] = t["radius"]
    return d


def _tiles_from_structure(structure):
    """从 structure.json 的 tile_geometry.per_frame 提取角标槽位（实测 [x,y,w,h]）。"""
    tg = structure.get("tile_geometry") or {}
    per = tg.get("per_frame") or {}
    tiles = None
    for ref in ("v1", "v4", "v8"):
        if isinstance(per.get(ref), dict) and per[ref].get("tiles"):
            tiles = per[ref]["tiles"]
            break
    if tiles is None and per:
        first = next(iter(per.values()))
        tiles = (first or {}).get("tiles")
    if not tiles:
        return None
    order = {"top_left": 0, "top_right": 1, "bottom_left": 2, "bottom_right": 3}
    tiles = sorted(tiles, key=lambda t: order.get(t.get("slot"), 9))
    out = []
    for j, t in enumerate(tiles):
        r = t.get("rect")
        if not r or len(r) < 4:
            continue
        out.append({"x": int(r[0]), "y": int(r[1]), "w": int(r[2]),
                    "h": int(r[3]), "offset": round(0.5 * (j + 1), 3)})
    return out or None


def resolve_style(cfg, structure):
    """合并兜底默认 -> structure.json -> cfg 三级配置。"""
    tiles = None
    st_tiles = _tiles_from_structure(structure)
    if st_tiles:
        tiles = st_tiles
    if tiles is None:
        for key in ("tile_defs", "corner_slots", "tiles", "slot_defs"):
            if isinstance(structure.get(key), list) and structure[key]:
                tiles = structure[key]
                break
    if tiles is None:
        tiles = DEFAULT_TILES
    tile_defs = [_norm_tile(t) for t in tiles]

    dash = dict(DEFAULT_DASH)
    if isinstance(structure.get("dash"), dict):
        dash.update(structure["dash"])
    ol = structure.get("outline") or {}
    if ol.get("line_width_px"):
        dash["width"] = int(round(ol["line_width_px"]))
    if ol.get("dash_len_px"):
        dash["dash"] = float(ol["dash_len_px"])
    if ol.get("gap_px"):
        dash["gap"] = float(ol["gap_px"])
    if isinstance(cfg.get("dash"), dict):
        dash.update(cfg["dash"])

    border = dict(DEFAULT_BORDER)
    tg = structure.get("tile_geometry") or {}
    if "white_rect_border_px" in tg:
        border["width"] = int(tg["white_rect_border_px"])   # 参考实测 0（无实线边框）
    if isinstance(tg.get("rounded_corner_radius_px"), dict) and \
            tg["rounded_corner_radius_px"].get("measured_estimate") is not None:
        border["radius"] = int(tg["rounded_corner_radius_px"]["measured_estimate"])
    if isinstance(structure.get("frame_border"), dict):
        border.update(structure["frame_border"])
    if isinstance(cfg.get("frame_border"), dict):
        border.update(cfg["frame_border"])

    if isinstance(cfg.get("tile_defs"), list) and cfg["tile_defs"]:
        tile_defs = [_norm_tile(t) for t in cfg["tile_defs"]]

    # 每个角标可用自身 border/radius 覆盖
    for t in tile_defs:
        if "border" in t:
            t["_border"] = t["border"]
        if "radius" in t:
            t["_radius"] = t["radius"]

    size = cfg.get("size") or structure.get("size") or DEFAULT_SIZE
    vids = structure.get("videos") or []
    if not cfg.get("size") and vids and vids[0].get("size"):
        size = vids[0]["size"]
    size = [int(size[0]), int(size[1])]
    fps = int(cfg.get("fps") or structure.get("fps")
              or (vids[0].get("fps") if vids else 0) or DEFAULT_FPS)

    interval = DEFAULT_CUT_INTERVAL
    cad = structure.get("cadence") or {}
    if cad.get("mean_s"):
        interval = float(cad["mean_s"])
    return {"tiles": tile_defs, "dash": dash, "border": border,
            "dash_main": bool(cfg.get("dash_main", True)),
            "size": size, "fps": fps, "cut_interval": interval,
            "structure_keys": list(structure.keys())}


# =============================== 底板 ===============================

def extract_plate(driving, out_dir, size, sample_every=3, scale=0.5, cap=60):
    """对 driving 抽帧逐像素中值合成底板 -> out_dir/plate.png。"""
    import cv2
    import numpy as np
    out_png = os.path.join(out_dir, "plate.png")
    capr = cv2.VideoCapture(driving)
    frames = []
    i = 0
    while len(frames) < cap:
        ok, fr = capr.read()
        if not ok or fr is None:
            break
        if i % sample_every == 0:
            frames.append(_resize(fr, max(1, int(fr.shape[1] * scale)),
                                  max(1, int(fr.shape[0] * scale))))
        i += 1
    capr.release()
    if not frames:
        raise RuntimeError(f"底板抽取失败：无法解码 {driving}")
    stack = np.stack(frames, axis=0).astype(np.float32)
    med = np.median(stack, axis=0).astype(np.uint8)
    plate = _resize_cover(med, size[0], size[1])
    os.makedirs(out_dir, exist_ok=True)
    cv2.imwrite(out_png, plate)

    # 自检：中心区 vs 边缘 亮度/纹理差异（疑似残留人物）
    g = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H, W = g.shape
    cen = g[int(0.30 * H):int(0.70 * H), int(0.30 * W):int(0.70 * W)]
    edge = np.concatenate([
        g[:int(0.15 * H), :].ravel(), g[int(0.85 * H):, :].ravel(),
        g[:, :int(0.15 * W)].ravel(), g[:, int(0.85 * W):].ravel()])
    cen_l, edge_l = float(cen.mean()), float(edge.mean())

    def tex(a):
        lap = (-4.0 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1]
               + a[1:-1, :-2] + a[1:-1, 2:])
        return float(lap.var())

    cen_t = tex(cen)
    edge_t = tex(g) 
    lum_diff = abs(cen_l - edge_l)
    warn = bool(lum_diff > 25.0)
    metrics = {"center_lum": round(cen_l, 2), "edge_lum": round(edge_l, 2),
               "lum_diff": round(lum_diff, 2), "center_tex": round(cen_t, 2),
               "edge_tex": round(edge_t, 2), "sampled_frames": len(frames),
               "threshold": 25.0}
    if warn:
        _log(f"[警告] plate_warn：底板中心/边缘亮度差 {lum_diff:.1f}（>{25.0}），"
             f"疑似残留人物，仍继续（中值合成）。")
    return out_png, warn, metrics


# =============================== 抠像（SubTask 3.1） ===============================

def _matte_complete(mat_dir, n_frames):
    files = sorted(glob.glob(os.path.join(mat_dir, "*.png")))
    return len(files) == n_frames and n_frames > 0


def synth_alpha_from_video(video, out_dir, n_frames, threshold=18.0):
    """调试兜底：cv2 背景差分生成软 mask 序列（写 <out_dir>/%05d.png）。"""
    import cv2
    import numpy as np
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok or fr is None:
            break
        frames.append(fr)
    cap.release()
    if not frames:
        raise RuntimeError(f"bgsub 失败：无法解码 {video}")
    sample = frames[::max(1, len(frames) // 30)][:30]
    bg = np.median(np.stack(sample, axis=0).astype(np.float32), axis=0)
    k = np.ones((7, 7), np.uint8)
    written = 0
    for i in range(min(n_frames, len(frames))):
        # 黑帧/fade 帧无有效前景：直接输出空 mask，避免整帧被误判为前景
        if float(frames[i].mean()) < 15.0:
            cv2.imwrite(os.path.join(out_dir, "%05d.png" % (i + 1)),
                        np.zeros(frames[i].shape[:2], np.uint8))
            written += 1
            continue
        diff = np.abs(frames[i].astype(np.float32) - bg).mean(axis=2)
        m = np.clip((diff - threshold) / 60.0 * 255.0, 0, 255).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        m = cv2.GaussianBlur(m, (0, 0), 4.0)
        cv2.imwrite(os.path.join(out_dir, "%05d.png" % (i + 1)), m)
        written += 1
    return written


def _load_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _matte_chunk_present(d, g0, count):
    """该段全局帧 [g0, g0+count-1] 的 PNG 是否已全部存在（断点续跑判定）。"""
    for i in range(count):
        if not os.path.exists(os.path.join(d, "%06d.png" % (g0 + i))):
            return False
    return True


def extract_frame_chunk(src, start_frame, count, out_mp4):
    """用 ffmpeg select 精确切出源视频的 [start_frame, start_frame+count-1] 帧段。

    分块抠像是为了规避 BiRefNet 对整批 421 帧一次性 interpolate 到 1024 的 OOM。
    """
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("未找到 ffmpeg，无法切分 matte 分块")
    end = start_frame + count - 1
    vf = "select='between(n\\,%d\\,%d)'" % (start_frame, end)
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-i", src, "-vf", vf, "-fps_mode", "passthrough", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "12",
           "-pix_fmt", "yuv420p", out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_mp4):
        raise RuntimeError("matte 切片失败（帧 %d..%d）: %s"
                           % (start_frame, end, (r.stderr or "")[-300:]))
    real = seg.probe_nb_frames(out_mp4)
    if int(real) != int(count):
        raise RuntimeError("matte 切片帧数 %s != 期望 %d（帧 %d..%d）"
                           % (real, count, start_frame, end))
    return out_mp4


def submit_matte_workflow(video, out_prefix, date, width=None, height=None):
    """提交 BiRefNet 逐帧抠像（LoadVideo->GetVideoComponents->ImageScale
    ->RemoveBackground->MaskToImage->SaveImage），等待并归档 alpha 序列。

    width/height：降分辨率后的抠像输入尺寸（ImageScale/lanczos），用于降低显存峰值。
    返回 (files, pid, secs)。提交前拷入 input，完成后清理临时输入。
    """
    os.makedirs(INPUT_ROOT, exist_ok=True)
    in_name = "multilook_matte_%s.mp4" % uuid.uuid4().hex[:8]
    in_path = os.path.join(INPUT_ROOT, in_name)
    shutil.copy2(video, in_path)
    base._INFO_CACHE.pop("LoadVideo", None)
    try:
        with open(MATTE_WORKFLOW, "r", encoding="utf-8") as f:
            tpl = json.load(f)
        vals = {"video": in_name, "output": out_prefix}
        if width:
            vals["width"] = int(width)
        if height:
            vals["height"] = int(height)
        wf = base.inject_placeholders(tpl, vals)
        errors, lines = base.validate_workflow(wf)
        for ln in lines:
            _log(ln)
        if errors:
            raise RuntimeError("抠像工作流校验失败: " + "; ".join(errors[:5]))
        _log(f"[matte] 提交抠像: video={in_name} "
             f"size={vals.get('width')}x{vals.get('height')} prefix={out_prefix}")
        r = base._post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        if r.get("node_errors"):
            raise RuntimeError("node_errors: "
                               + json.dumps(r["node_errors"], ensure_ascii=False)[:800])
        pid = r.get("prompt_id")
        t0 = time.time()
        rec = base.wait_done(pid)
        if not rec:
            raise RuntimeError(f"抠像执行失败/超时 pid={pid}")
        files = [p for p in base.find_output_files(rec) if p.lower().endswith(".png")]
        files = sorted(set(files), key=lambda p: os.path.basename(p))
        return files, pid, round(time.time() - t0, 1)
    finally:
        if os.path.exists(in_path):
            try:
                os.remove(in_path)
            except Exception:
                pass


def ensure_mattes(cfg, versions, style):
    """确保每个版本有完整 alpha 序列；返回 ({id: dir}, notes)。

    顺序：
    - 序列已完整（PNG 数 == 视频帧数）-> 复用；
    - no_gpu=True 且 synth_alpha=True -> cv2 背景差分兜底（开发期占位）；
    - no_gpu=True 且 synth_alpha=False -> 报错；
    - 否则 **分块 + 降分辨率** 走 birefnet_matte_video_api.json 提交等待并归档。

    分块（cfg.matte_chunk，默认 32）规避 BiRefNet 整批 interpolate 到 1024 的 OOM；
    降分辨率（cfg.matte_scale，默认 0.5）进一步降低显存峰值。
    每段失败重试 1 次；已完成段按 `matte_progress.json` + 已存在 PNG 跳过（断点续跑）。
    """
    matte_dir = _resolve(cfg.get("matte_dir")) or os.path.join(
        cfg["out_dir"], "matte")
    os.makedirs(matte_dir, exist_ok=True)
    date = cfg.get("date") or time.strftime("%Y-%m-%d")
    project = cfg.get("project") or "ootd_multilook"
    no_gpu = bool(cfg.get("no_gpu"))
    synth = bool(cfg.get("synth_alpha"))
    try:
        chunk = max(1, int(cfg.get("matte_chunk") or 32))
    except Exception:
        chunk = 32
    try:
        scale = float(cfg.get("matte_scale") if cfg.get("matte_scale") else 0.5)
    except Exception:
        scale = 0.5
    if scale <= 0:
        scale = 1.0

    prog_path = os.path.join(matte_dir, "matte_progress.json")
    prog = _load_json(prog_path, {}) or {}
    prog.update({"chunk": chunk, "scale": scale, "date": date,
                 "project": project,
                 "updated": time.strftime("%Y-%m-%dT%H:%M:%S")})
    prog.setdefault("videos", {})
    matte_map, notes = {}, {}

    for v in versions:
        vid = v["id"]
        d = os.path.join(matte_dir, vid)
        n = int(v["n"])
        sw = max(1, int(round(v["w"] * scale)))
        sh = max(1, int(round(v["h"] * scale)))
        vprog = prog["videos"].setdefault(
            vid, {"n": n, "src": v["video"], "scale": [sw, sh], "chunks": []})
        vprog.update({"n": n, "src": v["video"], "scale": [sw, sh]})

        # ---- 复用：序列已完整 ----
        if _matte_complete(d, n):
            have = len(glob.glob(os.path.join(d, "*.png")))
            matte_map[vid] = d
            vprog["status"] = "reuse"
            vprog["total_frames"] = have
            notes[vid] = {"mode": "reuse", "frames": have, "dir": d,
                          "chunk": chunk, "scale": scale, "input_size": [sw, sh]}
            _log(f"[matte][{vid}] 复用完整 alpha 序列（{n} 帧）: {d}")
            continue

        # ---- 无 GPU 兜底 ----
        if no_gpu:
            if not synth:
                raise RuntimeError(
                    f"[matte][{vid}] 缺 alpha 且 no_gpu=True/synth_alpha=False -> 报错")
            w = synth_alpha_from_video(v["video"], d, n)
            matte_map[vid] = d
            vprog["status"] = "bgsub"
            vprog["total_frames"] = w
            notes[vid] = {"mode": "bgsub(debug)", "frames": w, "dir": d,
                          "chunk": chunk, "scale": scale,
                          "note": "cv2 背景差分软 mask，仅供开发期占位"}
            _log(f"[matte][{vid}] bgsub 兜底生成 alpha {w} 帧 -> {d}")
            continue

        # ---- BiRefNet 分块 + 降分辨率 ----
        os.makedirs(d, exist_ok=True)
        n_chunks = (n + chunk - 1) // chunk
        done_idx = {int(c["index"]) for c in (vprog.get("chunks") or [])
                    if c.get("status") == "done"}
        _log(f"[matte][{vid}] 分块抠像 {n} 帧 = {n_chunks} 段 × {chunk} 帧，"
             f"抠像输入 {sw}x{sh}（scale={scale}）")
        for c in range(n_chunks):
            g0 = c * chunk + 1
            cnt = min(chunk, n - c * chunk)
            if c in done_idx and _matte_chunk_present(d, g0, cnt):
                _log(f"[matte][{vid}] chunk {c + 1}/{n_chunks} 已存在，跳过")
                continue
            cstart = c * chunk
            chunk_mp4 = os.path.join(matte_dir, "_tmp_%s_c%03d.mp4" % (vid, c))
            last_err = None
            for attempt in (1, 2):
                try:
                    extract_frame_chunk(v["video"], cstart, cnt, chunk_mp4)
                    prefix = f"{date}/{project}/matte_src/{vid}_c{c:03d}"
                    files, pid, secs = submit_matte_workflow(
                        chunk_mp4, prefix, date, sw, sh)
                    if len(files) < cnt:
                        raise RuntimeError(f"抠像帧数 {len(files)} < {cnt}")
                    for i in range(cnt):
                        shutil.copy2(files[i],
                                     os.path.join(d, "%06d.png" % (g0 + i)))
                    rec = {"index": c, "start": g0, "count": cnt, "pid": pid,
                           "seconds": secs, "attempt": attempt,
                           "status": "done", "files": cnt}
                    vprog["chunks"] = [x for x in (vprog.get("chunks") or [])
                                       if x.get("index") != c]
                    vprog["chunks"].append(rec)
                    vprog["chunks"].sort(key=lambda x: x.get("index", 0))
                    vprog["status"] = "running"
                    _save_json(prog_path, prog)
                    _log(f"[matte][{vid}] chunk {c + 1}/{n_chunks} 完成 "
                         f"帧 {g0}..{g0 + cnt - 1}（pid={pid}, {secs}s, "
                         f"第{attempt}次）")
                    last_err = None
                    break
                except Exception as e:
                    last_err = str(e)
                    _log(f"[警告][matte][{vid}] chunk {c + 1} 第{attempt}次失败: "
                         f"{last_err}")
                    for i in range(cnt):
                        p = os.path.join(d, "%06d.png" % (g0 + i))
                        if os.path.exists(p):
                            try:
                                os.remove(p)
                            except Exception:
                                pass
                finally:
                    if os.path.exists(chunk_mp4):
                        try:
                            os.remove(chunk_mp4)
                        except Exception:
                            pass
            if last_err is not None:
                vprog["status"] = "error"
                _save_json(prog_path, prog)
                raise RuntimeError(
                    f"[matte][{vid}] chunk {c + 1}/{n_chunks} 重试后仍失败: "
                    f"{last_err}")

        have = len(glob.glob(os.path.join(d, "*.png")))
        if have != n:
            vprog["status"] = "error"
            vprog["total_frames"] = have
            _save_json(prog_path, prog)
            raise RuntimeError(f"[matte][{vid}] 总帧数 {have} != 视频帧数 {n}")
        matte_map[vid] = d
        vprog["status"] = "done"
        vprog["total_frames"] = have
        _save_json(prog_path, prog)
        notes[vid] = {"mode": "birefnet_chunked", "frames": have, "dir": d,
                      "chunk": chunk, "scale": scale, "input_size": [sw, sh],
                      "n_chunks": n_chunks,
                      "chunks": [{k: x.get(k) for k in
                                  ("index", "start", "count", "pid",
                                   "seconds", "attempt")}
                                 for x in vprog["chunks"]]}
        _log(f"[matte][{vid}] BiRefNet 分块完成 {have} 帧 "
             f"（{n_chunks} 段, chunk={chunk}, scale={scale}）")

    _save_json(prog_path, prog)
    return matte_map, notes


# =============================== 虚线描边（SubTask 3.2） ===============================

def keep_largest_component(alpha, dilate_px=4, min_keep_area_ratio=0.01):
    """只保留 alpha 中面积最大的连通域（过滤畸变小人物/碎片）。

    - 先对二值 alpha 轻度膨胀（连接因阈值断裂的四肢/缝隙），在膨胀图上做连通域标注，
      取面积最大者；
    - 最大域面积 < min_keep_area_ratio × 全图面积 -> 视为无人物，返回全 0；
    - 返回过滤后的**原始** alpha（膨胀仅用于判定，边缘取自原 alpha，不改变人物形态）。
    """
    if alpha is None:
        return None
    h, w = alpha.shape[:2]
    binary = (alpha > 127).astype(np.uint8)
    if int(binary.sum()) == 0:
        return np.zeros_like(alpha)
    k = max(1, int(dilate_px))
    dil = cv2.dilate(binary, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(dil, 8)
    if num <= 1:
        return np.zeros_like(alpha)
    best, best_area = -1, 0
    for lab in range(1, num):
        a = int(stats[lab, cv2.CC_STAT_AREA])
        if a > best_area:
            best_area, best = a, lab
    if best < 0 or best_area < min_keep_area_ratio * h * w:
        return np.zeros_like(alpha)
    keep = ((labels == best) & (binary > 0)).astype(np.uint8) * 255
    return keep.astype(np.uint8)


def draw_dashed_outline(img, mask_u8, dash, gap, thickness, phase,
                        offset=(0, 0), color=(255, 255, 255), dilate=2):
    """沿 mask 外轮廓绘制白色虚线（marching ants），in-place。返回线段数。"""
    import cv2
    import numpy as np
    if thickness <= 0 or dash <= 0 or gap <= 0 or mask_u8 is None:
        return 0
    m = mask_u8
    if dilate > 0:
        m = cv2.dilate(m, np.ones((dilate * 2 + 1, dilate * 2 + 1), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return 0
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
    total = float(dash + gap)
    ox, oy = offset
    drawn = 0
    for c in cnts[:2]:
        if cv2.contourArea(c) < 30:
            continue
        pts = c.reshape(-1, 2)
        if len(pts) < 8:
            continue
        pts = np.vstack([pts, pts[:1]]).astype(np.float32)
        d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(d)])
        cond = ((cum[:-1] + phase) % total) < dash
        idx = np.nonzero(cond)[0]
        if idx.size == 0:
            continue
        # 合并连续点为折线，减少调用次数
        breaks = np.nonzero(np.diff(idx) > 1)[0]
        starts = np.concatenate([[0], breaks + 1])
        ends = np.concatenate([breaks, [idx.size - 1]])
        for s, e in zip(starts, ends):
            seg = pts[idx[s]:idx[e] + 2].astype(np.int32)
            seg = seg + np.array([ox, oy], np.int32)
            if len(seg) >= 2:
                cv2.polylines(img, [seg.reshape(-1, 1, 2)], False, color,
                              thickness, cv2.LINE_AA)
                drawn += 1
    return drawn


def _rounded_rect_border(img, x, y, w, h, radius, color, thickness):
    import cv2
    if thickness <= 0:
        return
    r = max(0, min(radius, min(w, h) // 2))
    cv2.line(img, (x + r, y), (x + w - r, y), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x + r, y + h - 1), (x + w - r, y + h - 1), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x, y + r), (x, y + h - r), color, thickness, cv2.LINE_AA)
    cv2.line(img, (x + w - 1, y + r), (x + w - 1, y + h - r), color, thickness, cv2.LINE_AA)
    for cx, cy, a0 in ((x + r, y + r, 180), (x + w - r, y + r, 270),
                       (x + w - r, y + h - r, 0), (x + r, y + h - r, 90)):
        cv2.ellipse(img, (cx, cy), (r, r), 0, a0, a0 + 90, color, thickness, cv2.LINE_AA)


# =============================== 布局 / 卡点 ===============================

def build_cuts(cuts, versions_dur, fps, cut_interval):
    """生成切换点数组（秒），并给出可用总时长（避开各版本尾部/角标偏移）。"""
    total = min(versions_dur)
    if cuts:
        c = sorted(float(x) for x in cuts if 0 < float(x) < total)
        return c, total
    if cut_interval <= 0:
        return [], total
    c, t = [], cut_interval
    while t < total - 1e-6:
        c.append(round(t, 3))
        t += cut_interval
    return c, total


def align_cuts_to_beats(cuts, dur, bpm, phase):
    """把自动生成的 cuts 对齐到 BGM 拍点（保持近似每段时长）。"""
    if not bpm or bpm <= 0:
        return cuts, None
    period = 60.0 / bpm
    desired = cuts[0] if cuts else DEFAULT_CUT_INTERVAL
    k = max(1, int(round(desired / period)))
    interval = k * period
    first = phase + interval
    while first < interval * 0.6:
        first += period
    new, t = [], first
    while t < dur - 1e-6:
        new.append(round(t, 3))
        t += interval
    return new, {"bpm": round(bpm, 2), "period": round(period, 4),
                 "interval": round(interval, 3), "beats_per_cut": k,
                 "phase": round(phase, 4)}


def layout_timeline(cuts, dur, order, remove_worn=False):
    """布局状态机：每段一个布局，main 按 look 轮换，角标槽位放其余 look。

    若 remove_worn=True / "shift": 已经换装展示过的服装直接去除，仅保留后续待换装款式；
    若 remove_worn="anchor": 穿过的服装对应的原固定槽位留空 (None)。
    """
    bounds = [0.0] + list(cuts) + [round(dur, 3)]
    n = len(order)
    tl = []
    for k in range(len(bounds) - 1):
        t0, t1 = bounds[k], bounds[k + 1]
        if t1 - t0 < 1e-3:
            continue
        main = order[k % n]
        if remove_worn in (True, "shift", "pack"):
            # 穿过的服装直接去除，剩余待展示服装按队列槽位顺次填充
            slots = [order[j] for j in range(k + 1, n)]
        elif remove_worn == "anchor":
            # 穿过的服装对应的固定槽位直接留空
            slots = [order[j] if j > k else None for j in range(1, n)]
        else:
            slots = [order[(k + 1 + j) % n] for j in range(max(1, n - 1))]
        tl.append({"t0": round(t0, 3), "t1": round(t1, 3), "main": main,
                   "slots": slots})
    return tl


# =============================== 人物取景框 ===============================

def compute_person_crop(reader, matte, n, tile_wh, samples=9, margin=0.12,
                        single_person=True):
    """由若干采样帧的 alpha bbox 并集 -> 固定取景框（源坐标，比例=角标比例）。"""
    import numpy as np
    tw, th = tile_wh
    xs0, ys0, xs1, ys1 = [], [], [], []
    for i in range(samples):
        fi = int(round((i + 0.5) / samples * (n - 1)))
        fr = reader.get(fi)
        m = matte.get(fi)
        if fr is None or m is None:
            continue
        if m.shape[:2] != fr.shape[:2]:
            import cv2
            m = cv2.resize(m, (fr.shape[1], fr.shape[0]), interpolation=cv2.INTER_LINEAR)
        if single_person:
            m = keep_largest_component(m)
        ys, xs = np.nonzero(m > 100)
        if xs.size == 0:
            continue
        xs0.append(xs.min()); xs1.append(xs.max())
        ys0.append(ys.min()); ys1.append(ys.max())
    if not xs0:
        return None
    x0, x1 = min(xs0), max(xs1)
    y0, y1 = min(ys0), max(ys1)
    bw, bh = (x1 - x0 + 1), (y1 - y0 + 1)
    x0 -= bw * margin; x1 += bw * margin
    y0 -= bh * margin; y1 += bh * margin
    cw, ch = x1 - x0, y1 - y0
    target_ar = tw / float(th)
    if cw / ch < target_ar:
        nw = ch * target_ar
        x0 -= (nw - cw) / 2.0
        cw = nw
    else:
        nh = cw / target_ar
        y0 -= (nh - ch) / 2.0
        ch = nh
    return [float(x0), float(y0), float(cw), float(ch)]


def _fit_crop_cover(crop, fw, fh, tile_wh):
    """把取景框（人物包围盒）以中心为准扩展成与角标相同的宽高比（cover）。

    越界时优先整体平移窗口使其落在画面内（不补黑）；仅当窗口本身大于画面时
    才允许越界（调用方用边缘夹取填充）。
    """
    tw, th = tile_wh
    ar = tw / float(th)
    if crop:
        x0, y0, cw, ch = [float(v) for v in crop]
    else:
        x0, y0, cw, ch = 0.0, 0.0, float(fw), float(fh)
    if cw <= 0 or ch <= 0:
        x0, y0, cw, ch = 0.0, 0.0, float(fw), float(fh)
    cx = x0 + cw / 2.0
    cy = y0 + ch / 2.0
    # 向外扩展较窄的一边，使窗口比例 == 角标比例（不改变人物尺度比例）
    if cw / ch < ar:
        cw = ch * ar
    else:
        ch = cw / ar
    if cw <= fw:
        x0 = min(max(cx - cw / 2.0, 0.0), fw - cw)
    else:
        x0 = cx - cw / 2.0
    if ch <= fh:
        y0 = min(max(cy - ch / 2.0, 0.0), fh - ch)
    else:
        y0 = cy - ch / 2.0
    return x0, y0, cw, ch


def _crop_to_tile(frame, mask, crop, tile_wh, fit="cover"):
    """按固定取景框裁剪 -> 缩放到角标尺寸。

    默认 fit="cover"：窗口比例与角标一致 -> 等比缩放，人物不变形（越界用边缘夹取，
    窗口能放下时靠平移落在画面内，不补黑）。
    fit="stretch"：保留旧行为（各向异性缩放，会把人物压扁），仅作调试。
    mask 与 frame 使用完全相同的窗口与缩放。
    """
    import cv2
    import numpy as np
    tw, th = tile_wh
    fh, fw = frame.shape[:2]

    if fit == "stretch":
        x0, y0, cw, ch = ([int(round(v)) for v in crop] if crop
                          else (0, 0, fw, fh))
        pad_l = max(0, -x0); pad_t = max(0, -y0)
        pad_r = max(0, x0 + cw - fw); pad_b = max(0, y0 + ch - fh)
        fx0, fy0 = max(0, x0), max(0, y0)
        fx1, fy1 = min(fw, x0 + cw), min(fh, y0 + ch)
        sub = frame[fy0:fy1, fx0:fx1]
        if sub.size == 0:
            sub = frame
            pad_l = pad_t = pad_r = pad_b = 0
        sub = cv2.copyMakeBorder(sub, pad_t, pad_b, pad_l, pad_r,
                                 cv2.BORDER_REPLICATE)
        f = _resize(sub, tw, th)
        m = None
        if mask is not None:
            mm = mask
            if mm.shape[:2] != (fh, fw):
                mm = cv2.resize(mm, (fw, fh), interpolation=cv2.INTER_LINEAR)
            msub = mm[fy0:fy1, fx0:fx1]
            if msub.size == 0:
                msub = mm
            else:
                msub = cv2.copyMakeBorder(msub, pad_t, pad_b, pad_l, pad_r,
                                          cv2.BORDER_CONSTANT, value=0)
            m = _resize(msub, tw, th)
        return f, m

    # ---- cover（默认）：窗口比例 == 角标比例，等比缩放 ----
    x0, y0, cw, ch = _fit_crop_cover(crop, fw, fh, tile_wh)
    ix0, iy0 = int(np.floor(x0)), int(np.floor(y0))
    ix1, iy1 = int(np.ceil(x0 + cw)), int(np.ceil(y0 + ch))
    pad_l = max(0, -ix0); pad_t = max(0, -iy0)
    pad_r = max(0, ix1 - fw); pad_b = max(0, iy1 - fh)
    fx0, fy0 = max(0, ix0), max(0, iy0)
    fx1, fy1 = min(fw, ix1), min(fh, iy1)
    sub = frame[fy0:fy1, fx0:fx1]
    if sub.size == 0:
        sub = frame
        pad_l = pad_t = pad_r = pad_b = 0
    sub = cv2.copyMakeBorder(sub, pad_t, pad_b, pad_l, pad_r,
                             cv2.BORDER_REPLICATE)
    f = _resize(sub, tw, th)
    m = None
    if mask is not None:
        mm = mask
        if mm.shape[:2] != (fh, fw):
            mm = cv2.resize(mm, (fw, fh), interpolation=cv2.INTER_LINEAR)
        msub = mm[fy0:fy1, fx0:fx1]
        if msub.size == 0:
            msub = mm
        else:
            msub = cv2.copyMakeBorder(msub, pad_t, pad_b, pad_l, pad_r,
                                      cv2.BORDER_CONSTANT, value=0)
        m = _resize(msub, tw, th)
    return f, m


# =============================== 单帧合成 ===============================

def composite(base_img, fg, alpha):
    import numpy as np
    a = (alpha.astype(np.float32) / 255.0)[..., None]
    out = base_img.astype(np.float32) * (1.0 - a) + fg.astype(np.float32) * a
    return out.astype(np.uint8)


def render_frame(canvas, layers, style, frame_idx):
    """把主画面 + 角标合成到 canvas（in-place），返回虚线线段数。

    layers: [{"kind":"main","frame","mask"}, {"kind":"tile","rect":{...},
             "frame","mask"}]
    """
    import cv2
    import numpy as np
    dash = style["dash"]
    border = style["border"]
    total = 0

    for ly in layers:
        if ly["kind"] == "main":
            f, m = ly["frame"], ly["mask"]
            if m is not None:
                m = cv2.GaussianBlur(m, (5, 5), 1.2)
                canvas[:] = composite(canvas, f, m)
                if style.get("dash_main", True):    # 主画面虚线可关（角标虚线保留）
                    bm = (ly["mask"] > 127).astype(np.uint8) * 255
                    phase = (frame_idx * dash["speed"]) % float(dash["dash"] + dash["gap"]) \
                        if dash.get("animate") else 0.0
                    total += draw_dashed_outline(
                        canvas, bm, dash["dash"], dash["gap"], dash["width"], phase,
                        offset=(0, 0), color=tuple(dash["color"]))
        elif ly["kind"] == "ref":
            # 静态参考图卡片 / 透明人物贴纸
            r = ly["rect"]
            x = max(0, min(r["x"], canvas.shape[1] - 1))
            y = max(0, min(r["y"], canvas.shape[0] - 1))
            w = min(r["w"], canvas.shape[1] - x)
            h = min(r["h"], canvas.shape[0] - y)
            img = ly["img"]
            if img.shape[1] != w or img.shape[0] != h:
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

            if len(img.shape) == 3 and img.shape[2] == 4:
                # 纯人物+服装透明贴纸（RGBA）：直接进行 Alpha 混合，画面透亮无背景框
                bgr = img[:, :, :3]
                alpha = img[:, :, 3].astype(np.float32) / 255.0
                alpha_3d = np.repeat(alpha[:, :, np.newaxis], 3, axis=2)
                region = canvas[y:y + h, x:x + w].astype(np.float32)
                canvas[y:y + h, x:x + w] = np.clip(
                    region * (1.0 - alpha_3d) + bgr.astype(np.float32) * alpha_3d, 0, 255
                ).astype(np.uint8)
            else:
                rad = int(r.get("radius", border["radius"]))
                rad = max(0, min(rad, w // 2, h // 2))
                m = np.zeros((h, w), np.uint8)
                if rad > 0:
                    cv2.rectangle(m, (rad, 0), (w - rad, h), 255, -1)
                    cv2.rectangle(m, (0, rad), (w, h - rad), 255, -1)
                    for cx, cy in ((rad, rad), (w - rad, rad),
                                   (rad, h - rad), (w - rad, h - rad)):
                        cv2.circle(m, (cx, cy), rad, 255, -1)
                else:
                    m[:] = 255
                region = canvas[y:y + h, x:x + w]
                region[m > 127] = img[m > 127]
                bw = int(r.get("border", border["width"]))
                if bw > 0:
                    _rounded_rect_border(canvas, x, y, w, h, rad,
                                         tuple(border["color"]), bw)
        else:
            r = ly["rect"]
            x, y, w, h = r["x"], r["y"], r["w"], r["h"]
            x = max(0, min(x, canvas.shape[1] - 1))
            y = max(0, min(y, canvas.shape[0] - 1))
            w = min(w, canvas.shape[1] - x)
            h = min(h, canvas.shape[0] - y)
            region = canvas[y:y + h, x:x + w].copy()
            f, m = ly["frame"], ly["mask"]
            if m is not None:
                m = cv2.GaussianBlur(m, (5, 5), 1.2)
                region = composite(region, f, m)
            canvas[y:y + h, x:x + w] = region
            rad = r.get("radius", border["radius"])
            bw = r.get("border", border["width"])
            if bw > 0:
                _rounded_rect_border(canvas, x, y, w, h, rad,
                                     tuple(border["color"]), bw)
            if m is not None:
                bm = (ly["mask"] > 127).astype(np.uint8) * 255
                phase = (frame_idx * dash["speed"]) % float(dash["dash"] + dash["gap"]) \
                    if dash.get("animate") else 0.0
                total += draw_dashed_outline(
                    canvas, bm, dash["dash"], dash["gap"], dash["width"], phase,
                    offset=(x, y), color=tuple(dash["color"]))
    return total


def draw_text(canvas, text):
    import cv2
    if not isinstance(text, dict):
        return
    lines = text.get("lines") or []
    x = int(text.get("x", 40))
    y0 = int(text.get("y0", 120))
    size = float(text.get("size", 1.6))
    th = int(text.get("thickness", 3))
    color = tuple(text.get("color", [255, 255, 255]))
    for i, s in enumerate(lines):
        cv2.putText(canvas, str(s), (x, y0 + i * int(size * 46)),
                    cv2.FONT_HERSHEY_SIMPLEX, size, color, th, cv2.LINE_AA)


# =============================== 主流程 ===============================

def _encode_frames(out_dir, out_raw, make_frame, n_out, size, fps, audio_src,
                   total_dur):
    """逐帧写入 ffmpeg stdin 编码 H.264 yuv420p crf18（+ 可选音轨）。"""
    import numpy as np
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("未找到 ffmpeg")
    W, H = size
    if audio_src and not seg.has_audio(audio_src):
        _log(f"[警告] {audio_src} 无音轨，改为静音输出")
        audio_src = None
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "pipe:0"]
    if audio_src:
        cmd += ["-i", audio_src]
    cmd += ["-map", "0:v"]
    if audio_src:
        cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-t", f"{total_dur:.3f}",
            "-movflags", "+faststart", out_raw]
    # stderr 重定向到文件（用 PIPE 且不并发读取会因管道缓冲写满而死锁）
    errlog = os.path.join(out_dir, "_compose_ffmpeg.log")
    ef = open(errlog, "wb")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=ef)
    try:
        for i in range(n_out):
            fr = make_frame(i)
            fr = np.ascontiguousarray(fr, dtype=np.uint8)
            proc.stdin.write(fr.tobytes())
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    rc = proc.wait()
    ef.close()
    try:
        with open(errlog, "r", encoding="utf-8", errors="replace") as f:
            err = f.read()
    except Exception:
        err = ""
    return rc == 0 and os.path.exists(out_raw), err[-800:]


def run_compose(cfg):
    import cv2
    t_all = time.time()
    out_dir = _resolve(cfg["out_dir"])
    os.makedirs(out_dir, exist_ok=True)
    out_path = _resolve(cfg["out_path"])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    date = cfg.get("date") or time.strftime("%Y-%m-%d")
    structure = load_structure(date)
    style = resolve_style(cfg, structure)
    W, H = style["size"]
    fps = style["fps"]
    dry_run = bool(cfg.get("dry_run"))

    # ---- 版本 ----
    versions = []
    order = []
    for i, v in enumerate(cfg.get("versions") or []):
        p = _resolve(v["video"])
        info = probe_video(p)
        vid = str(v.get("id") or f"g{i + 1}")
        versions.append({"id": vid, "video": p, "shift": float(v.get("shift", 0.0)),
                         "w": info["w"], "h": info["h"], "n": info["n"],
                         "fps": info["fps"], "dur": info["dur"]})
        order.append(vid)
    if not versions:
        raise RuntimeError("cfg.versions 为空")
    _log(f"[compose] versions={[v['id'] for v in versions]} "
         f"size={W}x{H} fps={fps} structure_keys={style['structure_keys']}")

    plate = cfg.get("plate")
    plate_warn, plate_metrics = False, {}
    matte_map, matte_notes = {}, {}

    # ---- 干跑：只校验抠像工作流并回计划 ----
    if dry_run:
        if not os.path.exists(MATTE_WORKFLOW):
            raise RuntimeError(f"抠像工作流不存在: {MATTE_WORKFLOW}")
        # 拷入 input 以进入 LoadVideo 动态枚举（校验才能通过），不提交
        os.makedirs(INPUT_ROOT, exist_ok=True)
        vin = "multilook_matte_dryrun.mp4"
        if not os.path.exists(os.path.join(INPUT_ROOT, vin)):
            shutil.copy2(versions[0]["video"], os.path.join(INPUT_ROOT, vin))
        with open(MATTE_WORKFLOW, "r", encoding="utf-8") as f:
            tpl = json.load(f)
        try:
            _ds = float(cfg.get("matte_scale") if cfg.get("matte_scale") else 0.5)
        except Exception:
            _ds = 0.5
        if _ds <= 0:
            _ds = 1.0
        _dw = max(1, int(round(W * _ds)))
        _dh = max(1, int(round(H * _ds)))
        wf = base.inject_placeholders(tpl, {
            "video": vin, "width": _dw, "height": _dh,
            "output": f"{date}/{cfg.get('project')}/matte_src/g1_c000"})
        base._INFO_CACHE.pop("LoadVideo", None)
        errors, lines = base.validate_workflow(wf)
        for ln in lines:
            _log(ln)
        if errors:
            raise RuntimeError("抠像工作流校验失败: " + "; ".join(errors[:5]))
        return {"out_path": out_path, "layout_timeline": [], "cuts": [],
                "plate": None, "matte": {}, "elapsed_s": round(time.time() - t_all, 2),
                "acceptance": {"dry_run": True, "matte_workflow_nodes": len(wf),
                               "matte_workflow_validate": "OK",
                               "matte_input_size": [_dw, _dh]}}

    # ---- 底板 ----
    if plate:
        plate = _resolve(plate)
        pimg = cv2.imread(plate)
        if pimg is None:
            raise RuntimeError(f"底板读取失败: {plate}")
        pimg = _resize_cover(pimg, W, H)
        cv2.imwrite(os.path.join(out_dir, "plate.png"), pimg)
        plate = os.path.join(out_dir, "plate.png")
    else:
        plate, plate_warn, plate_metrics = extract_plate(
            _resolve(cfg["driving"]), out_dir, style["size"])
        pimg = cv2.imread(plate)
    _log(f"[compose] plate={plate} warn={plate_warn}")

    # ---- 抠像 ----
    matte_map, matte_notes = ensure_mattes(cfg, versions, style)
    matte_readers = {}
    for v in versions:
        matte_readers[v["id"]] = MatteReader(os.path.dirname(matte_map[v["id"]]),
                                             os.path.basename(matte_map[v["id"]]))
    # 单人物过滤（默认开）：alpha 只保留最大连通域，剔除畸变小人物/碎片
    single = bool(cfg.get("single_person", True))
    # 角标取景适配：cover（默认，等比不变形）| stretch（旧行为，仅调试）
    tile_fit = str(cfg.get("tile_fit") or "cover")

    # ---- 卡点 ----
    dur_v = [v["dur"] - v["shift"] for v in versions]
    # 角标模式：video（默认，动态抠像小人）| ref（静态参考图卡片）| off（无角标）
    tiles_mode = str(cfg.get("tiles_mode")
                     or ("off" if cfg.get("tiles_off") else "video"))
    if tiles_mode == "off":
        n_slots = 0
    else:
        n_slots = max(1, min(len(style["tiles"]), max(1, len(order) - 1)))
    max_off = max([t["offset"] for t in style["tiles"][:n_slots]] or [0.0])
    dur_avail = min(dur_v) - max_off
    cuts, total = build_cuts(cfg.get("cuts"), dur_v, fps,
                             style.get("cut_interval", DEFAULT_CUT_INTERVAL))
    # 角标偏移 -> 收紧总时长
    total = min(total, dur_avail)
    cuts = [c for c in cuts if c < total - 1e-6]
    total = max(0.5, min(total, min(dur_v)))

    bgm_path = _resolve(cfg.get("bgm")) if cfg.get("bgm") else None
    bgm_info = None
    if cfg.get("bgm_auto") and not cfg.get("cuts"):
        try:
            chosen, analyzed, _pa, reason = swap.auto_select_bgm(BGM_DIR, len(cuts) or 1,
                                                                0.0, align=True)
            if chosen and chosen.get("reliable") and chosen.get("bpm"):
                new_cuts, meta = align_cuts_to_beats(cuts, total, chosen["bpm"],
                                                     chosen.get("phase") or 0.0)
                cuts = new_cuts
                bgm_path = chosen["path"]
                bgm_info = {"auto": True, "path": bgm_path,
                            "name": os.path.basename(bgm_path),
                            "reason": reason, "clap": meta}
                _log(f"[compose][bgm-auto] 选曲 {os.path.basename(bgm_path)} "
                     f"BPM≈{chosen.get('bpm')} -> cuts={cuts}（{reason}）")
        except Exception as e:
            _log(f"[警告][bgm-auto] 选曲/对齐失败，沿用默认 cuts: {e}")

    remove_worn = cfg.get("remove_worn", True if tiles_mode == "ref" else False)
    tl = layout_timeline(cuts, total, order, remove_worn=remove_worn)
    _log(f"[compose] total={total:.3f}s cuts={cuts} 段数={len(tl)} remove_worn={remove_worn}")

    # ---- 取景框（角标固定裁剪） ----
    rects = []
    for t in style["tiles"][:n_slots]:
        rects.append({"x": int(t["x"]), "y": int(t["y"]), "w": int(t["w"]),
                      "h": int(t["h"]), "offset": float(t["offset"]),
                      "radius": int(t.get("_radius", t.get("radius", style["border"]["radius"]))),
                      "border": int(t.get("_border", t.get("border", style["border"]["width"])))})
    crops = {}
    if n_slots > 0 and tiles_mode != "ref":   # 无角标/静态角标不需要取景框
        tmp_readers = {v["id"]: SeqReader(v["video"]) for v in versions}
        try:
            for v in versions:
                crops[v["id"]] = compute_person_crop(
                    tmp_readers[v["id"]], matte_readers[v["id"]], v["n"],
                    (rects[0]["w"], rects[0]["h"]) if rects else (W, H),
                    single_person=single)
        finally:
            for rd in tmp_readers.values():
                rd.release()

    # ---- 逐帧合成 ----
    n_out = max(1, int(round(total * fps)))
    _log(f"[compose] 合成 {n_out} 帧 @{fps}fps -> {out_path}")

    def seg_of(t):
        for e in tl:
            if e["t0"] <= t < e["t1"]:
                return e
        return tl[-1]

    vmeta = {v["id"]: v for v in versions}
    readers_pool = {}

    def _get_reader(key, path):
        if key not in readers_pool:
            readers_pool[key] = SeqReader(path)
        return readers_pool[key]

    dash_segments = 0
    main_off = float((cfg.get("main_def") or {}).get("offset", 0.0))

    # 静态参考角标：加载各 look 参考图（id -> 原图），卡片按槽位尺寸惰性缓存
    ref_cards = {}
    ref_cache_sized = {}
    if tiles_mode == "ref":
        look_paths = [str(x) for x in (cfg.get("looks") or [])]
        for idx, v in enumerate(versions):
            if idx < len(look_paths) and os.path.exists(look_paths[idx]):
                img = cv2.imread(look_paths[idx], cv2.IMREAD_UNCHANGED)
                if img is not None:
                    ref_cards[v["id"]] = img
        _log(f"[compose] 静态参考角标：已加载 {len(ref_cards)}/{len(versions)} 张参考图")

    def make_frame(i):
        nonlocal dash_segments
        t = i / float(fps)
        e = seg_of(t)
        canvas = pimg.copy()
        layers = []
        mv = vmeta[e["main"]]
        mi = int(round((t + main_off + mv["shift"]) * mv["fps"]))
        mfr = _get_reader(("main", e["main"]), mv["video"]).get(mi)
        mm = matte_readers[e["main"]].get(mi)
        if single and mm is not None:                       # 只保留最大连通域
            mm = keep_largest_component(mm)
        if mfr is not None and float(mfr.mean()) >= 6.0:   # 黑帧无有效前景
            layers.append({"kind": "main",
                           "frame": _resize_cover(mfr, W, H),
                           "mask": _resize_cover(mm, W, H) if mm is not None else None})
        for j, sv in enumerate(e["slots"]):
            if j >= len(rects):
                break
            r = rects[j]
            if tiles_mode == "ref":                         # 静态参考图卡片
                img = ref_cards.get(sv)
                if img is None:
                    continue
                ck = (sv, j)
                card = ref_cache_sized.get(ck)
                if card is None:
                    card = _resize_cover(img, r["w"], r["h"])
                    ref_cache_sized[ck] = card
                layers.append({"kind": "ref", "rect": r, "img": card})
                continue
            sver = vmeta[sv]
            si = int(round((t + r["offset"] + sver["shift"]) * sver["fps"]))
            sfr = _get_reader(("tile%d" % j, sv), sver["video"]).get(si)
            sm = matte_readers[sv].get(si)
            if single and sm is not None:                   # 只保留最大连通域
                sm = keep_largest_component(sm)
            if sfr is None or float(sfr.mean()) < 6.0:
                continue
            crop = crops.get(sv)
            if crop:
                f, m = _crop_to_tile(sfr, sm, crop, (r["w"], r["h"]),
                                     fit=tile_fit)
            else:
                # 无取景框时同样走保比例 cover（不再直接各向异性拉伸）
                f, m = _crop_to_tile(sfr, sm, None, (r["w"], r["h"]),
                                     fit=tile_fit)
            layers.append({"kind": "tile", "rect": r, "frame": f, "mask": m})
        dash_segments += render_frame(canvas, layers, style, i)
        if cfg.get("text"):
            draw_text(canvas, cfg["text"])
        return canvas

    audio = cfg.get("audio")
    if audio == "driving" or audio is True:
        audio_src = _resolve(cfg["driving"])
    elif isinstance(audio, str) and os.path.exists(_resolve(audio)):
        audio_src = _resolve(audio)
    else:
        audio_src = None

    out_raw = os.path.join(out_dir, "_compose_raw.mp4")
    ok, err = _encode_frames(out_dir, out_raw, make_frame, n_out, [W, H], fps,
                             audio_src, total)
    for rd in readers_pool.values():
        rd.release()
    if not ok:
        raise RuntimeError("编码失败: " + err)

    # ---- BGM 混音 ----
    if bgm_path and os.path.exists(bgm_path):
        amb = 0.2 if audio_src else 0.0
        okm, errm = swap.mix_bgm(out_raw, bgm_path, out_path,
                                 bgm_volume=1.0, ambient_volume=amb,
                                 start_offset=0.0)
        if not okm:
            _log("[警告] BGM 混音失败，回退为原始音轨版: " + errm[-200:])
            shutil.copy2(out_raw, out_path)
    else:
        shutil.copy2(out_raw, out_path)

    # ---- 验收 ----
    finfo = probe_video(out_path)
    accept = {
        "size": f"{finfo['w']}x{finfo['h']}",
        "size_ok": bool(finfo["w"] == W and finfo["h"] == H),
        "fps": finfo["fps"], "fps_ok": bool(abs(finfo["fps"] - fps) < 0.01),
        "duration_s": round(finfo["dur"], 3), "frames": finfo["n"],
        "target_duration_s": round(total, 3),
        "has_audio": finfo["has_audio"],
        "audio_codec": swap.probe_audio_codec(out_path),
        "plate": plate, "plate_warn": plate_warn, "plate_metrics": plate_metrics,
        "matte_mode": {k: v.get("mode") for k, v in matte_notes.items()},
        "matte_frames": {k: v.get("frames") for k, v in matte_notes.items()},
        "matte_chunk": int(cfg.get("matte_chunk") or 32),
        "matte_scale": (float(cfg.get("matte_scale")) if cfg.get("matte_scale")
                        else 0.5),
        "matte_input_size": {k: v.get("input_size") for k, v in matte_notes.items()},
        "matte_n_chunks": {k: v.get("n_chunks") for k, v in matte_notes.items()},
        "cuts": cuts, "n_segments": len(tl), "n_tiles": len(rects),
        "tiles_mode": tiles_mode,
        "single_person": single,
        "tile_fit": tile_fit,
        "dash_enabled": bool(style["dash"]["width"] > 0),
        "dash_segments_total": dash_segments,
        "bgm": bgm_info,
        "versions": [{"id": v["id"], "video": v["video"], "shift": v["shift"],
                      "n": v["n"], "fps": round(v["fps"], 3),
                      "dur": round(v["dur"], 3)} for v in versions],
        "looks": [str(x) for x in (cfg.get("looks") or [])],
    }
    report = {"out_path": out_path, "layout_timeline": tl, "cuts": cuts,
              "plate": plate, "matte": matte_map, "acceptance": accept,
              "elapsed_s": round(time.time() - t_all, 2),
              "project": cfg.get("project"), "date": date, "slug": cfg.get("slug"),
              "style": {"size": [W, H], "fps": fps, "tiles": rects,
                        "dash": style["dash"], "frame_border": style["border"]},
              "matte_notes": matte_notes}
    with open(os.path.join(out_dir, "compose_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    _log(f"[compose] 完成 -> {out_path}（{report['elapsed_s']}s）")
    return report


# =============================== CLI（最小自测） ===============================

def _parse_args():
    ap = argparse.ArgumentParser(description="贴纸多版本合成器（最小自测 CLI）")
    ap.add_argument("--versions", required=True, help="逗号分隔的版本视频路径")
    ap.add_argument("--driving", required=True, help="驱动视频（底板 + 默认音轨）")
    ap.add_argument("--out", required=True, help="输出 mp4 路径")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--plate", default=None)
    ap.add_argument("--cuts", default=None, help="切换点秒，逗号分隔（如 3,6,9）")
    ap.add_argument("--alpha", choices=["bgsub", "birefnet"], default="bgsub")
    ap.add_argument("--no-gpu", action="store_true")
    ap.add_argument("--bgm", default=None)
    ap.add_argument("--bgm-auto", action="store_true")
    ap.add_argument("--audio", default="driving")
    ap.add_argument("--size", default="1080x1920")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--project", default="ootd_multilook_poc")
    ap.add_argument("--date", default=None)
    ap.add_argument("--slug", default=None)
    ap.add_argument("--slot-offsets", default=None, help="角标时间偏移，逗号分隔")
    ap.add_argument("--version-offsets", default=None, help="版本时间偏移，逗号分隔")
    ap.add_argument("--matte-dir", default=None)
    ap.add_argument("--matte-chunk", type=int, default=32,
                    help="抠像分块帧数（默认 32，规避 BiRefNet 整批 OOM）")
    ap.add_argument("--matte-scale", type=float, default=0.5,
                    help="抠像输入降采样比例（默认 0.5 -> 540x960）")
    ap.add_argument("--no-single-person", dest="single_person",
                    action="store_false", default=True,
                    help="关闭『最大连通域保人』过滤（默认开启）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tile-fit", choices=["cover", "stretch"], default="cover",
                    help="角标取景适配：cover=等比不变形（默认），stretch=旧行为")
    return ap.parse_args()


def main():
    args = _parse_args()
    out_path = os.path.abspath(args.out)
    out_dir = os.path.abspath(args.out_dir) if args.out_dir else os.path.dirname(out_path)
    date = args.date or time.strftime("%Y-%m-%d")
    slug = args.slug or os.path.splitext(os.path.basename(out_path))[0]
    size = [int(x) for x in args.size.lower().split("x")]
    voff = [float(x) for x in args.version_offsets.split(",")] if args.version_offsets else []
    versions = []
    for i, p in enumerate([x for x in args.versions.split(",") if x.strip()]):
        item = {"id": f"g{i + 1}", "video": os.path.abspath(p.strip())}
        if i < len(voff):
            item["shift"] = voff[i]
        versions.append(item)
    tile_defs = None
    if args.slot_offsets:
        offs = [float(x) for x in args.slot_offsets.split(",")]
        tile_defs = []
        for t, o in zip(DEFAULT_TILES[:len(offs)], offs):
            tile_defs.append({"x": t["x"], "y": t["y"], "w": t["w"],
                              "h": t["h"], "offset": o})
    cfg = {
        "project": args.project, "date": date, "slug": slug,
        "out_dir": out_dir, "out_path": out_path,
        "driving": os.path.abspath(args.driving),
        "versions": versions, "looks": [],
        "cuts": [float(x) for x in args.cuts.split(",")] if args.cuts else None,
        "bgm": args.bgm, "bgm_auto": args.bgm_auto, "audio": args.audio,
        "tile_defs": tile_defs, "main_def": None, "dash": None,
        "frame_border": None,
        "matte_dir": os.path.abspath(args.matte_dir) if args.matte_dir else None,
        "no_gpu": args.no_gpu or args.alpha == "bgsub",
        "synth_alpha": args.alpha == "bgsub",
        "text": None, "size": size, "fps": args.fps,
        "plate": os.path.abspath(args.plate) if args.plate else None,
        "dry_run": args.dry_run,
        "single_person": bool(args.single_person),
        "matte_chunk": int(args.matte_chunk),
        "matte_scale": float(args.matte_scale),
        "tile_fit": str(args.tile_fit),
    }
    res = run_compose(cfg)
    print(json.dumps({k: res[k] for k in
                      ("out_path", "cuts", "plate", "elapsed_s")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())