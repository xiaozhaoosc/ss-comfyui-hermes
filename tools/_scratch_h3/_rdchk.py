# -*- coding: utf-8 -*-
import io, os

HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "_chk.txt")
dst = os.path.join(HERE, "_chk_utf8.txt")
raw = open(src, "rb").read()
for enc in ("utf-8", "gbk", "utf-16", "utf-16-le"):
    try:
        t = raw.decode(enc)
        if t.count("\x00") > len(t) * 0.2:
            continue
        break
    except Exception:
        continue
else:
    t = raw.decode("utf-8", "replace")
with io.open(dst, "w", encoding="utf-8") as f:
    f.write("len=%d\n%s\n" % (len(t), t))
