# -*- coding: utf-8 -*-
"""列出 2026-09-22_wb 树，写入日志便于 Read。"""
import io, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb"
OUT = os.path.join(HERE, "_lsout.txt")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("now=%s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    f.write("ROOT exists=%s\n" % os.path.isdir(ROOT))
    if os.path.isdir(ROOT):
        for dirpath, dirnames, filenames in os.walk(ROOT):
            rel = os.path.relpath(dirpath, ROOT)
            f.write("\n[%s]\n" % rel)
            for n in sorted(filenames):
                p = os.path.join(dirpath, n)
                f.write("   %-52s %10d\n" % (n, os.path.getsize(p)))
