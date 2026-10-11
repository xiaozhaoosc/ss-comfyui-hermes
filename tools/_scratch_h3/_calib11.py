# -*- coding: utf-8 -*-
"""
★绕开 insightface 的 FaceAnalysis 高层封装。
只用 RetinaFace 检测器做「检出 + 5点关键点 + bbox」，
另外单独用 ArcFace 做 embedding —— 但按需、且分批。

目的：
  1) 确认崩溃是否来自 FaceAnalysis.get 的某个子模型（landmark/genderage）
  2) 验证 RetinaFace + ArcFace 直连能否稳定跑完 73 帧
  3) 测出单帧耗时
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


log("=== calib11 start %s ===" % time.strftime("%H:%M:%S"))

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

import onnxruntime as ort
from insightface.model_zoo import get_model

MODEL_DIR = os.path.join(os.path.dirname(__import__("insightface").__file__),
                         "..", "..", "..", "models", "insightface", "models", "buffalo_l")

# 尝试从 insightface 默认缓存目录找模型
CAND = [
    os.path.expanduser(r"~\.insightface\models\buffalo_l"),
    r"D:\ai_projects\ComfyUI\models\insightface\models\buffalo_l",
    r"D:\ai_projects\ComfyUI\models\insightface\buffalo_l",
    r"D:\ai_projects\ComfyUI\models\insightface",
]
md = None
for c in CAND:
    if os.path.isdir(c):
        log("candidate dir exists: %s -> %s" % (c, sorted(os.listdir(c))[:12]))
        if any(n.endswith(".onnx") for n in os.listdir(c)):
            md = c
            break
if md is None:
    for c in CAND:
        if os.path.isdir(c):
            md = c
log("model dir = %s" % md)

log("ort providers=%s" % ort.get_available_providers())

# 直接构造 RetinaFace
if md:
    dp = os.path.join(md, "det_10g.onnx")
    log("det path exists=%s %s" % (os.path.exists(dp), dp))
    if os.path.exists(dp):
        t0 = time.time()
        det = get_model(dp, providers=["CPUExecutionProvider"])
        det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)
        log("RetinaFace loaded in %.1fs" % (time.time() - t0))

        log("--- detect 73 frames ---")
        t0 = time.time()
        n_ok = 0
        for i, fr in enumerate(frames):
            try:
                bboxes, kpss = det.detect(fr, input_size=(640, 640), max_num=0)
                if bboxes is not None and len(bboxes):
                    n_ok += 1
                if i % 10 == 0:
                    log("  i=%-3d %.2fs/帧 累计%.1fs ok=%d" % (
                        i, (time.time() - t0) / max(1, i + 1), time.time() - t0, n_ok))
            except Exception:
                log("  EXC at i=%d\n%s" % (i, traceback.format_exc()))
                break
        log("detect done %.1fs ok=%d/%d 平均%.3fs/帧" % (
            time.time() - t0, n_ok, len(frames), (time.time() - t0) / len(frames)))

log("=== calib11 done ===")
