# -*- coding: utf-8 -*-
"""在 h3_rope_common 内部逐行追踪，定位 analyze_face_stability 的崩溃点。"""
import sys, os, io, json, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_calib_log.txt")


def log(msg):
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
        f.flush()
        os.fsync(f.fileno())


with io.open(LOG, "w", encoding="utf-8") as f:
    f.write("=== calib4 start ===\n")

import numpy as np
import cv2
import h3_rope_common as H

VID = r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4"

log("A) _face_detector()")
try:
    name, det = H._face_detector()
    log("   name=%r det=%s" % (name, det))
except Exception:
    log("   EXC\n" + traceback.format_exc())
    sys.exit(1)

log("B) _read_frames()")
try:
    frames, fps, W, Hh, N = H._read_frames(VID, max_frames=0)
    log("   frames=%d fps=%s W=%s H=%s N=%s" % (len(frames), fps, W, Hh, N))
    log("   frame0 dtype=%s shape=%s" % (frames[0].dtype, frames[0].shape))
except Exception:
    log("   EXC\n" + traceback.format_exc())
    sys.exit(1)

log("C) detect on first frame")
try:
    ds = det(frames[0])
    log("   len(ds)=%d" % len(ds))
    if ds:
        d0 = ds[0]
        log("   keys=%s" % list(d0.keys()))
        for k, v in d0.items():
            if v is None:
                log("     %s = None" % k)
            else:
                a = np.asarray(v)
                log("     %s type=%s shape=%s dtype=%s" % (k, type(v).__name__, a.shape, a.dtype))
except Exception:
    log("   EXC\n" + traceback.format_exc())
    sys.exit(1)

log("D) detect all frames + crop")
try:
    n_none = 0
    for i, fr in enumerate(frames):
        d = det(fr)
        if not d:
            n_none += 1
        else:
            pass
    log("   done. frames=%d none=%d" % (len(frames), n_none))
except Exception:
    log("   EXC\n" + traceback.format_exc())
    sys.exit(1)

log("E) crops + lab")
try:
    for i, fr in enumerate(frames[:5]):
        d = det(fr)
        if d:
            c = H._crop_resize(fr, d[0]["bbox"])
            log("   i=%d crop=%s" % (i, None if c is None else c.shape))
            if c is not None:
                lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB).astype(np.float32)
                log("     lab ok %s" % (lab.shape,))
except Exception:
    log("   EXC\n" + traceback.format_exc())
    sys.exit(1)

log("F) optical flow")
try:
    g1 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(frames[1], cv2.COLOR_BGR2GRAY)
    fl = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    log("   flow %s mag=%f" % (fl.shape, float(np.mean(np.sqrt(fl[..., 0] ** 2 + fl[..., 1] ** 2)))))
except Exception:
    log("   EXC\n" + traceback.format_exc())
    sys.exit(1)

log("G) full analyze_face_stability")
try:
    r = H.analyze_face_stability(VID)
    log("   OK %s" % json.dumps({k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                                for k, v in r.items()}, ensure_ascii=False))
except Exception:
    log("   EXC\n" + traceback.format_exc())

log("=== calib4 done ===")
