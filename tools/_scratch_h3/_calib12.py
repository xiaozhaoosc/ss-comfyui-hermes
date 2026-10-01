# -*- coding: utf-8 -*-
"""验证 RetinaFace + ArcFace 直连组合：73 帧全程，含 5 点关键点 + embedding。"""
import sys, os, io, json, traceback, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_calib_now.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib12 start %s ===" % time.strftime("%H:%M:%S"))

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

from insightface.model_zoo import get_model

MD = r"C:\Users\kenzhao\.insightface\models\buffalo_l"
det = get_model(os.path.join(MD, "det_10g.onnx"), providers=["CPUExecutionProvider"])
det.prepare(ctx_id=-1, input_size=(640, 640), det_thresh=0.5)
rec = get_model(os.path.join(MD, "w600k_r50.onnx"), providers=["CPUExecutionProvider"])
rec.prepare(ctx_id=-1)
log("det+rec ready")

# insightface 标准对齐（112x112），用 rec.get 需要 norm_crop
from insightface.utils import face_align
log("face_align ok")

log("--- full loop: detect + align + embed ---")
t0 = time.time()
kps_list, emb_list, bbox_list = [], [], []
for i, fr in enumerate(frames):
    try:
        bboxes, kpss = det.detect(fr, input_size=(640, 640), max_num=0)
    except Exception:
        log("  det EXC at %d\n%s" % (i, traceback.format_exc()))
        break
    if bboxes is None or len(bboxes) == 0:
        kps_list.append(None); emb_list.append(None); bbox_list.append(None)
        continue
    # 取最大
    idx = int(np.argmax((bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])))
    bb = bboxes[idx]; kp = kpss[idx]
    bbox_list.append(bb); kps_list.append(kp)
    try:
        aimg = face_align.norm_crop(fr, landmark=kp, image_size=112)
        feat = rec.get_feat([aimg]).flatten()
        feat = feat / (np.linalg.norm(feat) + 1e-9)
        emb_list.append(feat)
    except Exception:
        log("  rec EXC at %d\n%s" % (i, traceback.format_exc()))
        emb_list.append(None)
    if i % 10 == 0:
        log("  i=%-3d %.3fs/帧 累计%.1fs" % (i, (time.time() - t0) / (i + 1), time.time() - t0))

log("loop done %.1fs 平均%.3fs/帧" % (time.time() - t0, (time.time() - t0) / len(frames)))
log("kps non-none=%d emb non-none=%d" % (
    sum(1 for k in kps_list if k is not None),
    sum(1 for e in emb_list if e is not None)))

# --- 计算关键指标 ---
ok_kps = [k for k in kps_list if k is not None]
arr = np.array([np.asarray(k, dtype=np.float64).ravel() for k in ok_kps])
d1 = np.abs(np.diff(arr, axis=0)).mean(axis=1)
log("landmark 逐差分: mean=%.4f med=%.4f max=%.4f" % (d1.mean(), np.median(d1), d1.max()))

ee = [e for e in emb_list if e is not None]
sims = []
for i in range(len(ee) - 1):
    s = float(np.dot(ee[i], ee[i + 1]))
    sims.append(s)
log("identity 相邻帧余弦: med=%.4f min=%.4f mean=%.4f" % (
    np.median(sims), np.min(sims), np.mean(sims)))

eye_px = []
for k in ok_kps:
    kk = np.asarray(k, dtype=np.float64)
    eye_px.append(float(np.linalg.norm(kk[0] - kk[1])))
log("eye dist px: med=%.2f min=%.2f max=%.2f" % (
    np.median(eye_px), np.min(eye_px), np.max(eye_px)))

log("=== calib12 done ===")
