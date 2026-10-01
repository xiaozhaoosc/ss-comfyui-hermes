# -*- coding: utf-8 -*-
import json, sys, urllib.request
sys.path.insert(0, r"D:\ai_projects\ComfyUI\tools")
import h3_rope_common as C

info = C.object_info()
OUT = r"D:\ai_projects\ComfyUI\_sig_fix.txt"
lines = []
for name in ["H3SaveHoldMap", "H3LoadHoldMap", "H3V2VInit", "H3JerkOracle"]:
    d = info.get(name)
    if not d:
        lines.append("%s : NOT FOUND" % name); continue
    lines.append("--- %s ---" % name)
    lines.append("  out: %s %s" % (d.get("output"), d.get("output_name")))
    for sect in ("required", "optional"):
        s = (d.get("input") or {}).get(sect) or {}
        if not s: continue
        lines.append("  [%s]" % sect)
        for k, v in s.items():
            t = v[0] if isinstance(v, list) and v else v
            if isinstance(t, list): t = "ENUM%s" % (str(t[:8]),)
            ex = v[1] if isinstance(v, list) and len(v) > 1 and isinstance(v[1], dict) else {}
            lines.append("    %-26s %-30s %s" % (k, t, ex.get("default", "")))
    lines.append("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("OK")
