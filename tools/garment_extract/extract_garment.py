# -*- coding: utf-8 -*-
"""
视频服装提取驱动脚本。
流水线: ffmpeg 抽清晰关键帧 -> ComfyUI BiRefNet 抠人像 -> SAM2 躯干锚点分割服装 -> 纯净服装 PNG。

用法:
    python extract_garment.py <视频目录> [--top 3] [--frames 12] [--server http://127.0.0.1:8188]

输出:
    output/<日期>/garment_extract/<视频名>/
        keyframes/          候选关键帧
        person_cutout/      人物透明抠图
        garment/            garment_<n>_transparent.png / garment_<n>_white.png
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
from PIL import Image

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
    """multipart 上传图片到 ComfyUI input 目录, 返回服务端文件名。"""
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

def run_workflow(wf, node_id, dest_path):
    """提交 workflow(单输出节点)并下载输出到 dest_path。"""
    p = api_post("/prompt", {"prompt": {k: v for k, v in wf.items() if isinstance(v, dict)}})
    hist = api_wait_prompt(p["prompt_id"])
    api_download_image(hist, node_id, dest_path)

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
        arrs = []
        for f in cand:
            im = np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), dtype=np.float32)
            arrs.append(im)
        # 拉普拉斯方差作为清晰度得分
        def sharpness(a):
            lap = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1) - 4 * a)
            return float(lap.var())
        scores = [sharpness(a) for a in arrs]
        # 近似重复帧去重: 与已选帧的平均绝对差过小则跳过
        picked = []
        order = sorted(range(len(cand)), key=lambda i: -scores[i])
        for i in order:
            if len(picked) >= top_n:
                break
            dup = False
            for j in picked:
                if float(np.abs(arrs[i] - arrs[j]).mean()) < 4.0:
                    dup = True
                    break
            if not dup:
                picked.append(i)
        picked.sort()  # 按时间顺序保存
        out = []
        for rank, i in enumerate(picked):
            dst = os.path.join(out_dir, f"frame_{rank:02d}.jpg")
            shutil.copy(os.path.join(tmp, cand[i]), dst)
            out.append((dst, scores[i], cand[i]))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------- Stage 3: 锚点

def torso_anchors(alpha):
    """由人像 alpha mask 推算躯干正样本点(SAM2 输入)。
    alpha: HxW float 0-1。返回 (points_json, person_bbox) 或 (None, None)。"""
    m = alpha > 0.5
    if m.sum() < 200:
        return None, None
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    h, cx = y1 - y0, (x0 + x1) // 2
    # 躯干锚点: 人像上沿往下 30% 与 45% 高度处(避开脸部, 命中胸/腰)
    p1 = (float(cx), float(y0 + 0.30 * h))
    p2 = (float(cx), float(y0 + 0.45 * h))
    coords = json.dumps([{"x": p1[0], "y": p1[1]}, {"x": p2[0], "y": p2[1]}])
    return coords, (int(x0), int(y0), int(x1), int(y1))

# ---------------------------------------------------------------- 工具

def largest_region(mask):
    """保留 mask 的最大连通域(纯 numpy 简易实现, 4-邻接 BFS)。"""
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

    with open(os.path.join(HERE, "workflow_pass1.json")) as f:
        wf1 = json.load(f)
    with open(os.path.join(HERE, "workflow_pass2.json")) as f:
        wf2 = json.load(f)

    manifest = []
    for video in videos:
        vname = os.path.splitext(os.path.basename(video))[0]
        vout = os.path.join(out_root, vname)
        kf_dir = os.path.join(vout, "keyframes")
        cut_dir = os.path.join(vout, "person_cutout")
        g_dir = os.path.join(vout, "garment")
        for d in (kf_dir, cut_dir, g_dir):
            os.makedirs(d, exist_ok=True)
        print(f"\n=== {vname} ===")

        # Stage 1
        keyframes = extract_keyframes(video, kf_dir, top_n=args.frames)
        print(f"stage1: {len(keyframes)} keyframes")

        results = []
        for kf_path, sharp, _ in keyframes:
            base = os.path.splitext(os.path.basename(kf_path))[0]
            try:
                # Stage 2: BiRefNet 人像 mask
                srv_name = api_upload_image(kf_path)
                wf1["1"]["inputs"]["image"] = srv_name
                mask_png = os.path.join(cut_dir, f"{base}_mask.png")
                run_workflow(wf1, "5", mask_png)
                alpha = np.asarray(Image.open(mask_png).convert("L"), np.float32) / 255.0
                # 弱 alpha 平滑成 0/1 附近的连续 alpha
                alpha = np.clip((alpha - 0.3) / 0.4, 0, 1)

                # 人物 cutout (alpha>0 即保存, 便于抽检)
                cut = compose_rgba(Image.open(kf_path), alpha)
                cut_path = os.path.join(cut_dir, f"{base}_cutout.png")
                cut.save(cut_path)

                # Stage 3: SAM2 躯干锚点 -> 服装 mask
                coords, bbox = torso_anchors(alpha)
                if coords is None:
                    print(f"  {base}: no person detected, skip")
                    continue
                wf2["1"]["inputs"]["image"] = srv_name
                wf2["3"]["inputs"]["coordinates_positive"] = coords
                gmask_png = os.path.join(g_dir, f"{base}_gmraw.png")
                run_workflow(wf2, "5", gmask_png)
                gm = np.asarray(Image.open(gmask_png).convert("L"), np.float32) / 255.0
                gm = (gm > 0.5)

                # Stage 4: 服装 mask ∩ 人像 alpha
                garment = largest_region(gm & (alpha > 0.5))
                area = float(garment.sum())
                if area < 2000:  # 锚点分割失败回退: 用人像躯干包围盒
                    x0, y0, x1, y1 = bbox
                    fallback = np.zeros_like(garment)
                    fy1, fy2 = y0 + int((y1 - y0) * 0.22), y0 + int((y1 - y0) * 0.85)
                    fallback[fy1:fy2, x0:x1 + 1] = alpha[fy1:fy2, x0:x1 + 1] > 0.5
                    garment, area = fallback, float(fallback.sum())
                    note = "fallback_bbox"
                else:
                    note = "sam2"

                # 裁剪 + 合成 (8% 边距)
                ys, xs = np.where(garment)
                if len(ys) == 0:
                    print(f"  {base}: empty garment mask, skip")
                    continue
                gy0, gy1, gx0, gx1 = ys.min(), ys.max(), xs.min(), xs.max()
                mh, mw = gy1 - gy0, gx1 - gx0
                pad_y, pad_x = int(mh * 0.08), int(mw * 0.08)
                H, W = garment.shape
                cy0, cy1 = max(0, gy0 - pad_y), min(H, gy1 + pad_y)
                cx0, cx1 = max(0, gx0 - pad_x), min(W, gx1 + pad_x)

                g_alpha = np.where(garment, alpha, 0.0)
                crop_rgba = compose_rgba(Image.open(kf_path), g_alpha).crop((cx0, cy0, cx1, cy1))
                white = Image.new("RGB", crop_rgba.size, (255, 255, 255))
                white.paste(crop_rgba, (0, 0), crop_rgba)
                results.append({
                    "base": base, "sharp": sharp, "area": area, "note": note,
                    "bbox": [int(cx0), int(cy0), int(cx1), int(cy1)],
                    "rgba": crop_rgba, "white": white,
                })
                print(f"  {base}: ok ({note}, area={area:.0f}, sharp={sharp:.1f})")
            except Exception as e:
                print(f"  {base}: FAILED {type(e).__name__}: {e}")

        # Top-N
        results.sort(key=lambda r: -(r["sharp"] * np.sqrt(r["area"])))
        for rank, r in enumerate(results[: args.top], 1):
            r["rgba"].save(os.path.join(g_dir, f"garment_{rank}_transparent.png"))
            r["white"].save(os.path.join(g_dir, f"garment_{rank}_white.png"))
            manifest.append({
                "video": os.path.basename(video), "rank": rank,
                "source_frame": r["base"], "sharpness": round(r["sharp"], 2),
                "mask_area": round(r["area"]), "method": r["note"],
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
