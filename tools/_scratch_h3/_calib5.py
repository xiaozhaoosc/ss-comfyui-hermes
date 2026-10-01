# -*- coding: utf-8 -*-
"""逐帧调用 insightface 检测，找出第几帧崩、抛什么异常（含 native 崩溃兜底）。"""
import sys, os, io, json, traceback, faulthandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_calib_log.txt")
fh = open(LOG, "w", encoding="utf-8")


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib5 start ===")
faulthandler.enable(file=fh, all_threads=True)

import numpy as np
import cv2
from insightface.app import FaceAnalysis

app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1, det_size=(640, 640))
log("insightface ready")

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

for i, fr in enumerate(frames):
    log("frame %d shape=%s contig=%s" % (i, fr.shape, fr.flags["C_CONTIGUOUS"]))
    try:
        faces = app.get(fr)
    except Exception:
        log("  app.get EXC at frame %d:\n%s" % (i, traceback.format_exc()))
        break
    if not faces:
        log("  no face")
        continue
    f = faces[0]
    log("  ok bbox=%s kps=%s emb=%s" % (
        np.asarray(f.bbox).round(1).tolist(),
        None if getattr(f, "kps", None) is None else np.asarray(f.kps).shape,
        None if getattr(f, "normed_embedding", None) is None else np.asarray(f.normed_embedding).shape))
log("=== calib5 done ===")
