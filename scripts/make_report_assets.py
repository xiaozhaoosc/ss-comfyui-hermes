# -*- coding: utf-8 -*-
"""
make_report_assets.py
=====================
为交付报告生成可视化比对资产：

1) `<group>_4way.png`      3 张代表切片 × 4 路（原图 / Qwen2.1 / Flux / SDXL）全景比对
2) `<group>_micro.png`     脸部 512x512 原生像素微距（不经缩放，看毛孔/眼眸/唇纹）
3) `<group>_eye.png`       眼部 256x256 原生像素微距
4) `sheet_overview.png`    6 组 × 4 路 总览（每组取中心切片）
5) `skin_scatter.png`      皮肤细节 vs 血色层次 散点图（四路分布）
"""

import os
import re
import sys
import glob
import json
import argparse
import csv

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_photorealism_v1 import (  # noqa: E402
    ROOT, BASE_DIR, MODE_DIRS, KEY_RE, DET_PATH,
    imread_any, index_dir, detect_face, face_regions,
)

MODES = ["base", "qwen21", "flux", "sdxl"]
MODE_LABEL = {"base": "ORIGINAL (1024 crop)", "qwen21": "Qwen-Image 2.1",
              "flux": "Flux.1-dev Abliterated", "sdxl": "SDXL RealVisXL v4"}
# BGR 标签色
MODE_COLOR = {"base": (150, 150, 150), "qwen21": (60, 150, 250),
              "flux": (230, 130, 60), "sdxl": (90, 190, 110)}


def put_label(img, text, color, scale=0.9, thick=2, pad=10):
    """在图顶贴一条带色块的小标题。"""
    h, w = img.shape[:2]
    bar = np.full((46, w, 3), 255, np.uint8)
    cv2.rectangle(bar, (0, 0), (w, 46), color, -1)
    out = np.vstack([bar, img])
    cv2.putText(out, text, (pad, 33), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), thick, cv2.LINE_AA)
    return out


def hstack_pad(imgs, pad=8, bg=255):
    """不同高度也能横拼：统一补到最高。"""
    hs = [i.shape[0] for i in imgs]
    ws = [i.shape[1] for i in imgs]
    H = max(hs)
    out = []
    for i in imgs:
        if i.shape[0] < H:
            d = H - i.shape[0]
            i = np.vstack([i, np.full((d, i.shape[1], 3), bg, np.uint8)])
        out.append(i)
    sep = np.full((H, pad, 3), bg, np.uint8)
    parts = []
    for k, i in enumerate(out):
        parts.append(i)
        if k != len(out) - 1:
            parts.append(sep)
    return np.hstack(parts), sum(ws) + pad * (len(ws) - 1)


def vstack_pad(imgs, pad=8, bg=255):
    ws = [i.shape[1] for i in imgs]
    W = max(ws)
    out = []
    for i in imgs:
        if i.shape[1] < W:
            d = W - i.shape[1]
            i = np.hstack([i, np.full((i.shape[0], d, 3), bg, np.uint8)])
        out.append(i)
    sep = np.full((pad, W, 3), bg, np.uint8)
    parts = []
    for k, i in enumerate(out):
        parts.append(i)
        if k != len(out) - 1:
            parts.append(sep)
    return np.vstack(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "2026-10-10_wb", "compare"))
    ap.add_argument("--cell", type=int, default=760, help="全景图单元格边长")
    ap.add_argument("--micro", type=int, default=512, help="微距裁剪边长（原生像素，不缩放）")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    base_idx = index_dir(BASE_DIR, "*_1x1.png")
    mode_idx = {k: index_dir(v) for k, v in MODE_DIRS.items() if k != "base"}

    groups = sorted({k[0] for k in base_idx})
    print(f"[groups] {len(groups)}")

    def path_for(mode, key):
        return base_idx[key] if mode == "base" else mode_idx.get(mode, {}).get(key)

    manifest = []

    for gi, group in enumerate(groups):
        keys = sorted([k for k in base_idx if k[0] == group])
        # 代表切片：1 / 5 / 9（左上、正中、右下）
        picks = []
        for want in (1, 5, 9):
            cand = [k for k in keys if k[3] == want]
            picks.append(cand[0] if cand else keys[len(picks) % len(keys)])
        picks = list(dict.fromkeys(picks))

        # ---------- 1) 4way 全景 ----------
        rows = []
        for key in picks:
            cells = []
            for mode in MODES:
                p = path_for(mode, key)
                img = imread_any(p) if p else None
                if img is None:
                    img = np.full((args.cell, args.cell, 3), 240, np.uint8)
                else:
                    img = cv2.resize(img, (args.cell, args.cell), interpolation=cv2.INTER_AREA)
                cells.append(put_label(img, MODE_LABEL[mode], MODE_COLOR[mode], scale=0.75))
            rows.append(hstack_pad(cells)[0])
        sheet = vstack_pad(rows)
        fp = os.path.join(args.out, f"{gi+1:02d}_{group}_4way.png")
        cv2.imencode(".png", sheet)[1].tofile(fp)
        print(f"[ok] {fp} {sheet.shape[1]}x{sheet.shape[0]}")
        manifest.append({"group": group, "type": "4way", "file": os.path.basename(fp)})

        # ---------- 2/3) 微距（原生像素） ----------
        key = picks[1] if len(picks) > 1 else picks[0]   # 正中切片
        b = imread_any(base_idx[key])
        bb, kps = detect_face(b)
        if bb is None:
            print(f"[warn] 无人脸 {group} {key}，跳过微距")
            continue
        fx1, fy1, fx2, fy2 = bb
        cx, cy = (fx1 + fx2) / 2, (fy1 + fy2) / 2

        def crop_native(p, fx, fy, half):
            """以归一化中心 (fx,fy) 裁一块内容对齐的区域。
            2048 图裁 2*half 见方（原生像素，不缩放）；
            1024 基线裁 half 见方再放大 2x，保证四路画面内容一致、尺寸一致。"""
            img = imread_any(p)
            if img is None:
                return None
            H, W = img.shape[:2]
            hs = half if W >= 2048 else half // 2
            X, Y = int(round(fx * W)), int(round(fy * H))
            x1, y1 = max(0, X - hs), max(0, Y - hs)
            x2, y2 = min(W, X + hs), min(H, Y + hs)
            sub = img[y1:y2, x1:x2]
            if sub.shape[0] != 2 * hs or sub.shape[1] != 2 * hs:
                sub = cv2.copyMakeBorder(sub, 0, 2 * hs - sub.shape[0], 0, 2 * hs - sub.shape[1],
                                         cv2.BORDER_REPLICATE)
            if W < 2048:   # 基线放大到与其它路同尺寸
                sub = cv2.resize(sub, (2 * half, 2 * half), interpolation=cv2.INTER_LANCZOS4)
            return sub

        for tag, half in (("micro", args.micro // 2), ("eye", 128)):
            if tag == "eye":
                if kps is None or len(kps) < 2:
                    continue
                # 归一化坐标（相对基线 1024）
                fx, fy = (kps[0][0] + kps[1][0]) / 2 / b.shape[1], (kps[0][1] + kps[1][1]) / 2 / b.shape[0]
            else:
                fx, fy = cx / b.shape[1], cy / b.shape[0]
            cells = []
            for mode in MODES:
                p = path_for(mode, key)
                sub = crop_native(p, fx, fy, half)
                if sub is None:
                    continue
                cells.append(put_label(sub, MODE_LABEL[mode], MODE_COLOR[mode], scale=0.55))
            if not cells:
                continue
            sheet = hstack_pad(cells)[0]
            fp = os.path.join(args.out, f"{gi+1:02d}_{group}_{tag}.png")
            cv2.imencode(".png", sheet)[1].tofile(fp)
            print(f"[ok] {fp} {sheet.shape[1]}x{sheet.shape[0]}")
            manifest.append({"group": group, "type": tag, "file": os.path.basename(fp)})

    # ---------- 4) 总览：6 组 × 4 路（中心切片） ----------
    cells_all = []
    for group in groups:
        keys = sorted([k for k in base_idx if k[0] == group])
        key = [k for k in keys if k[3] == 5] or keys[:1]
        key = key[0]
        row = []
        for mode in MODES:
            p = path_for(mode, key)
            img = imread_any(p) if p else None
            if img is None:
                img = np.full((args.cell, args.cell, 3), 240, np.uint8)
            else:
                img = cv2.resize(img, (420, 420), interpolation=cv2.INTER_AREA)
            row.append(img)
        cells_all.append(hstack_pad(row)[0])
    ov = vstack_pad(cells_all)
    fp = os.path.join(args.out, "sheet_overview.png")
    cv2.imencode(".png", ov)[1].tofile(fp)
    print(f"[ok] {fp} {ov.shape[1]}x{ov.shape[0]}")
    manifest.append({"group": "ALL", "type": "overview", "file": "sheet_overview.png"})

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("[done]")


if __name__ == "__main__":
    main()
