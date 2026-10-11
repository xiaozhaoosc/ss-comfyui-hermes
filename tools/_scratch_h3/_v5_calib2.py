# -*- coding: utf-8 -*-
"""Run the calibration in-process with full traceback captured to a file."""
import io, os, sys, traceback

LOG = r"D:\ai_projects\ComfyUI\_calib_log.txt"
buf = io.StringIO()

old_out, old_err = sys.stdout, sys.stderr
sys.stdout = buf
sys.stderr = buf
try:
    sys.path.insert(0, r"D:\ai_projects\ComfyUI\tools")
    import h3_rope_common as C

    D = r"D:\ai_projects\ComfyUI\output\2026-09-21"
    CANDS = [
        "shiling_sayyes_h3_yolo_00001-audio.mp4",
        "shiling_sayyes_h3_c3_00001-audio.mp4",
        "shiling_sayyes_h3_opt_00001-audio.mp4",
        "shiling_h3_c3_test_00001-audio.mp4",
        "shiling_whiskey_h3_c3_00001-audio.mp4",
    ]
    vids = [os.path.join(D, f) for f in CANDS if os.path.isfile(os.path.join(D, f))]
    print("found %d clips" % len(vids), flush=True)

    d = C.out_dir("h3_guard")
    res = []
    for v in vids:
        label = os.path.splitext(os.path.basename(v))[0]
        try:
            r = C.analyze_face_stability(v, label=label)
            res.append(r)
            print("  OK   %-44s det=%.3f id=%s jit=%s flick=%s" % (
                label[:44], r["detect_rate"], C.fmt(r["identity"], 4),
                C.fmt(r["jitter_ratio"], 4), C.fmt(r["flicker_rate"], 4)), flush=True)
        except Exception:
            print("  FAIL %-44s" % label[:44], flush=True)
            traceback.print_exc(file=buf)

    if res:
        rp = C.write_report(os.path.join(d, "baseline_calibration.md"), res,
                            meta={"说明": "对现网 C3/yolo 产物的基线标定",
                                  "检测器": res[0].get("detector")},
                            title="H3 基线标定（现网产物）")
        C.save_json(os.path.join(d, "baseline_calibration.json"), res)
        print("REPORT: %s" % rp, flush=True)
except Exception:
    traceback.print_exc(file=buf)
finally:
    sys.stdout, sys.stderr = old_out, old_err
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print("wrote", LOG)
