#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从成片提取无人背景板: BiRefNet 逐帧掩码 + 相机配准 + 时域中值合成。

用法:
  venv/Scripts/python.exe tools/extract_bg_plate.py \
      --video "output/2026-10-12/hitomi_batch/ayano (insta_ayano.fj)/[26-08-24] DcabvwjgySj_p0_00001-audio.mp4" \
      --slug ayano_dcab --date 2026-10-17 --out-root output/2026-10-17

阶段: extract -> mask -> align -> composite -> verify，--stage all 一次跑完，
单阶段可断点续跑（掩码/配准结果落盘缓存，--force-mask 强制重算掩码）。
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import warnings

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")

COMFY = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
LOG_PATH = None


def log(msg):
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if LOG_PATH:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ---------------------------------------------------------------- ComfyUI API

def submit_workflow(wf, timeout=900, poll=2.0):
    body = json.dumps({"prompt": wf, "client_id": uuid.uuid4().hex}).encode()
    req = urllib.request.Request(f"{COMFY}/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(OPENER.open(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:2000]
        raise RuntimeError(f"/prompt 400: {detail}")
    pid = resp["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(poll)
        hist = json.loads(OPENER.open(f"{COMFY}/history/{pid}", timeout=15).read())
        if pid not in hist:
            continue
        entry = hist[pid]
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            raise RuntimeError(f"任务执行错误: {json.dumps(status)[:1500]}")
        if status.get("completed"):
            return entry
    raise RuntimeError(f"任务超时 ({timeout}s): {json.dumps(wf)[:300]}")


# ---------------------------------------------------------------- ffprobe 等工具

def ffprobe_video(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
           "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
           "-of", "json", path]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    st = json.loads(out)["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return {"w": st["width"], "h": st["height"],
            "fps": round(float(num) / float(den), 3),
            "frames": int(st["nb_read_frames"])}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 阶段: extract

def stage_extract(args, out_dir, work_dir):
    src_copy = os.path.join("input", "bgplate", f"{args.slug}_src.mp4")
    frames_dir = os.path.join("input", "bgplate", args.slug, "frames")
    os.makedirs(os.path.dirname(src_copy), exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)

    src = args.video
    if not os.path.exists(src):
        raise SystemExit(f"源视频不存在: {src}")
    if os.path.abspath(src) != os.path.abspath(src_copy):
        shutil.copy2(src, src_copy)
    meta = ffprobe_video(src_copy)
    meta["src_copy"] = os.path.abspath(src_copy)
    meta["sha256"] = sha256_of(src_copy)
    log(f"视频: {meta['w']}x{meta['h']} @ {meta['fps']}fps, {meta['frames']} 帧")

    expected = frames_dir and len(glob.glob(os.path.join(frames_dir, "f_*.png")))
    if not expected or expected != meta["frames"] or args.force_mask:
        for f in glob.glob(os.path.join(frames_dir, "f_*.png")):
            os.remove(f)
        cmd = ["ffmpeg", "-y", "-i", src_copy, "-vsync", "0",
               os.path.join(frames_dir, "f_%05d.png")]
        log("抽帧中 (PNG 无损)...")
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    n = len(glob.glob(os.path.join(frames_dir, "f_*.png")))
    if n != meta["frames"]:
        raise SystemExit(f"抽帧数 {n} != 视频帧数 {meta['frames']}")
    meta["frames_dir"] = os.path.abspath(frames_dir)
    with open(os.path.join(work_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


# ---------------------------------------------------------------- 阶段: mask

def mask_workflow(frames_dir, seg, cap, skip, S, x0, y0, W, H, prefix):
    return {
        "1": {"class_type": "VHS_LoadImages", "inputs": {
            "directory": frames_dir, "image_load_cap": cap,
            "skip_first_images": skip, "select_every_nth": 1}},
        "2": {"class_type": "ResizeAndPadImage", "inputs": {
            "image": ["1", 0], "target_width": S, "target_height": S,
            "padding_color": "black", "interpolation": "lanczos"}},
        "3": {"class_type": "LoadBackgroundRemovalModel", "inputs": {
            "bg_removal_name": "BiRefNet-general.safetensors"}},
        "4": {"class_type": "RemoveBackground", "inputs": {
            "bg_removal_model": ["3", 0], "image": ["2", 0]}},
        "5": {"class_type": "CropMask", "inputs": {
            "mask": ["4", 0], "x": x0, "y": y0, "width": W, "height": H}},
        "6": {"class_type": "MaskToImage", "inputs": {"mask": ["5", 0]}},
        "7": {"class_type": "SaveImage", "inputs": {
            "images": ["6", 0], "filename_prefix": prefix}},
    }


def stage_masks(args, meta, out_dir, work_dir):
    W, H, N = meta["w"], meta["h"], meta["frames"]
    S = max(W, H)
    x0, y0 = (S - W) // 2, (S - H) // 2
    masks_dir = os.path.join(work_dir, "masks")
    os.makedirs(masks_dir, exist_ok=True)
    prefix = f"{args.date}/bg_plate_{args.slug}/_work/masks/c{{seg}}"

    todo = []
    if args.force_mask or not os.path.exists(os.path.join(work_dir, "masks_done.json")):
        todo = list(range(0, N, args.chunk))
    else:
        done = set(json.load(open(os.path.join(work_dir, "masks_done.json"))))
        todo = [s for s in range(0, N, args.chunk) if s not in done]
    if todo:
        log(f"掩码分块推理: {len(todo)} 块 x<= {args.chunk} 帧")
    for seg_i, start in enumerate(todo):
        cap = min(args.chunk, N - start)
        wf = mask_workflow(meta["frames_dir"], seg_i, cap, start, S, x0, y0, W, H,
                           prefix.format(seg=f"{seg_i:02d}"))
        t0 = time.time()
        submit_workflow(wf)
        log(f"  chunk {start}-{start + cap - 1} 完成 ({time.time() - t0:.0f}s)")
        done_path = os.path.join(work_dir, "masks_done.json")
        done = set()
        if os.path.exists(done_path):
            done = set(json.load(open(done_path)))
        done.add(start)
        json.dump(sorted(done), open(done_path, "w"))

    # 兼容两种落盘: 旧版无分段号 masks_*.png (work_dir 下) / 新版 cXX_*.png (masks/ 下)
    files = sorted(set(glob.glob(os.path.join(work_dir, "masks_*.png"))) |
                   set(glob.glob(os.path.join(masks_dir, "c*_*.png"))))
    if len(files) != N:
        raise SystemExit(f"掩码数 {len(files)} != 帧数 {N}")
    mm_path = os.path.join(work_dir, "masks_u8.npy")
    mm = np.lib.format.open_memmap(mm_path, mode="w+", dtype=np.uint8, shape=(N, H, W))
    for i, fp in enumerate(files):
        mm[i] = cv2.imread(fp, cv2.IMREAD_GRAYSCALE)
    mm.flush()
    log(f"掩码缓存: {mm_path} ({N} 帧)")
    return mm_path


# ---------------------------------------------------------------- 掩码后处理

def load_fg_dil(mask_u8, dilate_px):
    m = (mask_u8 > 0.02 * 255).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    kd = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_px * 2 + 1, dilate_px * 2 + 1))
    return cv2.dilate(m, kd)


# ---------------------------------------------------------------- 阶段: align

def align_one(gray_s, gray_ref, fg_dil_s, orb, bf, scale):
    """返回 (M_full2x3, mode, inliers)。M 把当前帧映射到参考帧坐标系。

    特征只在当前帧的背景区取（fg_dil 腐蚀 25px 后做掩码），参考帧全域取。
    """
    inv = cv2.bitwise_not(fg_dil_s)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    feat_mask = cv2.erode(inv, k)
    gs = cv2.resize(gray_s, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gr = cv2.resize(gray_ref, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    feat_mask_s = cv2.resize(feat_mask, (gs.shape[1], gs.shape[0]),
                             interpolation=cv2.INTER_NEAREST)

    kd, dd = orb.detectAndCompute(gr, None)
    ks, ds = orb.detectAndCompute(gs, feat_mask_s)
    if dd is None or ds is None or len(kd) < 12 or len(ks) < 12:
        return None, "identity", 0
    raw = bf.knnMatch(ds, dd, k=2)
    good = [m for m, n in (p for p in raw if len(p) == 2)
            if m.distance < 0.75 * n.distance]
    if len(good) < 12:
        return None, "identity", 0
    pts_s = np.float32([ks[m.queryIdx].pt for m in good])
    pts_d = np.float32([kd[m.trainIdx].pt for m in good])
    M, inl = cv2.estimateAffinePartial2D(pts_s, pts_d, method=cv2.RANSAC,
                                         ransacReprojThreshold=2.0, maxIters=5000)
    if M is None or inl is None or int(inl.sum()) < 20:
        return None, "identity", 0
    M_full = M.copy()
    M_full[:, 2] *= (1.0 / scale)
    return M_full, "direct", int(inl.sum())


def stage_align(args, meta, work_dir):
    W, H, N = meta["w"], meta["h"], meta["frames"]
    masks = np.load(os.path.join(work_dir, "masks_u8.npy"), mmap_mode="r")
    frames_dir = meta["frames_dir"]
    stride = max(1, math_ceil(N / args.max_samples))
    samples = list(range(0, N, stride))
    if samples[-1] != N - 1:
        samples.append(N - 1)
    S = len(samples)
    log(f"采样 {S}/{N} 帧 (stride={stride})")

    ref_idx = S // 2
    ref_path = os.path.join(frames_dir, f"f_{samples[ref_idx] + 1:05d}.png")
    ref_frame = cv2.imread(ref_path)
    gray_ref = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2GRAY)

    frames_mm = np.lib.format.open_memmap(
        os.path.join(work_dir, "frames_warp.npy"), mode="w+",
        dtype=np.uint8, shape=(S, H, W, 3))
    valid_mm = np.lib.format.open_memmap(
        os.path.join(work_dir, "valid.npy"), mode="w+",
        dtype=np.uint8, shape=(S, H, W))

    shifts = []
    sc = 0.25
    for s in samples:
        fr = cv2.imread(os.path.join(frames_dir, f"f_{s + 1:05d}.png"))
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        a = cv2.resize(gray_ref, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        b = cv2.resize(g, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        (dx, dy), resp = cv2.phaseCorrelate(a.astype(np.float64), b.astype(np.float64))
        shifts.append((abs(dx) / sc, abs(dy) / sc))
    sh = np.array(shifts)
    p95 = np.percentile(sh, 95, axis=0)
    p50 = np.percentile(sh, 50, axis=0)
    static = p95.max() < args.static_thresh and p50.max() < 0.5
    mode = "static" if static else "motion"
    log(f"运动判定: mode={mode} dx p50={p50[0]:.2f}/p95={p95[0]:.2f}px "
        f"dy p50={p50[1]:.2f}/p95={p95[1]:.2f}px")

    orb = cv2.ORB_create(nfeatures=2000, scaleFactor=1.2, nlevels=8)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    align_stats = {"modes": [], "inliers": [], "identity": 0, "chained": 0}

    prev_M = None
    for i, s in enumerate(samples):
        frame = cv2.imread(os.path.join(frames_dir, f"f_{s + 1:05d}.png"))
        fg = load_fg_dil(np.asarray(masks[s]), args.dilate)
        if static:
            warped = frame
            valid = (fg == 0).astype(np.uint8)
            align_stats["modes"].append("static")
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            M, m_mode, inl = align_one(gray, gray_ref, fg, orb, bf, 0.5)
            if M is None:
                M = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float64)
                align_stats["identity"] += 1
            else:
                align_stats["inliers"].append(inl)
            align_stats["modes"].append(m_mode)
            prev_M = M
            warped = cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_CONSTANT)
            ones = np.ones((H, W), np.uint8) * 255
            wv = cv2.warpAffine(ones, M, (W, H), flags=cv2.INTER_NEAREST) > 127
            valid = (wv & (fg == 0)).astype(np.uint8)
        frames_mm[i] = warped
        valid_mm[i] = valid
        if (i + 1) % 20 == 0:
            log(f"  align {i + 1}/{S}")
    frames_mm.flush()
    valid_mm.flush()

    json.dump({"mode": mode, "samples": samples, "S": S, "stats": {
        "identity": align_stats["identity"], "chained": align_stats["chained"],
        "inliers_med": int(np.median(align_stats["inliers"])) if align_stats["inliers"] else 0,
        "dx_p50": round(float(p50[0]), 2), "dx_p95": round(float(p95[0]), 2),
        "dy_p50": round(float(p50[1]), 2), "dy_p95": round(float(p95[1]), 2),
    }}, open(os.path.join(work_dir, "align.json"), "w"), indent=1)
    log(f"align 完成: identity={align_stats['identity']} chained={align_stats['chained']}")
    return samples


def math_ceil(a):
    return int(-(-a // 1))


# ---------------------------------------------------------------- 阶段: composite

def composite(args, meta, work_dir, out_dir):
    W, H = meta["w"], meta["h"]
    al = json.load(open(os.path.join(work_dir, "align.json")))
    S = al["S"]
    frames_mm = np.load(os.path.join(work_dir, "frames_warp.npy"), mmap_mode="r")
    valid_mm = np.load(os.path.join(work_dir, "valid.npy"), mmap_mode="r")

    plate = np.zeros((H, W, 3), np.float32)
    count = np.zeros((H, W), np.int32)
    tile = args.tile

    def tile_median_trim(data, v):
        """data (S,h,w,3), v (S,h,w)bool -> (plate (h,w,3), cnt (h,w))。

        np.sort 把 NaN 排到末尾后按有效数索引取分位，远快于 nanpercentile。
        spread(hi-lo) 大的像素说明有持续离群(反光/闪烁)，退回纯中值。
        """
        cnt = v.sum(axis=0)
        dat = np.where(v[..., None], data, np.nan)
        srt = np.sort(dat, axis=0)
        med_i = np.where(cnt > 0, (cnt - 1) // 2, 0)
        med = np.take_along_axis(srt, med_i[None, :, :, None], axis=0)[0]
        lo_i = np.clip((cnt * 0.4).astype(int), 0, S - 1)
        hi_i = np.clip(np.ceil(cnt * 0.6).astype(int) - 1, 0, S - 1)
        lo = np.take_along_axis(srt, lo_i[None, :, :, None], axis=0)[0]
        hi = np.take_along_axis(srt, hi_i[None, :, :, None], axis=0)[0]
        trim = (lo + hi) / 2
        spread = hi - lo
        spread_ok = (spread < 24).all(axis=-1) & (cnt > 4)
        t = np.where(spread_ok[..., None], trim, med)
        t[cnt == 0] = 0
        return t.astype(np.float32), cnt

    for y0 in range(0, H, tile):
        for x0 in range(0, W, tile):
            ys, xs = slice(y0, min(y0 + tile, H)), slice(x0, min(x0 + tile, W))
            data = np.asarray(frames_mm[:S, ys, xs, :], dtype=np.float32)
            v = np.asarray(valid_mm[:S, ys, xs], dtype=bool)
            t, cnt = tile_median_trim(data, v)
            plate[ys, xs] = t
            count[ys, xs] = cnt
    log("中值合成主pass 完成")

    fg_union = np.zeros((H, W), np.uint8)
    masks = np.load(os.path.join(work_dir, "masks_u8.npy"), mmap_mode="r")
    for s in al["samples"]:
        fg_union |= load_fg_dil(np.asarray(masks[s]), args.dilate)
    always_fg = None
    if al["mode"] == "static":
        always_fg = np.ones((H, W), np.uint8)
        for s in al["samples"]:
            always_fg &= load_fg_dil(np.asarray(masks[s]), args.dilate)

    # 边缘污染二次剔除
    if args.refine:
        k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19))
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        band = (cv2.dilate(fg_union, k9) > 0) & ~(cv2.erode(fg_union, k3) > 0)
        for y0 in range(0, H, tile):
            for x0 in range(0, W, tile):
                ys, xs = slice(y0, min(y0 + tile, H)), slice(x0, min(x0 + tile, W))
                b = band[ys, xs]
                if not b.any():
                    continue
                data = np.asarray(frames_mm[:S, ys, xs, :], dtype=np.float32)
                v = np.asarray(valid_mm[:S, ys, xs], dtype=bool)
                pl = plate[ys, xs]
                ad = np.where(v, np.abs(data - pl[None]).mean(axis=3), np.nan)
                srt1 = np.sort(ad, axis=0)
                cnt = v.sum(axis=0)
                med_i = np.where(cnt > 0, (cnt - 1) // 2, 0)
                d = np.take_along_axis(srt1, med_i[None, :, :], axis=0)[0]
                fix = b & (np.nan_to_num(d, nan=0) > 28)
                if not fix.any():
                    continue
                pol = np.nan_to_num(ad, nan=0) > 28
                nv = v & ~(pol & fix[None])
                t2, _ = tile_median_trim(data, nv)
                reg = plate[ys, xs]
                reg[fix] = t2[fix]
        log("边缘污染 refine pass 完成")

    coverage = count / S
    hole_thr = max(4, int(0.03 * S))
    hole = (count < hole_thr)
    plate_u8 = np.clip(plate, 0, 255).astype(np.uint8)

    plate_raw = plate_u8.copy()
    plate_raw[hole] = (255, 0, 255)
    cv2.imwrite(os.path.join(out_dir, "plate_raw.png"), plate_raw)
    cv2.imwrite(os.path.join(out_dir, "coverage.png"),
                (coverage * 255).astype(np.uint8))
    cv2.imwrite(os.path.join(out_dir, "mask_union.png"), fg_union * 255)

    inpaint_ratio = float(hole.mean())
    flags = cv2.INPAINT_TELEA if args.inpaint == "telea" else cv2.INPAINT_NS
    plate_inp = cv2.inpaint(plate_u8, (hole * 255).astype(np.uint8),
                            args.inpaint_radius, flags)
    soft = cv2.GaussianBlur(plate_inp, (0, 0), 1.2)
    m = hole > 0
    plate_inp[m] = soft[m]

    stats = {
        "mode": al["mode"], "S": S,
        "align": al["stats"],
        "coverage_p05": round(float(np.percentile(coverage, 5)), 3),
        "coverage_p50": round(float(np.percentile(coverage, 50)), 3),
        "inpaint_ratio": round(inpaint_ratio, 4),
    }
    if always_fg is not None:
        stats["always_fg_ratio"] = round(float(always_fg.mean()), 4)
    np.save(os.path.join(work_dir, "plate_f32.npy"), plate)
    json.dump(stats, open(os.path.join(work_dir, "composite.json"), "w"), indent=1)
    return plate_inp, stats, coverage, hole, fg_union, samples_ref(al)


def samples_ref(al):
    return al["samples"]


# ---------------------------------------------------------------- 阶段: verify

def birefnet_fg_ratio(img_path, meta, work_dir, tag):
    W, H = meta["w"], meta["h"]
    S = max(W, H)
    x0, y0 = (S - W) // 2, (S - H) // 2
    # LoadImage 对服务启动后新增文件有缓存问题 -> 统一走 VHS_LoadImages 目录加载
    frames_dir = os.path.join("input", "bgplate", f"verify_{tag}")
    os.makedirs(frames_dir, exist_ok=True)
    shutil.copy2(img_path, os.path.join(frames_dir, "img.png"))
    prefix = f"{os.path.relpath(work_dir, 'output').replace(os.sep, '/')}/verify/{tag}"
    wf = {
        "1": {"class_type": "VHS_LoadImages", "inputs": {
            "directory": os.path.abspath(frames_dir), "image_load_cap": 0,
            "skip_first_images": 0, "select_every_nth": 1}},
        "2": {"class_type": "ResizeAndPadImage", "inputs": {
            "image": ["1", 0], "target_width": S, "target_height": S,
            "padding_color": "black", "interpolation": "lanczos"}},
        "3": {"class_type": "LoadBackgroundRemovalModel", "inputs": {
            "bg_removal_name": "BiRefNet-general.safetensors"}},
        "4": {"class_type": "RemoveBackground", "inputs": {
            "bg_removal_model": ["3", 0], "image": ["2", 0]}},
        "5": {"class_type": "CropMask", "inputs": {
            "mask": ["4", 0], "x": x0, "y": y0, "width": W, "height": H}},
        "6": {"class_type": "MaskToImage", "inputs": {"mask": ["5", 0]}},
        "7": {"class_type": "SaveImage", "inputs": {
            "images": ["6", 0], "filename_prefix": prefix}},
    }
    submit_workflow(wf)
    files = sorted(glob.glob(os.path.join(work_dir, "verify", f"{tag}_*.png")))
    shutil.rmtree(frames_dir, ignore_errors=True)
    if not files:
        raise RuntimeError("verify 掩码未产出")
    mk = cv2.imread(files[-1], cv2.IMREAD_GRAYSCALE)
    fg = (mk > 127).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg)
    largest = 0 if n <= 1 else int(st[1:, cv2.CC_STAT_AREA].max())
    return float(fg.mean()), largest / (W * H)


def contact_sheet(out_dir, meta, work_dir, samples):
    W, H = meta["w"], meta["h"]
    ref_path = os.path.join(meta["frames_dir"], f"f_{samples[len(samples) // 2] + 1:05d}.png")
    ref = cv2.imread(ref_path)
    cov = cv2.imread(os.path.join(out_dir, "coverage.png"), cv2.IMREAD_GRAYSCALE)
    cov3 = cv2.applyColorMap(cov, cv2.COLORMAP_VIRIDIS)
    raw = cv2.imread(os.path.join(out_dir, "plate_raw.png"))
    plate = cv2.imread(os.path.join(out_dir, "plate.png"))
    pad = 8
    cell_w, cell_h = W, H
    sheet = np.zeros((2 * cell_h + 3 * pad + 30, 2 * cell_w + 3 * pad, 3), np.uint8)
    sheet[:] = (24, 24, 24)
    pos = [(pad, pad + 30), (pad * 2 + cell_w, pad + 30),
           (pad, pad * 2 + cell_h + 30), (pad * 2 + cell_w, pad * 2 + cell_h + 30)]
    for img, (x, y) in zip([ref, cov3, raw, plate], pos):
        sheet[y:y + cell_h, x:x + cell_w] = img
    for txt, (x, y) in zip(["source ref frame", "coverage", "plate_raw (magenta=hole)",
                            "plate (final)"], pos):
        cv2.putText(sheet, txt, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(os.path.join(out_dir, "contact_sheet.jpg"), sheet,
                [cv2.IMWRITE_JPEG_QUALITY, 88])


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--stage", default="all",
                    choices=["extract", "mask", "align", "composite", "verify", "all"])
    ap.add_argument("--chunk", type=int, default=104)
    ap.add_argument("--max-samples", type=int, default=120)
    ap.add_argument("--dilate", type=int, default=11)
    ap.add_argument("--tile", type=int, default=256)
    ap.add_argument("--refine", type=int, default=1)
    ap.add_argument("--inpaint", default="telea", choices=["telea", "ns"])
    ap.add_argument("--inpaint-radius", type=int, default=5)
    ap.add_argument("--static-thresh", type=float, default=1.5)
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--force-mask", action="store_true")
    args = ap.parse_args()

    out_root = args.out_root or os.path.join("output", args.date)
    out_dir = os.path.join(out_root, f"bg_plate_{args.slug}")
    work_dir = os.path.join(out_dir, "_work")
    os.makedirs(work_dir, exist_ok=True)
    global LOG_PATH
    LOG_PATH = os.path.join(out_dir, "extract.log")

    t_start = time.time()
    report = {"slug": args.slug, "source_video": os.path.abspath(args.video)}

    meta_path = os.path.join(work_dir, "meta.json")
    if args.stage in ("extract", "all") or not os.path.exists(meta_path):
        meta = stage_extract(args, out_dir, work_dir)
    else:
        meta = json.load(open(meta_path))
    report.update({"width": meta["w"], "height": meta["h"],
                   "frames": meta["frames"], "source_sha256": meta.get("sha256")})

    if args.stage in ("mask", "all"):
        stage_masks(args, meta, out_dir, work_dir)
    if not os.path.exists(os.path.join(work_dir, "masks_u8.npy")):
        raise SystemExit("缺少掩码缓存，请先跑 --stage mask")

    samples = None
    if args.stage in ("align", "all"):
        samples = stage_align(args, meta, work_dir)
    al_path = os.path.join(work_dir, "align.json")
    if samples is None:
        al = json.load(open(al_path))
        samples = al["samples"]

    if args.stage in ("composite", "all"):
        plate, stats, coverage, hole, fg_union, _ = composite(args, meta, work_dir, out_dir)
        cv2.imwrite(os.path.join(out_dir, "plate.png"), plate)
    else:
        stats = json.load(open(os.path.join(work_dir, "composite.json")))
        plate = cv2.imread(os.path.join(out_dir, "plate.png"))
        coverage = cv2.imread(os.path.join(out_dir, "coverage.png"),
                              cv2.IMREAD_GRAYSCALE) / 255.0

    # ---- verify 指标
    gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_luma = float(gray.mean())
    std = float(gray.std())
    person_ratio, person_max = birefnet_fg_ratio(
        os.path.join(out_dir, "plate.png"), meta, work_dir, "plate")

    fails, warns = [], []
    if not (8 < mean_luma < 248 and std > 8):
        fails.append("plate 黑图/纯色")
    stats["inpaint_ratio"] = stats.get("inpaint_ratio", 0)
    if stats["inpaint_ratio"] > 0.30:
        fails.append(f"洞占比 {stats['inpaint_ratio']:.1%} > 30%")
    elif stats["inpaint_ratio"] > 0.15:
        warns.append(f"洞占比 {stats['inpaint_ratio']:.1%} > 15%")
    if stats.get("always_fg_ratio", 0) > 0.08 and stats["mode"] == "static":
        fails.append(f"static 模式人物永久覆盖 {stats['always_fg_ratio']:.1%}")
    if person_ratio > 0.05:
        fails.append(f"疑似人物残留/主体过大 {person_ratio:.2%} > 5%")
    elif person_ratio > 0.004:
        warns.append(f"人物残留 {person_ratio:.2%} > 0.4%")
    if lap_var < 60:
        fails.append(f"清晰度过低 lap_var={lap_var:.0f} < 60")
    if stats["align"].get("identity", 0) > 0.1 * stats["S"]:
        warns.append("超 10% 样本配准失败(identity)")

    verdict = "fail" if fails else ("warn" if warns else "pass")
    report.update({
        "samples_used": stats["S"],
        "mode": stats["mode"],
        "align": stats["align"],
        "coverage": {"p05": stats["coverage_p05"], "p50": stats["coverage_p50"]},
        "always_fg_ratio": stats.get("always_fg_ratio"),
        "inpaint_ratio": stats["inpaint_ratio"],
        "quality": ("inpainted" if stats["inpaint_ratio"] > 0 else "clean"),
        "metrics": {"lap_var": round(lap_var, 1), "mean_luma": round(mean_luma, 1),
                    "std": round(std, 1),
                    "person_residual_ratio": round(person_ratio, 5),
                    "person_residual_largest": round(person_max, 5)},
        "verdict": verdict,
        "fail_reasons": fails,
        "warn_reasons": warns,
        "elapsed_sec": round(time.time() - t_start, 1),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "SOURCE.txt"), "w", encoding="utf-8") as f:
        f.write(f"source: {os.path.abspath(args.video)}\nsha256: {report['source_sha256']}\n"
                f"verdict: {verdict}\ngenerated: {report['generated_at']}\n")

    contact_sheet(out_dir, meta, work_dir, samples)

    if verdict == "fail" and os.path.exists(os.path.join(out_dir, "plate.png")):
        os.remove(os.path.join(out_dir, "plate.png"))

    # 沙箱对批量删除有守卫 -> 默认保留 _work 缓存与抽帧目录, 需要时手动清理
    log("保留 _work 缓存与抽帧目录 (手动清理可省 ~700MB 磁盘)")

    log(f"verdict={verdict} inpaint_ratio={stats['inpaint_ratio']:.1%} "
        f"person_residual={person_ratio:.2%} lap_var={lap_var:.0f} "
        f"耗时 {report['elapsed_sec']}s")
    for r in fails:
        print(f"FAIL_REASON={r}")
    sys.exit(2 if verdict == "fail" else 0)


if __name__ == "__main__":
    main()
