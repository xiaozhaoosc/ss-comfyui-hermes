# -*- coding: utf-8 -*-
"""把文件状态/内容写进固定日志文件（因为 PowerShell 的 stdout 不可靠）。"""
import io, os, glob, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_stat_log.txt")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("now=%s\n" % time.strftime("%H:%M:%S"))
    for n in sorted(glob.glob(os.path.join(HERE, "_*"))):
        try:
            st = os.stat(n)
            f.write("%-46s %10d bytes  %s\n" % (
                os.path.basename(n), st.st_size,
                time.strftime("%H:%M:%S", time.localtime(st.st_mtime))))
        except Exception as ex:
            f.write("%-46s ERR %r\n" % (os.path.basename(n), ex))
    f.write("\n--- tail of _wrap_out.txt ---\n")
    p = os.path.join(HERE, "_wrap_out.txt")
    if os.path.exists(p):
        with io.open(p, "r", encoding="utf-8", errors="replace") as g:
            t = g.read()
        f.write(t[-4000:] if t else "(empty)\n")
    f.write("\n--- tail of _wrap_out.txt.err ---\n")
    p = os.path.join(HERE, "_wrap_out.txt.err")
    if os.path.exists(p):
        with io.open(p, "r", encoding="utf-8", errors="replace") as g:
            t = g.read()
        f.write(t[-4000:] if t else "(empty)\n")
