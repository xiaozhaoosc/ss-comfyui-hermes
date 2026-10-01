# -*- coding: utf-8 -*-
"""找出确切死亡帧号 + 打印每次 detect 的耗时与 RSS，定位资源耗尽点。"""
import sys, os, io, json, time, ctypes, ctypes.wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_calib_now.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


class PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.wintypes.DWORD), ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def mem():
    try:
        p = PMC(); p.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(p), p.cb)
        return p.WorkingSetSize / 1048576.0, p.PagefileUsage / 1048576.0
    except Exception:
        return -1.0, -1.0


def hcount():
    """当前进程 handle 数"""
    try:
        n = ctypes.wintypes.DWORD(0)
        ctypes.windll.kernel32.GetProcessHandleCount(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(n))
        return n.value
    except Exception:
        return -1


log("=== calib15 %s ===" % time.strftime("%H:%M:%S"))

import numpy as np
import cv2

VID = r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4"
cap = cv2.VideoCapture(VID)
frames = []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    frames.append(fr.copy())
cap.release()
log("frames=%d mem=%.1f/%.1f handles=%d" % ((len(frames),) + mem() + (hcount(),)))

from insightface.model_zoo import get_model
MD = r"C:\Users\kenzhao\.insightface\models\buffalo_l"
det = get_model(os.path.join(MD, "det_10g.onnx"), providers=["CPUExecutionProvider"])
det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)
log("ready mem=%.1f/%.1f handles=%d" % (mem() + (hcount(),)))

for i, fr in enumerate(frames):
    t = time.time()
    bboxes, kpss = det.detect(fr, input_size=(640, 640), max_num=0)
    dt = time.time() - t
    ws, pf = mem()
    log("i=%-3d det=%.3fs n=%d mem=%.1f/%.1f handles=%d" % (
        i, dt, 0 if bboxes is None else len(bboxes), ws, pf, hcount()))

log("=== calib15 done ===")
