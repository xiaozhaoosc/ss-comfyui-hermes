# -*- coding: utf-8 -*-
"""
环境级排查：opencv / onnxruntime / torch 三个 native 库互相冲突。
逐步加载不同组合并跑循环，看哪一步开始不稳。
每步结果立即落盘。
"""
import sys, os, io, json, traceback, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_probe_dll.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== probe_dll %s ===" % time.strftime("%H:%M:%S"))
log("python=%s" % sys.version.replace("\n", " "))
log("cv2 dir=%s" % os.path.dirname(__import__("cv2").__file__)
    if __import__("importlib").util.find_spec("cv2") else "cv2 missing")

log("--- T1: only cv2, read all frames ---")
import cv2
log("cv2 %s from %s" % (cv2.__version__, os.path.dirname(cv2.__file__)))
VID = r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4"
cap = cv2.VideoCapture(VID)
frames = []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    frames.append(fr.copy())
cap.release()
log("T1 frames=%d OK" % len(frames))

log("--- T2: load onnxruntime, create RetinaFace session, no inference ---")
import onnxruntime as ort
log("ort %s providers=%s" % (ort.__version__, ort.get_available_providers()))
from insightface.model_zoo import get_model
MD = r"C:\Users\kenzhao\.insightface\models\buffalo_l"
det = get_model(os.path.join(MD, "det_10g.onnx"), providers=["CPUExecutionProvider"])
det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)
log("T2 session created OK")

log("--- T3: 5 inferences ---")
for i in range(5):
    b, k = det.detect(frames[i], input_size=(640, 640), max_num=0)
    log("  T3 i=%d n=%s" % (i, 0 if b is None else len(b)))
log("T3 OK")

log("--- T4: import torch, then 20 inferences ---")
import torch
log("torch %s threads=%d" % (torch.__version__, torch.get_num_threads()))
for i in range(20):
    b, k = det.detect(frames[i], input_size=(640, 640), max_num=0)
    log("  T4 i=%d n=%s" % (i, 0 if b is None else len(b)))
log("T4 OK")

log("=== probe_dll done ===")
