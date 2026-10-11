# -*- coding: utf-8 -*-
"""搜索 ComfyUI 服务端日志里的告警/报错，定位黑屏原因。"""
import io, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = r"D:\ai_projects\ComfyUI\output\_comfyui_start.log"
OUT = os.path.join(HERE, "_srvlog_out.txt")


def dec(raw):
    for enc in ("utf-8", "gbk", "utf-16", "utf-16-le"):
        try:
            t = raw.decode(enc)
        except Exception:
            continue
        if t.count("\x00") > len(t) * 0.1:
            continue
        return t
    return raw.decode("utf-8", "replace")


if not os.path.exists(LOG):
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("no server log at %s\n" % LOG)
    raise SystemExit

with open(LOG, "rb") as f:
    txt = dec(f.read()).replace("\x00", "")

lines = txt.splitlines()
KEYS = ["LowVRAM", "lowvram", "Attention", "attention", "Sage", "sage",
        "ERROR", "error", "WARNING", "warning", "OOM", "out of memory",
        "Traceback", "Exception", "nan", "NaN", "inf", "black", "zero",
        "H3Memory", "ChunkFeedForward", "head_chunks"]

hits = []
for i, ln in enumerate(lines):
    if any(k in ln for k in KEYS):
        hits.append((i, ln.rstrip()))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("server log total lines=%d\n" % len(lines))
    f.write("=== 命中告警/关键字的行（最多 120 条）===\n")
    for i, ln in hits[-120:]:
        f.write("%6d | %s\n" % (i, ln[:400]))
    f.write("\n=== 最后 50 行（原样）===\n")
    for ln in lines[-50:]:
        f.write("%s\n" % ln[:400])
