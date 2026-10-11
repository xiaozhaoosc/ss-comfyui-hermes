#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_transparent_stickers.py
使用 BiRefNet 直接对 5 张 OOTD 去手机参考图进行高精度静态抠像，生成透明背景 PNG (RGBA)。
"""
import os
import sys
import time
import numpy as np
from PIL import Image
import torch

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from comfy.bg_removal_model import load

MODEL_PATH = r"D:\OLLAMA_MODELS\models\background_removal\BiRefNet-general.safetensors"
OUT_BASE = os.path.join(ROOT, "output", "2026-10-03", "ootd_multilook_nophone")
SRC_DIR = os.path.join(OUT_BASE, "swap_nophone")
DST_DIR = os.path.join(OUT_BASE, "swap_cutout")
os.makedirs(DST_DIR, exist_ok=True)

def main():
    print(f"[sticker] 加载 BiRefNet 模型: {MODEL_PATH}")
    t0 = time.time()
    model = load(MODEL_PATH)
    print(f"[sticker] 模型加载完成 ({round(time.time() - t0, 2)}s)")

    for k in range(1, 6):
        src_file = os.path.join(SRC_DIR, f"g{k}_00001_.png")
        dst_file = os.path.join(DST_DIR, f"g{k}_cutout.png")
        if not os.path.exists(src_file):
            print(f"[警告] 找不到参考图: {src_file}")
            continue

        print(f"[sticker] 正在处理 g{k}: {os.path.basename(src_file)} ...")
        t_img = time.time()
        pil_img = Image.open(src_file).convert("RGB")
        w, h = pil_img.size

        # ComfyUI Image tensor 格式: [B, H, W, C], float32 in [0, 1]
        img_np = np.array(pil_img).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_np).unsqueeze(0)

        # 推理
        with torch.no_grad():
            mask_tensor = model.encode_image(img_tensor)

        # mask 输出 [B, H, W] 或 [H, W]
        mask_np = mask_tensor.squeeze().cpu().numpy()
        mask_uint8 = np.clip(mask_np * 255.0, 0, 255).astype(np.uint8)

        # 合成为 RGBA
        r, g, b = pil_img.split()
        alpha = Image.fromarray(mask_uint8)
        rgba_img = Image.merge("RGBA", (r, g, b, alpha))

        # 保存透明 PNG
        rgba_img.save(dst_file, format="PNG")
        print(f"[sticker] g{k} 抠像完成 -> {os.path.basename(dst_file)} ({round(time.time() - t_img, 2)}s)")

    print(f"[sticker] 全部 5 张透明小人贴纸生成完成！输出目录: {DST_DIR}")

if __name__ == "__main__":
    main()
