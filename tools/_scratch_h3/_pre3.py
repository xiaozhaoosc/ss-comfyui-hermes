# -*- coding: utf-8 -*-
"""确认输入素材存在，并打印默认参数。"""
import io, os, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "_pre_out.txt")
sys.path.insert(0, HERE)
L = []

import run_h3_guard_v5 as M
L.append("DEFAULTS = %s" % getattr(M, "DEFAULTS", None))

IN = os.path.join(ROOT, "input")
for rel in [M.__dict__.get("DEF_VIDEO", "shiling_dance_wave.mp4"),
            getattr(M, "DEFAULTS", {}).get("video", "")]:
    if rel:
        p = os.path.join(IN, rel)
        L.append("video %-36s exists=%s" % (rel, os.path.exists(p)))

L.append("")
L.append("---- input/ 下的视频 ----")
for ext in ("*.mp4", "*.mov", "*.webm", "*.avi"):
    for p in sorted(glob.glob(os.path.join(IN, ext))):
        L.append("   %-46s %8.2f MB" % (os.path.basename(p),
                                        os.path.getsize(p) / 1048576.0))

L.append("")
L.append("---- input/characters ----")
cd = os.path.join(IN, "characters")
if os.path.isdir(cd):
    for dirpath, dirnames, filenames in os.walk(cd):
        rel = os.path.relpath(dirpath, IN)
        imgs = [n for n in sorted(filenames)
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        if imgs:
            L.append("  [%s]  (%d)" % (rel, len(imgs)))
            for n in imgs[:14]:
                L.append("     %s" % n)
else:
    L.append("  (no input/characters dir)")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
