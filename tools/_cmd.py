# -*- coding: utf-8 -*-
"""
通用命令执行器：任意命令的输出都以 UTF-8 落盘到 tools/_cmd_out.txt。
用途：绕过 PowerShell 吞 stdout、以及 GBK/UTF-16 编码混乱的问题。
用法:  python _cmd.py "<command line>"
"""
import io, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CWD = os.path.dirname(HERE)          # D:\ai_projects\ComfyUI
OUT = os.path.join(HERE, "_cmd_out.txt")

cmd = sys.argv[1] if len(sys.argv) > 1 else ""


def dec(b):
    if not b:
        return ""
    for enc in ("utf-8", "gbk", "utf-16", "latin-1"):
        try:
            t = b.decode(enc)
        except Exception:
            continue
        if t.count("\x00") > len(t) * 0.2:
            continue
        return t
    return b.decode("utf-8", "replace")


if not cmd:
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("no command given\n")
    sys.exit(0)

p = subprocess.run(cmd, shell=True, capture_output=True, cwd=CWD)

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("CMD: %s\n" % cmd)
    f.write("CWD: %s\n" % CWD)
    f.write("RC : %s\n" % p.returncode)
    f.write("==== STDOUT ====\n")
    f.write(dec(p.stdout))
    f.write("\n==== STDERR ====\n")
    f.write(dec(p.stderr))
    f.write("\n")
