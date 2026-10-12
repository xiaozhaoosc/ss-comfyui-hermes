# -*- coding: utf-8 -*-
"""单张图片的服装提取（local_garment.py 视频流水线的单图版）。

与视频版的差异：
  * 无 ffmpeg 抽帧，直接吃一张图；
  * ATR 在粉紫打光的风格化图上标签不可靠 → 改用「纯黑背景人物剪影 +
    紫色系色域启发式」自动出 box，再交给 SAM2 box 提示精修；
  * 默认 CPU（本机 ComfyUI 常驻占 GPU， SAM2 b+ 用 box 提示只跑一次
    encoder，CPU 可接受）。配合 CUDA_VISIBLE_DEVICES="" 双保险。

用法：
  <ComfyUI venv python> tools/garment_extract/extract_from_image.py <image> <out_dir>
      [--boxes name=x0,y0,x1,y1 ...]   # 手工指定 box（跳过自动启发式）
      [--device cpu|cuda] [--no-sam2]  # --no-sam2 只出 ATR/色域 mask 调试用
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

import numpy as np
import torch
from PIL import Image, ImageFilter

ROOT = r"D:\ai_projects\ComfyUI"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_garment import SAM2_CFG, SAM2_DIR, SAM2_MODEL, clean_mask, compose_rgba  # noqa: E402


# ---------------------------------------------------------------- SAM2 加载
def load_sam2(device_str: str):
    import torch
    sys.path.insert(0, ROOT)
    import comfy.utils  # noqa: F401
    spec = importlib.util.spec_from_file_location(
        "csam2", os.path.join(SAM2_DIR, "__init__.py"),
        submodule_search_locations=[SAM2_DIR])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["csam2"] = pkg
    spec.loader.exec_module(pkg)
    lm = pkg.load_model
    fn = lm.load_model if hasattr(lm, "load_model") else lm
    dev = torch.device(device_str)
    dtype = torch.float16 if dev.type == "cuda" else torch.float32
    return fn(SAM2_MODEL, SAM2_CFG, "single_image", dtype, dev)


# ---------------------------------------------------------------- 启发式
def _disk(r: int) -> np.ndarray:
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return yy ** 2 + xx ** 2 <= r ** 2


def person_mask(img_rgb: np.ndarray, v_thr: int = 42) -> np.ndarray:
    """纯黑背景图的人物剪影：亮度阈值 + 最大连通域 + 闭运算填洞。"""
    from scipy import ndimage
    m = img_rgb.max(axis=2) > v_thr
    lab, n = ndimage.label(m)
    if n == 0:
        raise SystemExit("person_mask: 整图全黑？")
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    m = lab == (int(np.argmax(sizes)) + 1)
    m = ndimage.binary_closing(m, structure=_disk(7))
    return ndimage.binary_fill_holes(m)


def purple_boxes(img_rgb: np.ndarray, pmask: np.ndarray,
                 want: int = 2, min_area: int = 4000) -> list[tuple[str, tuple[int, int, int, int]]]:
    """紫色系服装的粗 box（按 y 自上而下）。覆盖不到的衣服用 --boxes 手补。"""
    from scipy import ndimage
    hsv = np.asarray(Image.fromarray(img_rgb).convert("HSV"), np.int16)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    purple = (h >= 170) & (h <= 240) & (s >= 70) & (v >= 55) & pmask
    purple = ndimage.binary_opening(purple, structure=_disk(3))
    lab, n = ndimage.label(purple)
    if n == 0:
        return []
    sizes = ndimage.sum(purple, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1]
    picked: list[tuple[int, tuple[int, int, int, int], int]] = []
    for i in order:
        if sizes[i] < min_area:
            break
        ys, xs = np.where(lab == i + 1)
        box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        cy = (box[1] + box[3]) / 2
        # 与已选 box 垂直方向重叠太多的算同一件
        if any(not (box[3] < b[1] or box[1] > b[3]) for _, b, _ in picked):
            continue
        picked.append((int(i) + 1, box, int(cy)))
        if len(picked) >= want:
            break
    picked.sort(key=lambda t: t[2])
    names = ["top", "bottom", "extra1", "extra2"][:len(picked)]
    out = []
    for name, (_, (x0, y0, x1, y1), _c) in zip(names, picked):
        px, py = int((x1 - x0) * 0.10), int((y1 - y0) * 0.10)
        out.append((name, (max(0, x0 - px), max(0, y0 - py),
                           min(img_rgb.shape[1], x1 + px), min(img_rgb.shape[0], y1 + py))))
    return out


# ---------------------------------------------------------------- SAM2
@torch.no_grad()
def sam2_box(predictor, box: tuple[int, int, int, int]) -> np.ndarray:
    box_np = np.array(box, np.float32)
    masks, scores, _ = predictor.predict(
        point_coords=None, point_labels=None, box=box_np, multimask_output=True)
    idx = int(np.argmax(scores))
    m = masks[idx]
    return (m > 0.0) if np.asarray(m).dtype != bool else m


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out_dir")
    ap.add_argument("--boxes", nargs="*", default=[],
                    help="name=x0,y0,x1,y1，给了就跳过自动启发式")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--no-sam2", action="store_true", help="只出粗 box 内的原始裁剪，调参用")
    a = ap.parse_args()

    from scipy import ndimage
    img = Image.open(a.image).convert("RGB")
    img_np = np.asarray(img)
    out_dir = os.path.abspath(a.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    pmask = person_mask(img_np)
    Image.fromarray((pmask * 255).astype(np.uint8)).save(os.path.join(out_dir, "person_mask.png"))

    if a.boxes:
        boxes = []
        for spec in a.boxes:
            name, coord = spec.split("=", 1)
            boxes.append((name, tuple(int(v) for v in coord.split(","))))
    else:
        boxes = purple_boxes(img_np, pmask)
    if not boxes:
        print("没有找到任何服装 box（色域启发式落空，请用 --boxes 手工指定）")
        return 3
    print(f"boxes: {[(n, b) for n, b in boxes]}", flush=True)
    for name, b in boxes:
        Image.fromarray(img_np[b[1]:b[3], b[0]:b[2]]).save(os.path.join(out_dir, f"box_{name}.png"))

    predictor = None
    if not a.no_sam2:
        print(f"loading SAM2 on {a.device} ...", flush=True)
        predictor = load_sam2(a.device)
        # 只跑一次 encoder，后续多个 box 提示复用
        predictor.set_image(img_np)
        print("SAM2 ready (image encoded)", flush=True)

    manifest = []
    for name, (x0, y0, x1, y1) in boxes:
        gm = np.zeros(img_np.shape[:2], bool)
        gm[y0:y1, x0:x1] = True          # box 内全候选，SAM2 负责抠
        if predictor is not None:
            m = sam2_box(predictor, (x0, y0, x1, y1))
            m = clean_mask(m & pmask)
        else:
            m = clean_mask(gm)
        area = float(m.sum())
        if area < 2000:
            print(f"  {name}: mask 太小({area:.0f})，跳过", flush=True)
            continue
        ys, xs = np.where(m)
        gx0, gy0, gx1, gy1 = xs.min(), ys.min(), xs.max(), ys.max()
        pad_x, pad_y = int((gx1 - gx0) * 0.06), int((gy1 - gy0) * 0.06)
        H, W = m.shape
        crop_box = (max(0, gx0 - pad_x), max(0, gy0 - pad_y),
                    min(W, gx1 + pad_x), min(H, gy1 + pad_y))
        rgba = compose_rgba(img, m).crop(crop_box)
        white = Image.new("RGB", rgba.size, (255, 255, 255))
        white.paste(rgba, (0, 0), rgba)

        gdir = os.path.join(out_dir, name)
        os.makedirs(gdir, exist_ok=True)
        rgba.save(os.path.join(gdir, "transparent.png"))
        white.save(os.path.join(gdir, "white.png"))
        mean_rgb = img_np[m > 0.5].mean(axis=0).round().astype(int).tolist()
        meta = {
            "name": name, "source_image": os.path.abspath(a.image),
            "box": [x0, y0, x1, y1], "crop_bbox": [int(v) for v in crop_box],
            "mask_area_px": int(area), "image_size": [W, H],
            "mean_rgb": mean_rgb, "mean_hex": "#%02x%02x%02x" % tuple(mean_rgb),
            "method": "sam2_box" if predictor is not None else "raw_box",
            "device": a.device,
        }
        with open(os.path.join(gdir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        manifest.append(meta)
        print(f"  {name}: area={area:.0f} hex={meta['mean_hex']} -> {gdir}", flush=True)

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"done: {len(manifest)} garments -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
