#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 0: 从参考视频纯净提取服装图（供 IDM-VTON 使用）
v3: 内联 ATR 解析（拿到完整 label 图）+ 下颌线以上剔除 + 最大连通域 + top-3 候选

用法:
  python tools/extract_garment.py --video <参考视频> --out <输出png> [--time 秒]
"""
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))  # ComfyUI 根目录（import folder_paths）

GARMENT_LABELS = (4, 5, 6, 7, 8, 10, 11)   # 上装/连衣裙/外套/袜/裤/围巾/裙
MIN_AREA, MAX_AREA = 0.06, 0.55            # 全身时尚帧服装占比可到 ~0.5


def detect_chin(frame, parsing):
    """下颌线 y：优先 Haar 人脸框底；退化用 label12 最大连通域底；再退化 None"""
    H = frame.shape[0]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                     minSize=(int(H * 0.04), int(H * 0.04)))
    if len(faces):
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return int(min(H - 1, y + h + 0.01 * H))
    face = (parsing == 12).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(face)
    if n >= 2:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, w, h, a = stats[big]
        bottom = y + h
        if a > 0.0008 * parsing.size and bottom < 0.75 * H:
            return int(min(H - 1, bottom + 0.01 * H))
    return None


class ATRParser:
    """轻量 ATR 解析：返回原图分辨率的 label 图"""

    def __init__(self):
        import onnxruntime as ort
        import folder_paths
        path = os.path.join(folder_paths.models_dir, 'IDM-VTON', 'humanparsing', 'parsing_atr.onnx')
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        print(f'[ATR] {path}')
        self.session = ort.InferenceSession(
            path, providers=['DmlExecutionProvider', 'CPUExecutionProvider'])

    def parse(self, pil_img):
        w, h = pil_img.size
        x = pil_img.convert('RGB').resize((512, 512), Image.BILINEAR)
        a = np.array(x).astype(np.float32) / 255.0
        a = (a - np.array([0.406, 0.456, 0.485])) / np.array([0.225, 0.224, 0.229])
        a = a.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
        out = self.session.run(None, {self.session.get_inputs()[0].name: a})
        small = np.argmax(out[0][0], axis=0).astype(np.uint8)
        return np.array(Image.fromarray(small).resize((w, h), Image.NEAREST))


def refine(parsing, chin_y):
    """返回 (garment_mask, fill) 或 (None, fill)"""
    garment = np.isin(parsing, GARMENT_LABELS).astype(np.uint8) * 255
    if chin_y:
        garment[:max(0, chin_y - 4), :] = 0  # 下颌线以上全部剔除（含颈/脸/发顶）
    garment = cv2.morphologyEx(garment, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    garment = cv2.morphologyEx(garment, cv2.MORPH_CLOSE,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(garment)
    if n < 2:
        return None, 0.0
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    comp = (lab == big).astype(np.uint8) * 255
    x, y, w, h, area = stats[big]
    fill = area / float(w * h)
    if fill < 0.42:
        return None, fill
    return comp, fill


def main():
    ap = argparse.ArgumentParser(description="参考视频服装纯净提取 v3")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--time", type=float, default=None, help="指定秒数；不指定则自动选最佳")
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--max-side", type=int, default=1024)
    ap.add_argument("--debug-dir", default=None)
    args = ap.parse_args()

    parser = ATRParser()
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"❌ 打不开视频: {args.video}")
        sys.exit(1)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if args.time is not None:
        cap.set(cv2.CAP_PROP_POS_MSEC, args.time * 1000)
        cand_idx = [int(cap.get(cv2.CAP_PROP_POS_FRAMES))]
    else:
        cand_idx = [int(total * f / (args.samples + 1)) for f in range(1, args.samples + 1)]

    cands = []
    for idx in cand_idx:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        parsing = parser.parse(pil)
        chin_y = detect_chin(frame, parsing)
        comp, fill = refine(parsing, chin_y)
        if comp is None:
            continue
        area = float((comp > 128).mean())
        if not (MIN_AREA <= area <= MAX_AREA):
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharp = cv2.Laplacian(gray, cv2.CV_64F).var()
        ys, xs = np.where(comp > 128)
        bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        score = sharp * fill * min(area, MAX_AREA - area + 0.05)
        cands.append((score, idx, frame, comp, area, sharp, fill, bbox, chin_y))
    cap.release()
    if not cands:
        print("❌ 没有合格候选帧")
        sys.exit(2)
    cands.sort(key=lambda c: -c[0])

    def make_garment(frame, comp, bbox):
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1
        mx, my = max(8, int(bw * 0.04)), max(8, int(bh * 0.04))
        H, W = frame.shape[:2]
        x1, y1 = max(0, x1 - mx), max(0, y1 - my)
        x2, y2 = min(W, x2 + mx), min(H, y2 + my)
        crop = frame[y1:y2, x1:x2]
        alpha = cv2.GaussianBlur(comp[y1:y2, x1:x2], (5, 5), 0).astype(np.float32) / 255.0
        h, w = crop.shape[:2]
        scale = args.max_side / max(h, w)
        if scale < 1:
            crop = cv2.resize(crop, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            alpha = cv2.resize(alpha, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_AREA)
        white = np.full_like(crop, 255, dtype=np.uint8)
        a3 = alpha[..., np.newaxis]
        return (crop.astype(np.float32) * a3 + white.astype(np.float32) * (1 - a3)).astype(np.uint8)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    s, idx, frame, comp, area, sharp, fill, bbox, chin = cands[0]
    cv2.imwrite(args.out, make_garment(frame, comp, bbox))
    print(f"✅ {args.out} | 帧 {idx}/{total} | 占比 {area:.2f} | 填充 {fill:.2f} | 清晰度 {sharp:.0f} | 下颌线 y={chin} | bbox {bbox}")

    if args.debug_dir:
        os.makedirs(args.debug_dir, exist_ok=True)
        for rank, (s2, idx2, fr2, cp2, a2, sh2, f2, bb2, ch2) in enumerate(cands[:3], 1):
            dbg = fr2.copy()
            dbg[cp2 > 128] = (0.4 * dbg[cp2 > 128] + np.array([0, 255, 0]) * 0.6).astype(np.uint8)
            if ch2:
                cv2.line(dbg, (0, ch2), (dbg.shape[1], ch2), (0, 0, 255), 2)
            cv2.imwrite(os.path.join(args.debug_dir, f"cand{rank}_frame{idx2}.png"), dbg)
            cv2.imwrite(os.path.join(args.debug_dir, f"cand{rank}_garment.png"), make_garment(fr2, cp2, bb2))
        print(f"   调试图(top-3): {args.debug_dir}")


if __name__ == "__main__":
    main()
