#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第1集后续剧情分镜原画预处理与画幅适配"""

import os
import glob
from PIL import Image, ImageOps

ROOT = r"D:\ai_projects\ComfyUI"
SRC_DIR = os.path.join(ROOT, "input", "yangjiajiang_ep01")
INPUT_DIR = os.path.join(ROOT, "input")

SHOT_PAGE_MAP = {
    13: 15,
    14: 16,
    15: 17,
    16: 18,
    17: 19,
    18: 20,
    19: 21,
    20: 22,
    21: 23,
    22: 24,
    23: 25,
    24: 26,
    25: 27,
    26: 28,
    27: 29,
    28: 30,
    29: 31,
    30: 32,
    31: 33,
    32: 34,
    33: 35,
    34: 36,
    35: 37,
    36: 38,
    37: 39,
    38: 39,
    39: 40,
    40: 41,
    41: 41,
}

def main():
    os.makedirs(INPUT_DIR, exist_ok=True)
    count = 0
    for shot_id, page_no in SHOT_PAGE_MAP.items():
        candidates = [
            os.path.join(SRC_DIR, f"page-{page_no:02d}.png"),
            os.path.join(SRC_DIR, f"page-{page_no}.png"),
        ]
        src_path = None
        for c in candidates:
            if os.path.exists(c):
                src_path = c
                break

        if not src_path:
            print(f"Warning: Page {page_no} not found for shot {shot_id}")
            continue

        img = Image.open(src_path).convert("RGB")

        # 16:9 横屏规格 (1376x768 / 960x544)
        img_16_9 = ImageOps.fit(img, (1376, 768), method=Image.Resampling.LANCZOS)
        out_16_9 = os.path.join(INPUT_DIR, f"yang_ep01_shot{shot_id:02d}.jpg")
        img_16_9.save(out_16_9, quality=95)

        # 9:16 竖屏规格 (544x960)
        img_9_16 = ImageOps.fit(img, (544, 960), method=Image.Resampling.LANCZOS)
        out_9_16 = os.path.join(INPUT_DIR, f"yang_ep01_v_shot{shot_id:02d}.jpg")
        img_9_16.save(out_9_16, quality=95)

        count += 1
        print(f"Shot {shot_id:02d} (p{page_no}): Ready -> {os.path.basename(out_16_9)} & {os.path.basename(out_9_16)}")

    print(f"\nAll {count} shots successfully prepared for Episode 1 continuation!")

if __name__ == "__main__":
    main()
