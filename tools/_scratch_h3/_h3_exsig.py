# -*- coding: utf-8 -*-
"""Verify every class_type used in the ref2va_audioinit example exists and print its signature."""
import json, urllib.request

COMFY = "http://127.0.0.1:8188"
EX = r"D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-MAINodes\examples\motion_pipeline_ref2va_audioinit_api.json"
OUT = r"D:\ai_projects\ComfyUI\_ex_sig.txt"

with open(EX, "r", encoding="utf-8") as f:
    wf = json.load(f)

used = {}
for nid, n in wf.items():
    used.setdefault(n["class_type"], []).append(nid)

with urllib.request.urlopen(COMFY + "/object_info", timeout=60) as r:
    info = json.loads(r.read().decode("utf-8"))

lines = []
lines.append("=== class_types used in example (%d) ===" % len(used))
missing = []
for ct in sorted(used):
    ok = ct in info
    if not ok:
        missing.append(ct)
    lines.append("  %-52s nodes=%s  %s" % (ct, ",".join(used[ct]), "OK" if ok else "*** MISSING ***"))

lines.append("")
lines.append("=== MISSING: %s ===" % (missing or "none"))

lines.append("")
lines.append("=" * 70)
lines.append("SIGNATURES")
lines.append("=" * 70)
for ct in sorted(used):
    d = info.get(ct)
    if not d:
        continue
    lines.append("")
    lines.append("--- %s ---" % ct)
    lines.append("  out: %s %s" % (d.get("output"), d.get("output_name")))
    for sect in ("required", "optional"):
        s = (d.get("input") or {}).get(sect) or {}
        if not s:
            continue
        lines.append("  [%s]" % sect)
        for k, v in s.items():
            t = v[0] if isinstance(v, list) and v else v
            if isinstance(t, list):
                t = "ENUM%s" % (str(t[:10]),)
            ex = v[1] if isinstance(v, list) and len(v) > 1 and isinstance(v[1], dict) else {}
            bits = []
            for kk in ("default", "min", "max"):
                if kk in ex:
                    bits.append("%s=%s" % (kk, ex[kk]))
            lines.append("    %-28s %-32s %s" % (k, t, " ".join(bits)))

# Also list every H3-ish class_type available, to know what else we can use
lines.append("")
lines.append("=" * 70)
lines.append("ALL available class_types containing H3 or MiniMax or SAGE or ReActor")
lines.append("=" * 70)
for ct in sorted(info):
    low = ct.lower()
    if ("h3" in low or "minimax" in low or "sage" in low
            or "reactor" in low or "audio" in low or "lora" in low):
        lines.append("  " + ct)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
