# -*- coding: utf-8 -*-
"""最终形态验证：只用 RetinaFace(检测+5点) + 像素级 identity，跑完 73 帧。"""
import sys, os, io, json, traceback, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_calib_now.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib13 start %s ===" % time.strftime("%H:%M:%S"))

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
log("RetinaFace ready")

t0 = time.time()
kps_list, bbox_list, crops = [], [], []
for i, fr in enumerate(frames):
    bboxes, kpss = det.detect(fr, input_size=(640, 640), max_num=0)
    if bboxes is None or len(bboxes) == 0:
        kps_list.append(None); bbox_list.append(None); crops.append(None)
        continue
    idx = int(np.argmax((bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])))
    kp = kpss[idx]; bb = bboxes[idx]
    kps_list.append(kp); bbox_list.append(bb)
    x1, y1, x2, y2 = [int(round(v)) for v in bb]
    H, W = fr.shape[:2]
    x1 = max(0, x1); y1 = max(0, y1); x2 = min(W, x2); y2 = min(H, y2)
    if x2 - x1 < 4 or y2 - y1 < 4:
        crops.append(None)
    else:
        crops.append(cv2.resize(fr[y1:y2, x1:x2], (112, 112), interpolation=cv2.INTER_AREA))
log("loop %.1fs 平均%.3fs/帧" % (time.time() - t0, (time.time() - t0) / len(frames)))

ok = [k for k in kps_list if k is not None]
log("detected=%d/%d" % (len(ok), len(frames)))

arr = np.array([np.asarray(k, dtype=np.float64).ravel() for k in ok])
d1 = np.abs(np.diff(arr, axis=0)).mean(axis=1)
log("lm diff mean=%.4f med=%.4f p95=%.4f max=%.4f" % (
    d1.mean(), np.median(d1), np.percentile(d1, 95), d1.max()))

# 像素级 identity
sims = []
prev = None
for c in crops:
    if c is None:
        prev = None
        continue
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float64).ravel()
    g = g - g.mean()
    if prev is not None:
        a = prev; b = g
        na = np.linalg.norm(a); nb = np.linalg.norm(b)
        if na > 1e-9 and nb > 1e-9:
            sims.append(float(np.dot(a, b) / (na * nb)))
    prev = g
log("pixel-identity med=%.4f min=%.4f mean=%.4f" % (
    np.median(sims), np.min(sims), np.mean(sims)))

# 色度 / 细节
cs, ds_ = [], []
for c in crops:
    if c is None:
        continue
    lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB).astype(np.float32)
    cs.append([float(lab[..., 1].mean()), float(lab[..., 2].mean())])
    ds_.append(float(cv2.Laplacian(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY),
                                  cv2.CV_32F).var()))
cs = np.array(cs)
log("chroma_var=%.5f detail_var=%.5f" % (float(np.mean(np.var(cs, axis=0))),
                                         float(np.var(ds_) / ((np.mean(ds_) + 1e-6) ** 2))))

log("=== calib13 done 总耗时%.1fs ===" % (time.time() - t0))
