# -*- coding: utf-8 -*-
"""定稿后处理：对修复输出叠胶片颗粒，校准平坦区噪声底到自然水平。

用法: python tools/finalize_grain.py <输入图> <输出图> [--sigma 1.5] [--seed 42]
定稿参数: sigma=1.5 (img_d 实测: flat 0.545→~1.6, ✔ 区间; kurt 因噪声正则化下降)
"""
import argparse

import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--sigma", type=float, default=1.5)
ap.add_argument("--seed", type=int, default=42)
args = ap.parse_args()

rng = np.random.default_rng(args.seed)
im = Image.open(args.src).convert("RGB")
a = np.asarray(im, dtype=np.float32)
noise = rng.normal(0.0, args.sigma, a.shape).astype(np.float32)
out = np.clip(a + noise, 0, 255).astype(np.uint8)
Image.fromarray(out).save(args.dst)
print(f"grain done: {args.dst} (sigma={args.sigma}, seed={args.seed})")
