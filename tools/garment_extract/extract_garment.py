# -*- coding: utf-8 -*-
"""
视频服装提取驱动脚本 v2。
流水线: ffmpeg 抽清晰关键帧 -> ComfyUI ATR 人体解析(服装类别掩码) -> SAM2 边缘精修 -> 纯净服装 PNG。

用法:
    python extract_garment.py <视频目录> [--top 3] [--frames 12] [--server http://127.0.0.1:8188]

输出:
    output/<日期>/garment_extract/<视频名>/
        keyframes/   候选关键帧
        garment/     garment_<n>_transparent.png / garment_<n>_white.png
        manifest.json
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid

import numpy as np
from PIL import Image, ImageFilter

SERVER = "http://127.0.0.1:8188"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- ComfyUI API

def api_post(path, payload):
    req = urllib.request.Request(
        SERVER + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def api_upload_image(png_path):
    boundary = uuid.uuid4().hex
    fname = os.path.basename(png_path)
    with open(png_path, "rb") as f:
        data = f.read()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{fname}"\r\n'.encode(),
        b"Content-Type: image/png\r\n\r\n",
        data,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        SERVER + "/upload/image", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())["name"]

def api_wait_prompt(prompt_id, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        with urllib.request.urlopen(SERVER + f"/history/{prompt_id}", timeout=15) as r:
            hist = json.loads(r.read().decode())
        if prompt_id in hist:
            status = hist[prompt_id].get("status", {})
            if not status.get("completed", False) and status.get("status_str") == "error":
                raise RuntimeError(f"workflow error for {prompt_id}: {json.dumps(status)[:800]}")
            return hist[prompt_id]
        time.sleep(1.0)
    raise TimeoutError(f"prompt {prompt_id} timed out")

def api_download_image(hist_item, node_id, dest_path):
    info = hist_item["outputs"][node_id]["images"][0]
    q = f"/view?filename={urllib.parse.quote(info['filename'])}&subfolder={urllib.parse.quote(info.get('subfolder',''))}&type={info['type']}"
    with urllib.request.urlopen(SERVER + q, timeout=60) as r:
        with open(dest_path, "wb") as f:
            f.write(r.read())

def run_workflow(wf, out_map, dest_dir, base):
    """提交 workflow, 按 out_map{node_id: suffix} 下载多个输出, 返回 {suffix: path}。"""
    p = api_post("/prompt", {"prompt": {k: v for k, v in wf.items() if isinstance(v, dict)}})
    hist = api_wait_prompt(p["prompt_id"])
    out = {}
    for node_id, suffix in out_map.items():
        dest = os.path.join(dest_dir, f"{base}_{suffix}.png")
        api_download_image(hist, node_id, dest)
        out[suffix] = dest
    return out

# ---------------------------------------------------------------- Stage 1: 抽帧

def extract_keyframes(video, out_dir, sample_fps=4, top_n=12):
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="gkf_")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", video, "-vf", f"fps={sample_fps}",
             "-q:v", "2", os.path.join(tmp, "f_%04d.jpg")],
            check=True)
        cand = sorted(f for f in os.listdir(tmp) if f.endswith(".jpg"))
        if not cand:
            raise RuntimeError(f"ffmpeg produced no frames for {video}")
        arrs = [np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), np.float32) for f in cand]

        def sharpness(a):
            lap = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1) - 4 * a)
            return float(lap.var())

        scores = [sharpness(a) for a in arrs]
        picked = []
        for i in sorted(range(len(cand)), key=lambda i: -scores[i]):
            if len(picked) >= top_n:
                break
            if all(float(np.abs(arrs[i] - arrs[j]).mean()) >= 4.0 for j in picked):
                picked.append(i)
        picked.sort()
        out = []
        for rank, i in enumerate(picked):
            dst = os.path.join(out_dir, f"frame_{rank:02d}.jpg")
            shutil.copy(os.path.join(tmp, cand[i]), dst)
            out.append((dst, scores[i]))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- 工具

def largest_region(mask):
    try:
        from scipy import ndimage
        lab, n = ndimage.label(mask)
        if n <= 1:
            return mask
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        return lab == (int(np.argmax(sizes)) + 1)
    except ImportError:
        return mask

def compose_rgba(img, mask01):
    rgba = np.dstack([np.asarray(img.convert("RGB")), (mask01 * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA")

# ---------------------------------------------------------------- 主流程

def main():
    global SERVER
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    args = ap.parse_args()
    SERVER = args.server.rstrip("/")

    out_root = os.path.join("output", time.strftime("%Y-%m-%d"), "garment_extract")
    videos = [os.path.join(args.input_dir, f) for f in sorted(os.listdir(args.input_dir))
              if f.lower().endswith(".mp4")]
    if not videos:
        sys.exit(f"no mp4 in {args.input_dir}")

    with open(os.path.join(HERE, "workflow_pass2.json")) as f:
        wf = json.load(f)

    manifest = []
    for video in videos:
        vname = os.path.splitext(os.path.basename(video))[0]
        vout = os.path.join(out_root, vname)
        kf_dir = os.path.join(vout, "keyframes")
        raw_dir = os.path.join(vout, "masks_raw")
        g_dir = os.path.join(vout, "garment")
        for d in (kf_dir, raw_dir, g_dir):
            os.makedirs(d, exist_ok=True)
        print(f"\n=== {vname} ===")

        keyframes = extract_keyframes(video, kf_dir, top_n=args.frames)
        print(f"stage1: {len(keyframes)} keyframes")

        results = []
        for kf_path, sharp in keyframes:
            base = os.path.splitext(os.path.basename(kf_path))[0]
            try:
                srv_name = api_upload_image(kf_path)
                wf["1"]["inputs"]["image"] = srv_name
                outs = run_workflow(wf, {"4": "atr", "8": "sam2"}, raw_dir, base)

                atr = np.asarray(Image.open(outs["atr"]).convert("L"), np.float32) / 255.0
                atr_m = atr > 0.5
                atr_area = float(atr_m.sum())
                if atr_area < 2000:
                    print(f"  {base}: ATR garment mask too small, skip")
                    continue

                sam2 = np.asarray(Image.open(outs["sam2"]).convert("L"), np.float32) / 255.0
                sam2_m = largest_region(sam2 > 0.5)
                sam2_area = float(sam2_m.sum())
                # SAM2 精修掩码与 ATR 掩码面积差在 30% 内才可信, 否则回退 ATR(轻度羽化)
                if 0.7 * atr_area <= sam2_area <= 1.3 * atr_area and sam2_area > 2000:
                    garment_m, method = sam2_m, "atr+sam2"
                else:
                    a = Image.fromarray((atr_m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
                    garment_m = np.asarray(a, np.float32) / 255.0
                    garment_m = np.clip((garment_m - 0.3) / 0.4, 0, 1)
                    method = "atr_only"

                ys, xs = np.where(garment_m > 0.5)
                gy0, gy1, gx0, gx1 = ys.min(), ys.max(), xs.min(), xs.max()
                pad_y, pad_x = int((gy1 - gy0) * 0.08), int((gx1 - gx0) * 0.08)
                H, W = garment_m.shape
                box = (max(0, gx0 - pad_x), max(0, gy0 - pad_y), min(W, gx1 + pad_x), min(H, gy1 + pad_y))

                crop_rgba = compose_rgba(Image.open(kf_path), garment_m).crop(box)
                white = Image.new("RGB", crop_rgba.size, (255, 255, 255))
                white.paste(crop_rgba, (0, 0), crop_rgba)
                area = float((garment_m > 0.5).sum())
                results.append({"base": base, "sharp": sharp, "area": area, "method": method,
                                "bbox": [int(v) for v in box], "rgba": crop_rgba, "white": white})
                print(f"  {base}: ok ({method}, atr={atr_area:.0f}, sam2={sam2_area:.0f}, sharp={sharp:.1f})")
            except Exception as e:
                print(f"  {base}: FAILED {type(e).__name__}: {e}")

        results.sort(key=lambda r: -(r["sharp"] * np.sqrt(r["area"])))
        for rank, r in enumerate(results[: args.top], 1):
            r["rgba"].save(os.path.join(g_dir, f"garment_{rank}_transparent.png"))
            r["white"].save(os.path.join(g_dir, f"garment_{rank}_white.png"))
            manifest.append({
                "video": os.path.basename(video), "rank": rank,
                "source_frame": r["base"], "sharpness": round(r["sharp"], 2),
                "mask_area": round(r["area"]), "method": r["method"],
                "crop_bbox": r["bbox"],
                "files": [f"garment_{rank}_transparent.png", f"garment_{rank}_white.png"],
            })
        print(f"saved top {min(args.top, len(results))} garments -> {g_dir}")

    mf = os.path.join(out_root, "manifest.json")
    with open(mf, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nmanifest -> {mf}")

if __name__ == "__main__":
    main()
