# -*- coding: utf-8 -*-
"""
本地推理版服装提取(不经 ComfyUI 服务器, 避免服务器不稳定)。
用 ComfyUI venv 运行: D:\\ai_projects\\ComfyUI\\venv\\Scripts\\python.exe local_garment.py <视频目录>

流水线与 extract_garment.py 相同:
ffmpeg 抽帧 -> ATR 人体解析(onnxruntime) -> SAM2 掩码精修(torch) -> clean_mask -> 纯净服装 PNG
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import importlib.util

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image, ImageFilter

ROOT = r"D:\ai_projects\ComfyUI"
SAM2_DIR = os.path.join(ROOT, "custom_nodes", "ComfyUI-segment-anything-2")
ATR_ONNX = os.path.join(ROOT, "models", "IDM-VTON", "humanparsing", "parsing_atr.onnx")
SAM2_MODEL = os.path.join(ROOT, "models", "sam2", "sam2_hiera_base_plus.safetensors")
SAM2_CFG = os.path.join(SAM2_DIR, "sam2_configs", "sam2_hiera_b+.yaml")

CLOTH_IDS = [4, 5, 6, 7, 8]   # upper-clothes, skirt, pants, dress, belt
PROTECT_IDS = [2, 3, 11]      # hair, sunglasses, face

# ---------------------------------------------------------------- SAM2 加载

def load_sam2():
    # 以包形式导入 ComfyUI-segment-anything-2 (目录名含 '-'), 并注入 comfy.utils
    sys.path.insert(0, ROOT)
    import comfy.utils  # noqa: F401  (load_model 内部依赖)
    spec = importlib.util.spec_from_file_location(
        "csam2", os.path.join(SAM2_DIR, "__init__.py"),
        submodule_search_locations=[SAM2_DIR])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["csam2"] = pkg
    spec.loader.exec_module(pkg)
    lm = pkg.load_model
    fn = lm.load_model if hasattr(lm, "load_model") else lm
    return fn(SAM2_MODEL, SAM2_CFG, "single_image", torch.float16, torch.device("cuda"))

# ---------------------------------------------------------------- ATR 人体解析

class ATR:
    def __init__(self):
        self.sess = ort.InferenceSession(ATR_ONNX, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])

    def __call__(self, img_np):
        """img_np: HxWx3 uint8 RGB -> HxW uint8 label map"""
        h, w = img_np.shape[:2]
        x = np.array(Image.fromarray(img_np).resize((512, 512), Image.BILINEAR)).astype(np.float32) / 255.0
        x = (x - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
        x = x.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
        out = self.sess.run(None, {self.sess.get_inputs()[0].name: x})[0][0]
        lab = np.argmax(out, axis=0).astype(np.uint8)
        return np.array(Image.fromarray(lab).resize((w, h), Image.NEAREST))

def atr_garment_mask(parsing):
    m = np.isin(parsing, CLOTH_IDS)
    m &= ~np.isin(parsing, PROTECT_IDS)
    return m

# ---------------------------------------------------------------- 掩码清洗

def clean_mask(mask, min_ratio=0.1):
    from scipy import ndimage
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    main_id = int(np.argmax(sizes)) + 1
    main_top = np.where(lab == main_id)[0].min()
    H, W = mask.shape
    keep_ids = [main_id]
    for i in range(1, n + 1):
        if i == main_id or sizes[i - 1] < sizes.max() * min_ratio:
            continue
        ys, xs = np.where(lab == i)
        if xs.min() == 0 or xs.max() == W - 1:  # 触及左右边缘 -> 画面碎片
            continue
        if ys.max() < main_top:  # 整体悬于主服装上方 -> 飘发误判
            continue
        keep_ids.append(i)
    others = sorted((sizes[i - 1] for i in keep_ids if i != main_id), reverse=True)
    if not others or others[0] < 0.4 * sizes[main_id - 1]:
        keep_ids = [main_id]
    keep = np.isin(lab, keep_ids)
    disk = np.zeros((19, 19), bool)
    yy, xx = np.mgrid[-9:10, -9:10]
    disk[yy**2 + xx**2 <= 81] = True
    keep = ndimage.binary_closing(keep, structure=disk)
    return ndimage.binary_fill_holes(keep)

def compose_rgba(img, mask01):
    rgba = np.dstack([np.asarray(img.convert("RGB")), (mask01 * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA")

# ---------------------------------------------------------------- SAM2 精修

@torch.no_grad()
def sam2_refine(predictor, img_rgb, mask_bool):
    with torch.autocast("cuda", dtype=torch.float16):
        predictor.set_image(img_rgb)
        m256 = np.array(Image.fromarray(mask_bool.astype(np.uint8) * 255).resize((256, 256), Image.BILINEAR), np.float32) / 255.0
        out_masks, scores, _ = predictor.predict(
            point_coords=None, point_labels=None, box=None,
            multimask_output=True, mask_input=m256[None])
    idx = int(np.argmax(scores))
    return (out_masks[idx] > 0.0) if out_masks[idx].dtype == bool else (out_masks[idx] > 0.0)

# ---------------------------------------------------------------- 主流程

def main():
    input_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    out_root = os.path.join(ROOT, "output", time.strftime("%Y-%m-%d"), "garment_extract")
    videos = [os.path.join(input_dir, f) for f in sorted(os.listdir(input_dir))
              if f.lower().endswith(".mp4")]
    if not videos:
        sys.exit(f"no mp4 in {input_dir}")

    print("loading SAM2...", flush=True)
    predictor = load_sam2()
    atr = ATR()
    print("models ready", flush=True)

    manifest = []
    for video in videos:
        vname = os.path.splitext(os.path.basename(video))[0]
        vout = os.path.join(out_root, vname)
        kf_dir = os.path.join(vout, "keyframes")
        raw_dir = os.path.join(vout, "masks_raw")
        g_dir = os.path.join(vout, "garment")
        for d in (kf_dir, raw_dir, g_dir):
            os.makedirs(d, exist_ok=True)
        print(f"\n=== {vname} ===", flush=True)

        # 复用已有关键帧; 没有则现抽
        kfs = sorted(f for f in os.listdir(kf_dir) if f.startswith("frame_") and f.endswith(".jpg"))
        if not kfs:
            tmp = tempfile.mkdtemp(prefix="gkf_")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vf", "fps=4",
                            "-q:v", "2", os.path.join(tmp, "f_%04d.jpg")], check=True)
            cands = sorted(f for f in os.listdir(tmp) if f.endswith(".jpg"))
            arrs = [np.asarray(Image.open(os.path.join(tmp, f)).convert("L"), np.float32) for f in cands]
            def sharp(a):
                lap = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1) - 4 * a)
                return float(lap.var())
            picked = []
            for i in sorted(range(len(cands)), key=lambda i: -sharp(arrs[i])):
                if len(picked) >= 12:
                    break
                if all(float(np.abs(arrs[i] - arrs[j]).mean()) >= 4.0 for j in picked):
                    picked.append(i)
            picked.sort()
            for rank, i in enumerate(picked):
                shutil.copy(os.path.join(tmp, cands[i]), os.path.join(kf_dir, f"frame_{rank:02d}.jpg"))
            shutil.rmtree(tmp, ignore_errors=True)
            kfs = sorted(f for f in os.listdir(kf_dir) if f.endswith(".jpg"))

        results = []
        for kf_name in kfs:
            base = os.path.splitext(kf_name)[0]
            kf_path = os.path.join(kf_dir, kf_name)
            try:
                img = Image.open(kf_path).convert("RGB")
                img_np = np.asarray(img)
                parsing = atr(img_np)
                gm = atr_garment_mask(parsing)
                Image.fromarray((gm * 255).astype(np.uint8)).save(os.path.join(raw_dir, f"{base}_atr.png"))
                atr_m = clean_mask(gm)
                atr_area = float(atr_m.sum())
                if atr_area < 2000:
                    print(f"  {base}: ATR mask too small, skip", flush=True)
                    continue

                sam2_m = clean_mask(sam2_refine(predictor, img_np, atr_m))
                sam2_area = float(sam2_m.sum())
                if 0.5 * atr_area <= sam2_area <= 1.6 * atr_area and sam2_area > 2000:
                    garment_m, method = sam2_m.astype(np.float32), "atr+sam2"
                else:
                    a = Image.fromarray((atr_m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
                    garment_m = np.clip((np.asarray(a, np.float32) / 255.0 - 0.3) / 0.4, 0, 1)
                    method = "atr_only"

                ys, xs = np.where(garment_m > 0.5)
                gy0, gy1, gx0, gx1 = ys.min(), ys.max(), xs.min(), xs.max()
                pad_y, pad_x = int((gy1 - gy0) * 0.08), int((gx1 - gx0) * 0.08)
                H, W = garment_m.shape
                box = (max(0, gx0 - pad_x), max(0, gy0 - pad_y), min(W, gx1 + pad_x), min(H, gy1 + pad_y))

                crop_rgba = compose_rgba(img, garment_m).crop(box)
                white = Image.new("RGB", crop_rgba.size, (255, 255, 255))
                white.paste(crop_rgba, (0, 0), crop_rgba)

                lap = Image.fromarray(np.asarray(img.convert("L"))).filter(ImageFilter.FIND_EDGES)
                sharpv = float(np.asarray(lap, np.float32).var())
                area = float((garment_m > 0.5).sum())
                results.append({"base": base, "sharp": sharpv, "area": area, "method": method,
                                "bbox": [int(v) for v in box], "rgba": crop_rgba, "white": white})
                print(f"  {base}: ok ({method}, atr={atr_area:.0f}, sam2={sam2_area:.0f}, sharp={sharpv:.1f})", flush=True)
            except Exception as e:
                print(f"  {base}: FAILED {type(e).__name__}: {e}", flush=True)

        results.sort(key=lambda r: -(r["sharp"] * np.sqrt(r["area"]) * (0.6 if r["method"] == "atr_only" else 1.0)))
        for rank, r in enumerate(results[:3], 1):
            r["rgba"].save(os.path.join(g_dir, f"garment_{rank}_transparent.png"))
            r["white"].save(os.path.join(g_dir, f"garment_{rank}_white.png"))
            manifest.append({
                "video": os.path.basename(video), "rank": rank,
                "source_frame": r["base"], "sharpness": round(r["sharp"], 2),
                "mask_area": round(r["area"]), "method": r["method"], "crop_bbox": r["bbox"],
                "files": [f"garment_{rank}_transparent.png", f"garment_{rank}_white.png"],
            })
        print(f"saved top {min(3, len(results))} garments -> {g_dir}", flush=True)

    mf = os.path.join(out_root, "manifest.json")
    with open(mf, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nmanifest -> {mf}", flush=True)

if __name__ == "__main__":
    main()
