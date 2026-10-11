# -*- coding: utf-8 -*-
"""subprocess 运行 calib8，把子进程的 stdout/stderr 合并落盘，返回码也落盘。"""
import subprocess, io, os

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\kenzhao\anaconda3\python.exe"
SCRIPT = os.path.join(HERE, "_calib8.py")
OUT = os.path.join(HERE, "_wrap8_out.txt")

p = subprocess.run([PY, "-u", SCRIPT], capture_output=True, cwd=HERE)
with io.open(OUT, "a", encoding="utf-8") as f:
    f.write("\n===== run rc=%s =====\n" % p.returncode)
    f.write("--- stdout ---\n")
    f.write(p.stdout.decode("utf-8", "replace"))
    f.write("\n--- stderr ---\n")
    f.write(p.stderr.decode("utf-8", "replace"))
    f.write("\n")
