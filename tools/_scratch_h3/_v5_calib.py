# -*- coding: utf-8 -*-
"""Baseline calibration: measure existing C3/yolo outputs so the metric is anchored
against a clip the user already diagnosed as 'face still flickers'."""
import os, sys
sys.path.insert(0, r"D:\ai_projects\ComfyUI\tools")
import h3_rope_common as C

D = r"D:\ai_projects\ComfyUI\output\2026-09-21"
CANDIDATES = [
    "shiling_sayyes_h3_yolo_00001-audio.mp4",   # 报告认定的"仍有细微抖动"基线
    "shiling_sayyes_h3_c3_00001-audio.mp4",     # 更早的 C3 版本
    "shiling_sayyes_h3_opt_00001-audio.mp4",
    "shiling_h3_c3_test_00001-audio.mp4",
    "shiling_whiskey_h3_c3_00001-audio.mp4",
]

vids = [os.path.join(D, f) for f in CANDIDATES if os.path.isfile(os.path.join(D, f))]
print("found %d clips" % len(vids))

d = C.out_dir("h3_guard")
res = []
for v in vids:
    label = os.path.splitext(os.path.basename(v))[0]
    try:
        r = C.analyze_face_stability(v, label=label)
        res.append(r)
        print("  OK  %-46s det=%.3f id=%s jit=%s" % (
            label[:46], r["detect_rate"], C.fmt(r["identity"], 4),
            C.fmt(r["jitter_ratio"], 4)))
    except Exception as e:
        print("  FAIL %-46s %r" % (label[:46], e))

if res:
    rp = C.write_report(os.path.join(d, "baseline_calibration.md"), res,
                        meta={"说明": "对现网 C3/yolo 产物的基线标定",
                              "检测器": res[0].get("detector"),
                              "用途": "验证抖动指标能区分不同质量的换脸结果"},
                        title="H3 基线标定（现网 C3 产物）")
    C.save_json(os.path.join(d, "baseline_calibration.json"), res)
    print("报告:", rp)
