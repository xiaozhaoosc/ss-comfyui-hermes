# -*- coding: utf-8 -*-
"""
干净顺序、不 import torch 的最终验证：
  1) cv2 读帧
  2) onnxruntime + RetinaFace 检测 73 帧
  3) 像素级 identity + 色度 + 细节 + 光流
全部指标一次算出，确认通路完全稳定。
"""
import sys, os, io, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_calib_now.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib14 start %s ===" % time.strftime("%H:%M:%S"))

import numpy as np
import cv2
log("cv2 %s" % cv2.__version__)

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
    crops.append(None if (x2 - x1 < 4 or y2 - y1 < 4)
                 else cv2.resize(fr[y1:y2, x1:x2], (112, 112), interpolation=cv2.INTER_AREA))
el = time.time() - t0
log("detect+align %.1fs 平均%.3fs/帧" % (el, el / len(frames)))

ok = [k for k in kps_list if k is not None]
log("detect_rate=%.4f (%d/%d)" % (len(ok) / len(frames), len(ok), len(frames)))

arr = np.array([np.asarray(k, dtype=np.float64).ravel() for k in ok])
d1 = np.abs(np.diff(arr, axis=0)).mean(axis=1)
log("lm_diff mean=%.4f med=%.4f p95=%.4f max=%.4f" % (
    d1.mean(), np.median(d1), np.percentile(d1, 95), d1.max()))

# 光流
mags = []
for i in range(0, len(frames) - 1, max(1, len(frames) // 40)):
    if bbox_list[i] is None or bbox_list[i + 1] is None:
        continue
    g1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
    fl = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    mags.append(float(np.mean(np.sqrt(fl[..., 0] ** 2 + fl[..., 1] ** 2))))
gm = float(np.median(mags))
eye_px = [float(np.linalg.norm(np.asarray(k, dtype=np.float64)[0]
                               - np.asarray(k, dtype=np.float64)[1])) for k in ok]
scale = float(np.median(eye_px))
log("global_motion=%.4f eye_px=%.2f" % (gm, scale))
lm_norm = d1.mean() / scale
log("jitter_ratio=%.6f  (lm_norm=%.6f / gm_norm=%.6f)" % (
    lm_norm / (gm / scale + 1e-6), lm_norm, gm / scale))

med = float(np.median(d1))
log("flicker_rate=%.4f" % float(np.mean(d1 > 2.0 * med)))

sims, prev = [], None
for c in crops:
    if c is None:
        prev = None
        continue
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float64).ravel()
    g = g - g.mean()
    if prev is not None:
        na, nb = np.linalg.norm(prev), np.linalg.norm(g)
        if na > 1e-9 and nb > 1e-9:
            sims.append(float(np.dot(prev, g) / (na * nb)))
    prev = g
log("pixel_identity med=%.4f min=%.4f" % (np.median(sims), np.min(sims)))

cs, ds_ = [], []
for c in crops:
    if c is None:
        continue
    lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB).astype(np.float32)
    cs.append([float(lab[..., 1].mean()), float(lab[..., 2].mean())])
    ds_.append(float(cv2.Laplacian(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), cv2.CV_32F).var()))
log("chroma_var=%.5f detail_var=%.5f" % (
    float(np.mean(np.var(np.array(cs), axis=0))),
    float(np.var(ds_) / ((np.mean(ds_) + 1e-6) ** 2))))

log("=== calib14 done 总%.1fs ===" % (time.time() - t0))
