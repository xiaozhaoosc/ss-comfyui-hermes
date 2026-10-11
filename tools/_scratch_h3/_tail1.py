# -*- coding: utf-8 -*-
"""tail 一个文件的尾部（自动解码编码），写入 _tail1_out.txt。"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_tail1_out.txt")
SRC = sys.argv[1] if len(sys.argv) > 1 else ""


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


txt = ""
if SRC and os.path.exists(SRC):
    with open(SRC, "rb") as f:
        txt = dec(f.read()).replace("\x00", "")
else:
    txt = "(missing: %s)" % SRC

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(txt[-5000:])
    f.write("\n")
