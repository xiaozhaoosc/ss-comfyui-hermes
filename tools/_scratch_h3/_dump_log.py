# -*- coding: utf-8 -*-
"""把 _calib_log.txt 转成纯 ASCII 安全文本，便于 Read 工具读取。"""
import io, os

HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "_calib_log.txt")
dst = os.path.join(HERE, "_calib_log_ascii.txt")

with io.open(src, "r", encoding="utf-8", errors="replace") as f:
    t = f.read()

with io.open(dst, "w", encoding="utf-8", errors="replace") as f:
    f.write(t)
    f.write("\n\n[EOF len=%d]\n" % len(t))
