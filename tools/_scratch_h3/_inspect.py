# -*- coding: utf-8 -*-
"""检查产物视频是否真的有画面：逐帧 mean/std，并导出首/中/尾帧为 PNG。"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np          # noqa: F401
import cv2

GD = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard"
VIDS = ["h3_full_00001_.mp4",
        "h3_full_noswblend_00001_.mp4",
        "h3_full_pass1baseline_00001_.mp4"]
L = []

for v in VIDS:
    p = os.path.join(GD, v)
    if not os.path.exists(p):
        L.append("%s MISSING" % v)
        continue
    cap = cv2.VideoCapture(p)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    L.append("%s" % v)
    L.append("   frames=%s fps=%s %sx%s file=%d bytes" % (
        n, fps, w, h, os.path.getsize(p)))
    idx = 0
    picks = {0, max(0, n // 2), max(0, n - 1)}
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if idx in picks:
            L.append("   frame %-4d mean=%.2f std=%.2f min=%d max=%d" % (
                idx, fr.mean(), fr.std(), fr.min(), fr.max()))
            cv2.imwrite(os.path.join(HERE, "_insp_%s_%03d.png" % (
                v.replace(".mp4", ""), idx)), fr)
        idx += 1
    cap.release()
    L.append("   actually read %d frames" % idx)

# 顺便看看 holdmap
hp = os.path.join(GD, "h3_full_holdmap.holdmap.json")
if os.path.exists(hp):
    with io.open(hp, "r", encoding="utf-8") as f:
        L.append("\nholdmap: %s" % f.read()[:600])

with io.open(os.path.join(HERE, "_inspect_out.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
