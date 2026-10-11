#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 2 集九宫格分镜表智能切片工具 (EP02 Smart Grid Cutter)

升级特性：
1. 【智能边框检测】：优先使用 OpenCV 自动探测 9 个独立画框（完美剔除黑边框与底部说明文字）；
2. 【安全平退机制】：未检测到完整 9 框时自动平退为等距 3x3 网格均匀切片；
3. 【电影级重采样】：按照竖屏 9:16 (544x960) 规格进行高保真 Lanczos 重采样输出；
4. 【标准输出】：保存至 input/yang_ep02_shot01.jpg ~ yang_ep02_shot54.jpg。
"""

import os
import sys
import argparse
import cv2
import numpy as np
from PIL import Image, ImageOps

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

INPUT_DIR = os.path.join(ROOT, "input")


def find_panel_boxes(img_path):
    """自动检测九宫格中 9 个主画格的外接矩形"""
    im_gray = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if im_gray is None:
        return []
    H, W = im_gray.shape

    edges = cv2.Canny(im_gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    raw_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # 尺寸大致为宽 240~360, 高 180~360
        if 240 < w < W * 0.38 and 180 < h < H * 0.38:
            raw_boxes.append((x, y, w, h))

    # 去重
    filtered = []
    for b in sorted(raw_boxes, key=lambda x: (x[1] // 160, x[0])):
        if not any(abs(b[0] - fb[0]) < 25 and abs(b[1] - fb[1]) < 25 for fb in filtered):
            filtered.append(b)

    # 排序：从上到下，从左到右
    sorted_boxes = sorted(filtered, key=lambda b: (b[1] // 200, b[0]))
    return sorted_boxes[:9]


def slice_ep02_grid(
    grid_image_path,
    grid_index=1,
    rows=3,
    cols=3,
    target_width=544,
    target_height=960,
    margin_ratio=0.035,
    output_prefix="yang_ep02_shot"
):
    """将单张 3x3 九宫格大图切分为 9 个独立 9:16 镜头关键帧"""
    if not os.path.exists(grid_image_path):
        raise FileNotFoundError(f"未找到九宫格图片: {grid_image_path}")

    pil_img = Image.open(grid_image_path).convert("RGB")
    W, H = pil_img.size

    start_shot_id = (grid_index - 1) * 9 + 1
    end_shot_id = grid_index * 9
    shot_ids = list(range(start_shot_id, end_shot_id + 1))

    # 尝试智能边框检测
    boxes = find_panel_boxes(grid_image_path)
    use_smart_boxes = (len(boxes) == 9)

    if use_smart_boxes:
        print(f"\n=== [智能边框定位] 识别到 9 个独立子画框: {os.path.basename(grid_image_path)} ===")
    else:
        print(f"\n=== [标准网格分割] 使用 3x3 均匀网格: {os.path.basename(grid_image_path)} ===")
        cell_w = W / cols
        cell_h = H / rows
        boxes = []
        for r in range(rows):
            for c in range(cols):
                boxes.append((int(c * cell_w), int(r * cell_h), int(cell_w), int(cell_h)))

    sliced_paths = {}
    for idx, (x, y, w, h) in enumerate(boxes[:9]):
        shot_id = shot_ids[idx]

        # 内缩 4~6px 剔除黑线
        inset_x = max(4, int(w * 0.02))
        inset_y = max(4, int(h * 0.02))
        crop_box = (
            x + inset_x,
            y + inset_y,
            x + w - inset_x,
            y + h - inset_y
        )

        cell_img = pil_img.crop(crop_box)
        fitted_img = ImageOps.fit(cell_img, (target_width, target_height), method=Image.Resampling.LANCZOS)

        out_fn = f"{output_prefix}{shot_id:02d}.jpg"
        out_path = os.path.join(INPUT_DIR, out_fn)
        fitted_img.save(out_path, quality=95)
        sliced_paths[shot_id] = out_path

        print(f"  [切片成功] 镜 {shot_id:02d} ({out_fn}, {target_width}x{target_height}) 来自框 [{x},{y},{w},{h}]")

    print(f"=== Grid {grid_index} 切片完毕，生成镜头 {start_shot_id:02d} ~ {end_shot_id:02d} ===\n")
    return sliced_paths


def main():
    parser = argparse.ArgumentParser(description="第2集九宫格原画自动切片工具")
    parser.add_argument("--image", type=str, help="九宫格原画大图路径")
    parser.add_argument("--grid", type=int, default=1, choices=range(1, 7), help="指定九宫格编号 (1~6)")
    parser.add_argument("--all-dir", type=str, help="扫描目录中所有的 grid*.jpg/png 自动全部切片")
    args = parser.parse_args()

    if args.image:
        slice_ep02_grid(args.image, grid_index=args.grid)
    elif args.all_dir:
        for g in range(1, 7):
            for ext in [".jpg", ".png", ".jpeg"]:
                cand = os.path.join(args.all_dir, f"yang_ep02_grid{g:02d}{ext}")
                cand2 = os.path.join(args.all_dir, f"grid{g:02d}{ext}")
                cand3 = os.path.join(args.all_dir, f"grid{g}{ext}")
                cand4 = os.path.join(args.all_dir, f"yang_ep02_grid0{g}{ext}")
                target = cand if os.path.exists(cand) else (cand2 if os.path.exists(cand2) else (cand3 if os.path.exists(cand3) else (cand4 if os.path.exists(cand4) else None)))
                if target:
                    slice_ep02_grid(target, grid_index=g)
                    break
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
