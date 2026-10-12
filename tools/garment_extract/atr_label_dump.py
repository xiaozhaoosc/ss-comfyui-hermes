# -*- coding: utf-8 -*-
"""ATR 人体解析标签诊断器：看一张图里每个标签落在哪里。

用途：为服装提取校准 CLOTH_IDS（local_garment.py 的注释与 PROTECT_IDS 可疑，
11 在标准 ATR 里是 Skirt 而不是 Face，先跑这个再定标签）。

用法：
  <ComfyUI venv python> tools/garment_extract/atr_label_dump.py <image> <out_dir>
输出：
  <out_dir>/label_vis.png    彩色标签叠加图
  <out_dir>/parsing.npy      原始标签图
  stdout：逐标签 面积/占比/bbox
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import onnxruntime as ort
from PIL import Image

from local_garment import ATR_ONNX

# 标准 ATR (humanparsing) 18 类
ATR_NAMES = {
    0: "Background", 1: "Hat", 2: "Hair", 3: "Sunglasses", 4: "Upper-clothes",
    5: "Dress", 6: "Coat", 7: "Socks", 8: "Pants", 9: "Torso-skin", 10: "Scarf",
    11: "Skirt", 12: "Face", 13: "Left-arm", 14: "Right-arm", 15: "Left-leg",
    16: "Right-leg", 17: "Left-shoe", 18: "Right-shoe",
}
PALETTE = [
    (0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 128, 255),
    (255, 0, 255), (0, 255, 255), (128, 0, 255), (255, 128, 0), (255, 200, 200),
    (0, 128, 0), (255, 0, 128), (255, 255, 255), (128, 128, 0), (0, 128, 128),
    (128, 0, 0), (0, 0, 128), (128, 128, 128), (100, 100, 0),
]


class ATRLetterbox:
    """等比缩放 + letterbox 的 ATR。（实测对本图失效：黑边+黑底 → 全判背景）"""

    def __init__(self):
        self.sess = ort.InferenceSession(ATR_ONNX, providers=["CPUExecutionProvider"])

    def __call__(self, img_np: np.ndarray) -> np.ndarray:
        h, w = img_np.shape[:2]
        s = 512.0 / max(h, w)
        nh, nw = max(1, int(round(h * s))), max(1, int(round(w * s)))
        x0, y0 = (512 - nw) // 2, (512 - nh) // 2
        canvas = np.zeros((512, 512, 3), np.float32)
        small = np.asarray(Image.fromarray(img_np).resize((nw, nh), Image.BILINEAR))
        canvas[y0:y0 + nh, x0:x0 + nw] = small.astype(np.float32) / 255.0
        mean = np.array([0.406, 0.456, 0.485], np.float32)
        std = np.array([0.225, 0.224, 0.229], np.float32)
        canvas = (canvas - mean) / std
        out = self.sess.run(None, {self.sess.get_inputs()[0].name: canvas.transpose(2, 0, 1)[np.newaxis]})[0][0]
        lab = np.argmax(out, axis=0).astype(np.uint8)[y0:y0 + nh, x0:x0 + nw]
        return np.array(Image.fromarray(lab).resize((w, h), Image.NEAREST))


class ATRBands:
    """超高图横切成近方形 band，逐 band ATR 后按原坐标拼回。

    模型输入固定 512x512：整图直压会把 1:2 的竖图人体比例压烂；
    letterbox 又会被黑边带偏。切成 高/宽<=1.25 的 band，每条拉伸畸变很小。
    """

    def __init__(self, max_ratio: float = 1.25):
        self.sess = ort.InferenceSession(ATR_ONNX, providers=["CPUExecutionProvider"])
        self.max_ratio = max_ratio
        self.mean = np.array([0.406, 0.456, 0.485], np.float32)
        self.std = np.array([0.225, 0.224, 0.229], np.float32)

    def _run512(self, band_np: np.ndarray) -> np.ndarray:
        x = np.asarray(Image.fromarray(band_np).resize((512, 512), Image.BILINEAR))
        x = (x.astype(np.float32) / 255.0 - self.mean) / self.std
        out = self.sess.run(None, {self.sess.get_inputs()[0].name: x.transpose(2, 0, 1)[np.newaxis]})[0][0]
        return np.argmax(out, axis=0).astype(np.uint8)

    def __call__(self, img_np: np.ndarray) -> np.ndarray:
        h, w = img_np.shape[:2]
        n = max(1, -(-h // int(w * self.max_ratio)))   # ceil
        band_h = -(-h // n)
        labels = np.zeros((h, w), np.uint8)
        for i in range(n):
            y0, y1 = i * band_h, min(h, (i + 1) * band_h)
            lab512 = self._run512(img_np[y0:y1])
            labels[y0:y1] = np.array(
                Image.fromarray(lab512).resize((w, y1 - y0), Image.NEAREST))
        return labels


def main() -> int:
    img_path = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    atr = ATRBands()
    img = Image.open(img_path).convert("RGB")
    img_np = np.asarray(img)
    parsing = atr(img_np)

    np.save(os.path.join(out_dir, "parsing.npy"), parsing)
    H, W = parsing.shape
    total = H * W
    hist = np.bincount(parsing.ravel(), minlength=19)
    print(f"image {img_path}  {W}x{H}")
    for lid in range(19):
        c = int(hist[lid])
        if c == 0:
            continue
        ys, xs = np.where(parsing == lid)
        print(f"label {lid:2d} {ATR_NAMES.get(lid, '?'):14s} {c:9d}px {c / total * 100:5.1f}%  "
              f"y[{ys.min():4d},{ys.max():4d}] x[{xs.min():4d},{xs.max():4d}]")

    vis = np.zeros((H, W, 3), np.uint8)
    for lid in range(19):
        vis[parsing == lid] = PALETTE[lid % len(PALETTE)]
    # 叠加 50% 透明度方便比对
    blend = (img_np * 0.5 + vis * 0.5).astype(np.uint8)
    Image.fromarray(blend).save(os.path.join(out_dir, "label_vis.png"))
    Image.fromarray(vis).save(os.path.join(out_dir, "label_pure.png"))
    print(f"vis -> {os.path.join(out_dir, 'label_vis.png')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
