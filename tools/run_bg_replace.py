#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方案 A 换背景: BiRefNet 掩码 (ComfyUI) + ffmpeg 像素级合成。

引擎说明:
  ffmpeg (默认): ComfyUI 只产 312 帧掩码 PNG, 合成用 ffmpeg alphamerge+overlay,
                 单次编码无 VHS 色彩矩阵偏移, 人物区 PSNR ~44dB
  comfy:        旧路径, ImageCompositeMasked 在图内合成 (有 ~1.5% 全局色偏)

用法:
  venv/Scripts/python.exe tools/run_bg_replace.py \
      --video "output/.../xxx-audio.mp4" --slug ayano_dcab \
      --bg background_library/backgrounds/bg_studio_cyc_grey/main.png \
      --prefix "2026-10-17/bgswap/ayano_studio_v1"
"""
import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

import cv2
import numpy as np
from skimage.metrics import structural_similarity

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMFY = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def submit_workflow(wf, timeout=1500, poll=3.0):
    body = json.dumps({"prompt": wf, "client_id": uuid.uuid4().hex}).encode()
    req = urllib.request.Request(f"{COMFY}/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(OPENER.open(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"/prompt 400: {e.read().decode(errors='replace')[:2000]}")
    pid = resp["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(poll)
        hist = json.loads(OPENER.open(f"{COMFY}/history/{pid}", timeout=15).read())
        if pid not in hist:
            continue
        st = hist[pid].get("status", {})
        if st.get("status_str") == "error":
            raise RuntimeError(f"执行错误: {json.dumps(st)[:1500]}")
        if st.get("completed"):
            return hist[pid]
    raise RuntimeError(f"任务超时 ({timeout}s)")


def ffprobe_video(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
           "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
           "-of", "json", path]
    st = json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                   check=True).stdout)["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    return {"w": st["width"], "h": st["height"],
            "fps": float(num) / float(den), "frames": int(st["nb_read_frames"])}


def ffprobe_audio_duration(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0",
           "-show_entries", "stream=duration", "-of", "json", path]
    try:
        st = json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                       check=True).stdout)["streams"]
        return float(st[0]["duration"]) if st else None
    except Exception:
        return None


def comfy_mask_sequence(video_rel, out_prefix, W, H):
    """对整段视频跑 BiRefNet, 掩码落成 PNG 序列, 返回文件列表。"""
    S = max(W, H)
    x0, y0 = (S - W) // 2, (S - H) // 2
    wf = {
        "1": {"class_type": "VHS_LoadVideo", "inputs": {
            "video": video_rel, "force_rate": 0, "custom_width": 0,
            "custom_height": 0, "frame_load_cap": 0, "skip_first_frames": 0,
            "select_every_nth": 1, "format": "AnimateDiff"}},
        "20": {"class_type": "ResizeAndPadImage", "inputs": {
            "image": ["1", 0], "target_width": S, "target_height": S,
            "padding_color": "black", "interpolation": "lanczos"}},
        "4": {"class_type": "LoadBackgroundRemovalModel", "inputs": {
            "bg_removal_name": "BiRefNet-general.safetensors"}},
        "5": {"class_type": "RemoveBackground", "inputs": {
            "bg_removal_model": ["4", 0], "image": ["20", 0]}},
        "21": {"class_type": "CropMask", "inputs": {
            "mask": ["5", 0], "x": x0, "y": y0, "width": W, "height": H}},
        "6": {"class_type": "MaskToImage", "inputs": {"mask": ["21", 0]}},
        "7": {"class_type": "SaveImage", "inputs": {
            "images": ["6", 0], "filename_prefix": out_prefix}},
    }
    submit_workflow(wf)
    files = sorted(glob.glob(os.path.join("output", out_prefix + "_*.png")))
    return files


def comfy_masks_for_dir(frames_dir, out_prefix, W, H):
    """对目录图片跑 BiRefNet (锚点/验证用), 返回掩码文件列表。"""
    S = max(W, H)
    x0, y0 = (S - W) // 2, (S - H) // 2
    wf = {
        "1": {"class_type": "VHS_LoadImages", "inputs": {
            "directory": os.path.abspath(frames_dir), "image_load_cap": 0,
            "skip_first_images": 0, "select_every_nth": 1}},
        "2": {"class_type": "ResizeAndPadImage", "inputs": {
            "image": ["1", 0], "target_width": S, "target_height": S,
            "padding_color": "black", "interpolation": "lanczos"}},
        "4": {"class_type": "LoadBackgroundRemovalModel", "inputs": {
            "bg_removal_name": "BiRefNet-general.safetensors"}},
        "5": {"class_type": "RemoveBackground", "inputs": {
            "bg_removal_model": ["4", 0], "image": ["2", 0]}},
        "21": {"class_type": "CropMask", "inputs": {
            "mask": ["5", 0], "x": x0, "y": y0, "width": W, "height": H}},
        "6": {"class_type": "MaskToImage", "inputs": {"mask": ["21", 0]}},
        "7": {"class_type": "SaveImage", "inputs": {
            "images": ["6", 0], "filename_prefix": out_prefix}},
    }
    submit_workflow(wf)
    return sorted(glob.glob(os.path.join("output", out_prefix + "_*.png")))


def estimate_anchor(video, W, H, anchor_root, out_prefix):
    """抽 5 帧 -> BiRefNet 掩码 -> feet_y/head_y (归一化)。"""
    frames_dir = os.path.join(anchor_root, "frames")
    shutil.rmtree(anchor_root, ignore_errors=True)
    os.makedirs(frames_dir, exist_ok=True)
    cap = cv2.VideoCapture(video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    for i, fi in enumerate([int(round(total * f)) for f in (0.05, 0.3, 0.5, 0.7, 0.95)]):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, fr = cap.read()
        if ok:
            cv2.imwrite(os.path.join(frames_dir, f"f_{i + 1:02d}.png"), fr)
    cap.release()

    masks = comfy_masks_for_dir(frames_dir, out_prefix, W, H)
    bottoms, tops, cxs = [], [], []
    for fp in masks:
        m = (cv2.imread(fp, cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)
        if m.sum() < 0.01 * W * H:
            continue
        ys, xs = np.where(m > 0)
        bottoms.append(ys.max())
        tops.append(ys.min())
        cxs.append(xs.mean())
    shutil.rmtree(anchor_root, ignore_errors=True)
    if not bottoms:
        return {"feet_y": 0.93, "head_y": 0.05, "cx": 0.5, "person_h": 0.88,
                "estimated": False}
    feet_y = min(float(np.percentile(bottoms, 90)) / H, 0.995)
    head_y = float(np.percentile(tops, 10)) / H
    return {"feet_y": round(feet_y, 4), "head_y": round(head_y, 4),
            "cx": round(float(np.median(cxs)) / W, 4),
            "person_h": round(feet_y - head_y, 4), "estimated": True}


def estimate_ground_y(bg):
    g = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    H = g.shape[0]
    roi = g[int(H * 0.4):, :]
    sob = np.abs(cv2.Sobel(roi, cv2.CV_64F, 0, 1, ksize=3)).sum(axis=1)
    sob = np.convolve(sob, np.ones(9) / 9.0, mode="same")
    row = int(np.argmax(sob)) + int(H * 0.4)
    return min(max(row / H, 0.4), 0.95)


def prep_background(bg_path, W, H, feet_y, ground_y, out_path):
    bg = cv2.imread(bg_path)
    if bg is None:
        raise RuntimeError(f"背景图读取失败: {bg_path}")
    dy = (feet_y - ground_y) * H
    s = max(1.0, 1.0 + 2.0 * abs(dy) / H)
    sw, sh = int(round(W * s)), int(round(H * s))
    interp = cv2.INTER_LANCZOS4 if s > 1.001 else cv2.INTER_AREA
    scaled = cv2.resize(bg, (sw, sh), interpolation=interp)
    y0 = int(round(ground_y * H * s - feet_y * H))
    y0 = int(np.clip(y0, 0, sh - H))
    x0 = (sw - W) // 2
    crop = scaled[y0:y0 + H, x0:x0 + W]
    if crop.shape[0] != H or crop.shape[1] != W:
        crop = cv2.resize(crop, (W, H), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(out_path, crop)
    return {"scale": round(s, 4), "bg_ground_y": round(ground_y, 4),
            "feet_y": round(feet_y, 4), "dy_px": int(round(dy)), "crop_y0": y0}


def ffmpeg_composite(bg_png, src_mp4, mask_files, out_mp4, crf, W, H, fps):
    """alphamerge+overlay: mask=1 处显示 src(人物), mask=0 处显示 bg。

    mask PNG 是 MaskToImage 的灰度复制(RGB 三通道等值), format=gray 后取值不变。
    negate 后 alpha 在背景区为 255 -> bg 盖在 src 上; 人物区 alpha=0 -> src 直通。
    """
    dur = len(mask_files) / fps + 0.5
    base = mask_files[0][:mask_files[0].rfind("_", 0, mask_files[0].rfind("_"))]
    mask_pat = base + "_%05d_.png"
    fc = (
        f"[0:v]scale={W}:{H},format=gbrp,setsar=1[bg0];"
        f"[2:v]format=gray,negate,setsar=1[m0];"
        f"[bg0][m0]alphamerge[bga];"
        f"[1:v]format=gbrp,setsar=1[src0];"
        f"[src0][bga]overlay=format=gbrp[v]"
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", f"{fps:.5f}", "-t", f"{dur:.3f}", "-i", bg_png,
        "-i", src_mp4,
        "-framerate", f"{fps:.5f}", "-start_number", "1", "-i", mask_pat,
        "-filter_complex", fc,
        "-map", "[v]", "-map", "1:a?",
        "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-c:a", "copy", out_mp4,
    ]
    subprocess.run(cmd, check=True)


def psnr_masked(a, b, mask):
    diff = (a.astype(np.float64) - b.astype(np.float64)) ** 2
    m = mask > 0
    if not m.any():
        return 99.0
    mse = diff[m].mean()
    if not np.isfinite(mse) or mse == 0:
        return 99.0
    return 10 * np.log10(255.0 ** 2 / mse)


def verify_output(out_path, src_path, meta, mask_files, bg_prep_path, dbg_dir):
    fails, warns = [], []
    om = ffprobe_video(out_path)
    if om["frames"] != meta["frames"]:
        fails.append(f"帧数 {om['frames']} != {meta['frames']}")
    if (om["w"], om["h"]) != (meta["w"], meta["h"]):
        fails.append(f"分辨率 {om['w']}x{om['h']} != {meta['w']}x{meta['h']}")
    a_out = ffprobe_audio_duration(out_path)
    a_src = ffprobe_audio_duration(src_path)
    if a_out is None:
        fails.append("音轨丢失")
    elif a_src and abs(a_out - a_src) > 0.05:
        warns.append(f"音轨时长差 {abs(a_out - a_src):.3f}s")

    cap = cv2.VideoCapture(out_path)
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % 10 == 0:
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            if g.mean() < 5 or g.std() < 5:
                fails.append(f"第 {i} 帧疑似黑帧 (mean={g.mean():.1f})")
                cv2.imwrite(os.path.join(dbg_dir, f"black_{i:04d}.png"), fr)
        i += 1
    cap.release()

    W, H = meta["w"], meta["h"]
    idxs = [int(round(meta["frames"] * f)) for f in (0.1, 0.35, 0.6, 0.85, 0.98)]
    bg_prep = cv2.imread(bg_prep_path)
    g_bgp = cv2.cvtColor(bg_prep, cv2.COLOR_BGR2GRAY)
    cap_s = cv2.VideoCapture(src_path)
    cap_o = cv2.VideoCapture(out_path)
    for i in idxs:
        cap_s.set(cv2.CAP_PROP_POS_FRAMES, i)
        cap_o.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok1, src = cap_s.read()
        ok2, out = cap_o.read()
        if not (ok1 and ok2) or i >= len(mask_files):
            continue
        m = cv2.imread(mask_files[i], cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        person = (m > 0.98).astype(np.uint8)
        interior = cv2.erode(person, np.ones((9, 9), np.uint8)) > 0
        bg = ~(cv2.dilate((m > 0.3).astype(np.uint8),
                          np.ones((25, 25), np.uint8)) > 0)
        g_src = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        g_out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        _, ssim_map = structural_similarity(g_src, g_out, data_range=255, full=True)
        _, ssim_bg = structural_similarity(g_out, g_bgp, data_range=255, full=True)
        p_psnr = psnr_masked(src, out, interior.astype(np.uint8))
        p_ssim = float(ssim_map[interior].mean()) if interior.any() else 1.0
        b_mae = float(np.abs(src[bg].astype(np.float64) - out[bg]).mean()) if bg.any() else 0.0
        b_psnr = psnr_masked(src, out, bg.astype(np.uint8))
        b_plate_ssim = float(ssim_bg[bg].mean()) if bg.any() else 0.0

        tag = f"f{i:04d}"
        if p_psnr < 40:
            fails.append(f"{tag} 人物区 PSNR {p_psnr:.1f} < 40 (人物被改动)")
        elif p_psnr < 42:
            warns.append(f"{tag} 人物区 PSNR {p_psnr:.1f} < 42")
        if p_ssim < 0.98:
            fails.append(f"{tag} 人物区 SSIM {p_ssim:.4f} < 0.98")
        if b_psnr > 35:
            fails.append(f"{tag} 背景区 PSNR {b_psnr:.1f} > 35 (背景没换)")
        if b_mae < 8:
            fails.append(f"{tag} 背景区 MAE {b_mae:.1f} < 8 (背景没换)")
        if b_plate_ssim < 0.55:
            warns.append(f"{tag} 输出背景与目标板 SSIM {b_plate_ssim:.3f} < 0.55")
        if fails:
            sheet = np.hstack([src, out])
            cv2.putText(sheet, f"p={p_psnr:.1f} b={b_psnr:.1f} mae={b_mae:.1f}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            cv2.imwrite(os.path.join(dbg_dir, f"diff_{tag}.jpg"), sheet)
        log(f"  {tag}: person(interior) PSNR={p_psnr:.1f} SSIM={p_ssim:.4f} | "
            f"bg PSNR={b_psnr:.1f} MAE={b_mae:.1f} plateSSIM={b_plate_ssim:.3f}")
    cap_s.release()
    cap_o.release()
    return fails, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--bg", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--engine", default="ffmpeg", choices=["ffmpeg", "comfy"])
    ap.add_argument("--bg-ground-y", type=float, default=None)
    ap.add_argument("--feet-y", type=float, default=None)
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--no-verify", dest="verify", action="store_false")
    ap.add_argument("--keep-masks", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    src_copy = os.path.join("input", "bgswap", f"{args.slug}_src.mp4")
    os.makedirs("input/bgswap", exist_ok=True)
    if os.path.abspath(args.video) != os.path.abspath(src_copy):
        shutil.copy2(args.video, src_copy)
    meta = ffprobe_video(src_copy)
    W, H = meta["w"], meta["h"]
    fps = meta["fps"]
    log(f"源: {W}x{H}, {meta['frames']} 帧 @ {fps:.2f}fps, engine={args.engine}")

    base = os.path.dirname(args.prefix)  # e.g. 2026-10-17/bgswap
    dbg_dir = os.path.join("output", base, "_verify")
    os.makedirs(dbg_dir, exist_ok=True)

    if args.feet_y:
        anchor = {"feet_y": args.feet_y, "estimated": False}
    else:
        anchor = estimate_anchor(
            src_copy, W, H,
            os.path.join("input", "bgswap", "_anchor", args.slug),
            f"{args.prefix}_anchor")
        log(f"锚点: feet_y={anchor['feet_y']:.3f} head_y={anchor.get('head_y', 0):.3f} "
            f"person_h={anchor.get('person_h', 0):.3f}")

    bg = cv2.imread(args.bg)
    gy = args.bg_ground_y if args.bg_ground_y is not None else estimate_ground_y(bg)
    bg_out = os.path.join("input", "bgswap", f"{args.slug}_bg.png")
    align_info = prep_background(args.bg, W, H, anchor["feet_y"], gy, bg_out)
    log(f"背景对位: {align_info} (ground_y 自动估算={args.bg_ground_y is None})")

    out_path = os.path.join("output", args.prefix + ".mp4")
    if args.engine == "ffmpeg":
        # 唯一前缀避免 SaveImage 计数器接续旧文件; 掩码默认保留(沙箱禁批量删除)
        mask_prefix = args.prefix + f"_masks_{datetime.datetime.now().strftime('%H%M%S')}"
        log("生成掩码序列 (ComfyUI BiRefNet)...")
        mask_files = comfy_mask_sequence(f"bgswap/{args.slug}_src.mp4",
                                         mask_prefix, W, H)
        if len(mask_files) != meta["frames"]:
            raise RuntimeError(f"掩码数 {len(mask_files)} != {meta['frames']}")
        log(f"掩码 {len(mask_files)} 帧, ffmpeg 合成...")
        ffmpeg_composite(bg_out, src_copy, mask_files, out_path,
                         args.crf, W, H, fps)
    else:
        tpl = "workflows/v1/bg_replace_sample_api.json"
        wf = json.load(open(tpl, encoding="utf-8"))
        wf["1"]["inputs"]["video"] = f"bgswap/{args.slug}_src.mp4"
        wf["10"]["inputs"]["image"] = f"bgswap/{args.slug}_bg.png"
        wf["12"]["inputs"]["amount"] = meta["frames"]
        wf["30"]["inputs"]["filename_prefix"] = args.prefix
        wf["30"]["inputs"]["crf"] = args.crf
        log(f"提交工作流 ({tpl}) ...")
        entry = submit_workflow(wf)
        gifs = entry.get("outputs", {}).get("30", {}).get("gifs", [])
        if not gifs:
            raise RuntimeError("未找到输出")
        out_path = gifs[0]["fullpath"]

    log(f"输出: {out_path} (渲染耗时 {time.time() - t0:.0f}s)")
    result = {"out": out_path, "align": align_info, "anchor": anchor,
              "frames": meta["frames"], "engine": args.engine}
    if args.verify:
        fails, warns = verify_output(out_path, src_copy, meta,
                                     mask_files if args.engine == "ffmpeg" else [],
                                     bg_out, dbg_dir)
        result["verify"] = {"fails": fails, "warns": warns,
                            "verdict": "fail" if fails else ("warn" if warns else "pass")}
        log(f"验收: {result['verify']['verdict']}")
        for f in fails:
            print(f"VERIFY_FAIL: {f}")
        for w in warns:
            print(f"VERIFY_WARN: {w}")
    if args.engine == "ffmpeg":
        log(f"掩码已保留: output/{mask_prefix}_*.png ({len(mask_files)} 张, 可手动清理)")
    json.dump(result, open(os.path.join(dbg_dir, f"result_{os.path.basename(args.prefix)}.json"),
                           "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(2 if (args.verify and result["verify"]["fails"]) else 0)


if __name__ == "__main__":
    main()
