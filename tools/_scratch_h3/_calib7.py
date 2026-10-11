# -*- coding: utf-8 -*-
"""
_quiesce_threads 修复效果验证：只测一个片段，全程对 stderr 加锁。
如果 insightface 的 native 崩溃仍在，faulthandler 会给出 C 层栈。
"""
import sys, os, io, json, traceback, faulthandler, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_calib_now.txt")
fh = open(LOG, "w", encoding="utf-8", buffering=1)


def log(msg):
    fh.write(str(msg) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


log("=== calib7 start %s ===" % time.strftime("%H:%M:%S"))
faulthandler.enable(file=fh, all_threads=True)

import h3_rope_common as H
H._quiesce_threads()
import torch
log("torch threads now = %d" % torch.get_num_threads())

VID = r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4"

log("calling analyze_face_stability ...")
t0 = time.time()
try:
    r = H.analyze_face_stability(VID)
    log("OK in %.1fs" % (time.time() - t0))
    log(json.dumps({k: (float(v) if isinstance(v, (int, float)) else v)
                    for k, v in r.items()}, ensure_ascii=False, indent=2))
except Exception:
    log("EXC after %.1fs\n%s" % (time.time() - t0, traceback.format_exc()))
log("=== calib7 done ===")
