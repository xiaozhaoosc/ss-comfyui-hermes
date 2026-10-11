# -*- coding: utf-8 -*-
"""Diff the official example (PASSES) against our base graph (FAILS) to find the
structural difference that triggers `unhashable type: 'list'` on SamplerCustomAdvanced."""
import json, sys
sys.path.insert(0, r"D:\ai_projects\ComfyUI\tools")
import h3_rope_common as C
import run_h3_guard_v5 as V

EX = r"D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-MAINodes\examples\motion_pipeline_ref2va_audioinit_api.json"
OUT = r"D:\ai_projects\ComfyUI\_diag_diff.txt"

with open(EX, encoding="utf-8") as f:
    ex = json.load(f)

base = V.build_graph("base", video="shiling_dance_wave.mp4",
                     char="characters/v3/C01_FACE_FRONT.png", bg=None,
                     width=448, height=768, length=73, seed=42, fps=24.0,
                     prefix="diag/base")

lines = []


def find_sampler(g):
    for nid, n in g.items():
        if n["class_type"] == "SamplerCustomAdvanced":
            return nid, n
    return None, None


for tag, g in (("EXAMPLE", ex), ("OURS", base)):
    sid, s = find_sampler(g)
    lines.append("=" * 66)
    lines.append("%s  SamplerCustomAdvanced = node %s" % (tag, sid))
    lines.append("  inputs: %s" % json.dumps(s["inputs"], ensure_ascii=False))
    # resolve each input to the producing node
    for k, v in s["inputs"].items():
        if isinstance(v, list) and len(v) == 2:
            src = g.get(str(v[0]))
            lines.append("    %-14s <- node %-5s slot %s  (%s)" % (
                k, v[0], v[1], src["class_type"] if src else "MISSING"))
    lines.append("")
    # what does latent_image point at, and what are ITS outputs?
    li = s["inputs"].get("latent_image")
    if li:
        src = g.get(str(li[0]))
        if src:
            lines.append("  latent_image source %s (%s) inputs: %s" % (
                li[0], src["class_type"],
                json.dumps({k: (v if not isinstance(v, list) else v) for k, v in src["inputs"].items()},
                           ensure_ascii=False)[:400]))
    lines.append("")

# also compare node-count / types
lines.append("=" * 66)
ex_types = sorted({n["class_type"] for n in ex.values()})
our_types = sorted({n["class_type"] for n in base.values()})
lines.append("types only in EXAMPLE: %s" % [t for t in ex_types if t not in our_types])
lines.append("types only in OURS   : %s" % [t for t in our_types if t not in ex_types])

# Check the ResolutionSelector usage: example passes width/height as links,
# we pass ints. Also example passes length as a link.
lines.append("")
lines.append("example Ref2VA width/height/length inputs:")
for nid, n in ex.items():
    if n["class_type"] == "MiniMaxH3ReferenceToVideo":
        for k in ("width", "height", "length"):
            lines.append("   %s = %s" % (k, n["inputs"].get(k)))
        break
lines.append("ours Ref2VA width/height/length inputs:")
for nid, n in base.items():
    if n["class_type"] == "MiniMaxH3ReferenceToVideo":
        for k in ("width", "height", "length"):
            lines.append("   %s = %s" % (k, n["inputs"].get(k)))
        break

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
