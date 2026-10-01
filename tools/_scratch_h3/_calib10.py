# -*- coding: utf-8 -*-
"""
验证「累积型崩溃」假设：
  A) 循环 app.get(frames[0]) 重复 100 次（同一帧）→ 如果仍崩，就是纯累积问题
  B) 用 ort 会话级 API 直接推理，绕过 insightface，看是否还崩
  C) 每次 get 后打印 RSS，看是否单调增长
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


def rss_mb():
    try:
        import ctypes, ctypes.wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.wintypes.DWORD),
                        ("PageFaultCount", ctypes.wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.WorkingSetSize / 1048576.0
    except Exception:
        return -1.0


log("=== calib10 start %s ===" % time.strftime("%H:%M:%S"))
log("RSS at start = %.1f MB" % rss_mb())

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
log("frames=%d RSS=%.1f MB" % (len(frames), rss_mb()))

import insightface
log("insightface at %s" % os.path.dirname(insightface.__file__))

from insightface.app import FaceAnalysis
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1, det_size=(640, 640))
log("ready RSS=%.1f MB" % rss_mb())

log("--- A: repeat app.get(frames[0]) x 120 ---")
t0 = time.time()
for k in range(120):
    try:
        f_ = app.get(frames[0])
    except Exception:
        log("  EXC at k=%d\n%s" % (k, traceback.format_exc()))
        break
    if k % 10 == 0:
        log("  k=%-4d RSS=%.1f MB  n=%d  %.1fs" % (k, rss_mb(), len(f_), time.time() - t0))
log("--- A done RSS=%.1f MB total=%.1fs ---" % (rss_mb(), time.time() - t0))

log("=== calib10 done ===")
