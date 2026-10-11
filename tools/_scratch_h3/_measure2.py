# -*- coding: utf-8 -*-
"""最终 A/B 质检：v5_full / v5_pass1 / base(C3同输入) 三方对比。"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import h3_rope_common as H

D22 = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard"
D23 = r"D:\ai_projects\ComfyUI\output\2026-09-23_wb\h3_guard"
OUTD = D22   # 报告统一放这里（与本次 H3 工作同批）

VIDS = [
    ("v5_full", os.path.join(D22, "h3v5_00001_.mp4"),
     "★v5 最终产物：derope 去绳 + lock 锁脸 + SigmaShift + fp16 VAE"),
    ("base_C3_同输入同种子", os.path.join(D23, "h3v5base_00001_.mp4"),
     "对照组：忠实复刻旧 C3（4 步、CodeFormer 0.95、无去绳、无锁脸）"),
    ("v5_pass1_去绳前", os.path.join(D22, "h3v5_pass1baseline_00001_.mp4"),
     "v5 的 pass1 基线（未做去绳重绘）→ 用于隔离「去绳」的净贡献"),
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

H.save_json(os.path.join(OUTD, "measure_ab.json"), rows)

ok = [r for r in rows if "error" not in r]
if ok:
    H.write_report(
        os.path.join(OUTD, "H3_v5_AB对比报告.md"), ok,
        meta={"方案": "v5 full = derope(时序去绳) + lock(面部锁定) + MiniMaxH3SigmaShift",
              "输入": "input/shiling_dance_wave.mp4（三个样本同一输入、同一 seed=42）",
              "人脸参考": "input/characters/v3/C01_FACE_FRONT.png",
              "分辨率/长度": "448x768 / 73 帧 @ 24fps",
              "说明": "base 与 v5 为同输入同种子，可直接对比；v5_pass1 用于隔离去绳贡献"},
        title="H3 人物迁移 v5 · 同输入 A/B 质检报告")

with io.open(os.path.join(HERE, "_measure2_out.txt"), "w", encoding="utf-8") as f:
    f.write("rows=%d ok=%d\n" % (len(rows), len(ok)))
    for r in rows:
        if "error" in r:
            f.write("  %-22s ERROR %s\n" % (r["label"], r["error"]))
            continue
        f.write("  %-22s frames=%s det=%.3f id=%.4f jit=%.4f flk=%.4f "
                "chr=%.4f dv=%.4f mar=%.4f sharp=%.1f\n" % (
                    r["label"], r.get("frames"), r.get("detect_rate", 0),
                    r.get("identity", 0), r.get("jitter_ratio", 0),
                    r.get("flicker_rate", 0), r.get("chroma_var", 0),
                    r.get("detail_var", 0), r.get("mar_std", 0),
                    r.get("frame_sharp", 0)))
