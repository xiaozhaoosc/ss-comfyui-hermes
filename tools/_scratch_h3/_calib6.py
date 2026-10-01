# -*- coding: utf-8 -*-
"""用 torch 在崩溃帧跑 buffalo_l 的各个子模型，定位是哪一个子模型崩溃。"""
import sys, os, io, json, traceback, faulthandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_calib_log.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib6 start ===")
faulthandler.enable(file=fh, all_threads=True)

import numpy as np
import cv2
import torch
from insightface.app import FaceAnalysis

log("torch=%s threads=%d" % (torch.__version__, torch.get_num_threads()))
try:
    torch.set_num_threads(1)
    log("set_num_threads(1) ok")
except Exception:
    log("set_num_threads EXC\n" + traceback.format_exc())

app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1, det_size=(640, 640))
log("insightface ready; models=%s" % [m.__class__.__name__ for m in app.models.values()])

VID = r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4"
cap = cv2.VideoCapture(VID)
frames = []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    frames.append(fr)
cap.release()
log("frames=%d" % len(frames))

FR = 17
fr = frames[FR].copy()
log("target frame %d shape=%s" % (FR, fr.shape))

det_model = None
rec_model = None
for k, m in app.models.items():
    log("  model key=%s class=%s input=%s" % (k, m.__class__.__name__,
                                              getattr(m, "input_shape", None)))
    if m.__class__.__name__ in ("SCRFD",):
        det_model = m
    if "recognition" in k or m.__class__.__name__ in ("ArcFaceONNX",):
        rec_model = m

log("det_model=%s" % (det_model.__class__.__name__ if det_model else None))

log("--- step: det_model.detect ---")
try:
    bboxes, kpss = det_model.detect(fr, input_size=(640, 640), max_num=0)
    log("  ok bboxes=%s" % (np.asarray(bboxes).shape,))
except Exception:
    log("  EXC\n" + traceback.format_exc())

log("--- step: app.get ---")
try:
    faces = app.get(fr)
    log("  ok n=%d" % len(faces))
except Exception:
    log("  EXC\n" + traceback.format_exc())

log("--- step: loop frames 15..25 with single-thread ---")
for i in range(15, min(26, len(frames))):
    log("  frame %d ..." % i)
    try:
        f_ = app.get(frames[i].copy())
        log("    n=%d" % len(f_))
    except Exception:
        log("    EXC\n" + traceback.format_exc())
        break

log("=== calib6 done ===")
