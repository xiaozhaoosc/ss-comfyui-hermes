# -*- coding: utf-8 -*-
"""
把 faulthandler 直接绑到真实 stderr（fd 2），并用 subprocess 把 fd2 重定向到文件。
这样 C 层崩溃栈一定落盘，不会被 Python 的缓冲/异常处理吞掉。
"""
import sys, os, io, json, traceback, faulthandler, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

# ---- 关键：先打开 faulthandler 的真实文件描述符 ----
FDB = open(os.path.join(HERE, "_faulthandler.txt"), "w", encoding="utf-8", buffering=1)
faulthandler.enable(file=FDB, all_threads=True)

LOG = os.path.join(HERE, "_calib_now.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib8 start %s ===" % time.strftime("%H:%M:%S"))

sys.stderr = os.fdopen(os.dup(2), "w", buffering=1)

import numpy as np
import cv2
import torch
log("torch=%s threads=%d" % (torch.__version__, torch.get_num_threads()))

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
    frames.append(fr.copy())
cap.release()
log("frames=%d" % len(frames))

log("--- A: torch.set_num_threads(1) then loop ---")
torch.set_num_threads(1)
for i, fr in enumerate(frames):
    log("  A frame %d" % i)
    try:
        faces = app.get(fr)
        log("    n=%d" % len(faces))
    except Exception:
        log("    EXC\n" + traceback.format_exc())
        break
log("--- A done ---")
log("=== calib8 done ===")
