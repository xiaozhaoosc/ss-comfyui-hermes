# -*- coding: utf-8 -*-
"""在现有 C3 基线片段上校准人脸稳定性指标 —— 加固版：每步立即落盘。"""
import sys, os, io, json, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_calib_log.txt")


def log(msg):
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
        f.flush()
        os.fsync(f.fileno())


# 每次运行清空日志
with io.open(LOG, "w", encoding="utf-8") as f:
    f.write("=== calib3 start ===\n")

log("step1: import h3_rope_common")
import h3_rope_common as H
log("step1: ok")

log("step2: probe ffmpeg / cv2 / insightface")
try:
    import cv2
    log("  cv2 %s" % cv2.__version__)
except Exception as e:
    log("  cv2 FAIL %r" % (e,))
try:
    import insightface
    log("  insightface %s" % getattr(insightface, "__version__", "?"))
except Exception as e:
    log("  insightface FAIL %r" % (e,))

log("step3: locate baseline clips")
CAND_DIRS = [
    r"D:\ai_projects\ComfyUI\output\2026-09-21",
    r"D:\ai_projects\ComfyUI\output\2026-09-21_wb",
    r"D:\ai_projects\ComfyUI\output",
]
CANDS = [
    "shiling_sayyes_h3_yolo_00001-audio.mp4",
    "shiling_sayyes_h3_c3_00001-audio.mp4",
    "shiling_sayyes_h3_opt_00001-audio.mp4",
    "shiling_h3_c3_test_00001-audio.mp4",
    "shiling_whiskey_h3_c3_00001-audio.mp4",
]

found = []
for c in CANDS:
    for d in CAND_DIRS:
        p = os.path.join(d, c)
        if os.path.isfile(p):
            found.append((c, p))
            break
log("  found %d/%d" % (len(found), len(CANDS)))
for c, p in found:
    log("    %s -> %.1f MB" % (c, os.path.getsize(p) / 1e6))

if not found:
    log("no clips found; listing output/2026-09-21 for *.mp4")
    d = CAND_DIRS[0]
    if os.path.isdir(d):
        for n in sorted(os.listdir(d)):
            if n.lower().endswith((".mp4", ".webm", ".mkv")):
                log("    - %s" % n)
    log("=== calib3 abort (no clips) ===")
    sys.exit(0)

log("step4: measure")
rows = []
for i, (c, p) in enumerate(found):
    log("[%d/%d] %s" % (i + 1, len(found), c))
    try:
        r = H.analyze_face_stability(p)
        r["clip"] = c
        rows.append(r)
        log("  -> %s" % json.dumps({k: (round(v, 4) if isinstance(v, float) else v)
                                    for k, v in r.items() if k != "per_frame"},
                                   ensure_ascii=False))
    except Exception:
        log("  EXC:\n" + traceback.format_exc())

log("step5: score")
try:
    scored = H.score_rows(rows)
    log(json.dumps(scored, ensure_ascii=False, indent=2))
except Exception:
    log("score EXC:\n" + traceback.format_exc())

log("=== calib3 done ===")
