# -*- coding: utf-8 -*-
"""列出最终交付物，确认存在。"""
import io, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ITEMS = [
    os.path.join(ROOT, "output", "2026-09-22_wb", "h3_guard", "h3v5_00001_.mp4"),
    os.path.join(ROOT, "output", "2026-09-22_wb", "h3_guard", "h3v5_pass1baseline_00001_.mp4"),
    os.path.join(ROOT, "output", "2026-09-22_wb", "h3_guard", "H3人物迁移优化方案_v5.md"),
    os.path.join(ROOT, "output", "2026-09-22_wb", "h3_guard", "H3_v5_AB对比报告.md"),
    os.path.join(ROOT, "output", "2026-09-22_wb", "h3_guard", "measure_ab.json"),
    os.path.join(ROOT, "output", "2026-09-22_wb", "h3_guard", "calib_baseline_report.md"),
    os.path.join(ROOT, "output", "2026-09-23_wb", "h3_guard", "h3v5base_00001_.mp4"),
    os.path.join(ROOT, "tools", "run_h3_guard_v5.py"),
    os.path.join(ROOT, "tools", "h3_rope_common.py"),
    os.path.join(ROOT, "workflows", "v5", "h3_guard_v5_full_api.json"),
    os.path.join(ROOT, "workflows", "v5", "h3_guard_v5_base_api.json"),
]

L = ["now=%s" % time.strftime("%Y-%m-%d %H:%M:%S"), ""]
for p in ITEMS:
    ok = os.path.exists(p)
    sz = os.path.getsize(p) if ok else 0
    L.append("%-6s %9d  %s" % ("OK" if ok else "MISS", sz, p))

with io.open(os.path.join(HERE, "_final_out.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
