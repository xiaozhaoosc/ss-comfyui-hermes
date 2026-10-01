# -*- coding: utf-8 -*-
"""对 full profile 的产物做质检，并与 C3 基线对比，输出报告。"""
import io, os, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import h3_rope_common as H

ROOT = H.out_root()
GD = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard"

VIDS = [
    ("v5_full", os.path.join(GD, "h3v5_00001_.mp4"),
     "★v5 full 最终产物（derope 去绳 + lock 锁脸 + SigmaShift）"),
    ("v5_pass1_derope前", os.path.join(GD, "h3v5_pass1baseline_00001_.mp4"),
     "v5 的 pass1 基线（未经去绳重绘）—— 用于看去绳的净贡献"),
    ("c3_baseline_sayyes", r"D:\ai_projects\ComfyUI\output\2026-09-21\shiling_sayyes_h3_yolo_00001-audio.mp4",
     "旧 C3 基线（报告里'还在闪'的那个，仅作参照）"),
]

rows = []
for label, p, note in VIDS:
    if not os.path.exists(p):
        rows.append({"label": label, "path": p, "note": note,
                     "error": "FILE MISSING"})
        continue
    try:
        r = H.analyze_face_stability(p, label=label)
        r["note"] = note
        rows.append(r)
    except Exception as e:
        rows.append({"label": label, "path": p, "note": note,
                     "error": "%s: %s" % (type(e).__name__, e)})

H.save_json(os.path.join(GD, "measure_full.json"), rows)

ok_rows = [r for r in rows if "error" not in r]
if ok_rows:
    p = H.write_report(
        os.path.join(GD, "H3_full_质检报告.md"), ok_rows,
        meta={"方案": "full = derope + lock + MiniMaxLowVRAMAttention",
              "输入": "input/shiling_dance_wave.mp4",
              "人脸参考": "input/characters/v3/C01_FACE_FRONT.png",
              "样本": "%d 个片段（其中 1 个为旧 C3 基线，仅作参照）" % len(ok_rows)},
        title="H3 full profile · 人脸时序稳定性质检")

with io.open(os.path.join(HERE, "_measure_out.txt"), "w", encoding="utf-8") as f:
    f.write("rows=%d ok=%d\n" % (len(rows), len(ok_rows)))
    for r in rows:
        if "error" in r:
            f.write("  %-22s ERROR %s\n" % (r["label"], r["error"]))
        else:
            f.write("  %-22s frames=%s det=%.3f id=%.4f jit=%.4f flk=%.4f "
                    "chr=%.4f det_v=%.4f mar=%.4f sharp=%.1f  (%.1fs)\n" % (
                        r["label"], r.get("frames"), r.get("detect_rate", 0),
                        r.get("identity", 0), r.get("jitter_ratio", 0),
                        r.get("flicker_rate", 0), r.get("chroma_var", 0),
                        r.get("detail_var", 0), r.get("mar_std", 0),
                        r.get("frame_sharp", 0), r.get("sec_total", 0)))
