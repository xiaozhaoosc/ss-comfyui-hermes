# -*- coding: utf-8 -*-
"""
frame 17 到底有什么特别？逐个子模型在 frame 16/17/18 上跑，看哪个挂。
也保存这三帧为 PNG，便于人工比对。
"""
import sys, os, io, json, traceback, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_calib_now.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib9 start %s ===" % time.strftime("%H:%M:%S"))

import numpy as np
import cv2
import torch
torch.set_num_threads(1)

VID = r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4"
cap = cv2.VideoCapture(VID)
frames = []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    frames.append(fr.copy())
cap.release()
log("frames=%d" % len(frames))

# 保存 14..20 帧
for i in range(14, 21):
    if i < len(frames):
        p = os.path.join(HERE, "_frame_%02d.png" % i)
        cv2.imwrite(p, frames[i])
        log("saved %s shape=%s mean=%.2f std=%.2f" % (
            os.path.basename(p), frames[i].shape, frames[i].mean(), frames[i].std()))

# 逐帧统计差异（看 frame17 是否异常）
log("--- inter-frame abs diff ---")
for i in range(12, 22):
    if i + 1 < len(frames):
        d = float(np.abs(frames[i].astype(np.float32) - frames[i + 1].astype(np.float32)).mean())
        log("  %d->%d  %.3f" % (i, i + 1, d))

# 直接跑检测模型（RetinaFace）在各帧
log("--- RetinaFace detect on frames 15..19 ---")
from insightface.app import FaceAnalysis
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1, det_size=(640, 640))
det = app.models["detection"]
log("det=%s input_shape=%s" % (det.__class__.__name__, getattr(det, "input_shape", None)))

for i in range(15, 20):
    if i >= len(frames):
        break
    log("  frame %d" % i)
    try:
        bboxes, kpss = det.detect(frames[i], input_size=(640, 640), max_num=0)
        log("    det ok n=%d" % (0 if bboxes is None else len(bboxes)))
    except Exception:
        log("    det EXC\n" + traceback.format_exc())
    try:
        faces = app.get(frames[i])
        log("    app.get ok n=%d" % len(faces))
    except Exception:
        log("    app.get EXC\n" + traceback.format_exc())

log("=== calib9 done ===")
