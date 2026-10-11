import csv, io, os
import numpy as np

p = r"D:\ai_projects\ComfyUI\output\2026-10-10_wb\_eval\metrics_per_image.csv"
rows = list(csv.DictReader(io.open(p, encoding="utf-8-sig")))
out = []
cols = ["model", "scene", "n_face", "face_area", "face_lap", "skin_hf", "hf_ratio",
        "lap_var", "saturation", "clip_high", "clip_low", "brightness", "blockiness"]
out.append(" | ".join(cols))
for r in rows:
    out.append(" | ".join(str(r.get(c)) for c in cols))

out.append("")
out.append("=== 按模型均值 ===")
keys = ["n_face", "face_area", "face_lap", "skin_hf", "hf_ratio", "lap_var",
        "saturation", "clip_high", "clip_low", "brightness", "blockiness"]
models = ["z_image_turbo", "flux_dev_fp8", "sdxl_realvis", "juggernaut"]
out.append("metric | " + " | ".join(models))
for k in keys:
    vals = []
    for m in models:
        vs = []
        for r in rows:
            if r["model"] != m:
                continue
            try:
                vs.append(float(r[k]))
            except Exception:
                pass
        vals.append("%.5f" % np.mean(vs) if vs else "n/a")
    out.append("%s | %s" % (k, " | ".join(vals)))

out.append("")
out.append("=== 皮肤高频 / 全图高频 比值（越接近1越好，越低越像磨皮）===")
for m in models:
    rs = [r for r in rows if r["model"] == m]
    ratios = []
    for r in rs:
        try:
            sh, oh = float(r["skin_hf"]), float(r["hf_ratio"])
            if oh > 0:
                ratios.append(sh / oh)
        except Exception:
            pass
    out.append("%-16s ratio_mean=%.3f  n=%d" % (m, np.mean(ratios) if ratios else -1, len(ratios)))

with io.open(r"D:\ai_projects\ComfyUI\_peek_eval.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
