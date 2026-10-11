# -*- coding: utf-8 -*-
"""用 subprocess 跑 calib3，并把它的 stdout/stderr 一并写入日志（绕过 PowerShell 吞输出）。"""
import subprocess, io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_calib_log.txt")
PY = r"C:\Users\kenzhao\anaconda3\python.exe"
SCRIPT = os.path.join(HERE, "_calib3.py")


def log(msg):
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(str(msg) + "\n")
        f.flush()


with io.open(LOG, "w", encoding="utf-8") as f:
    f.write("=== run_calib start ===\n")

p = subprocess.run([PY, SCRIPT], capture_output=True, cwd=HERE)
log("returncode=%s" % p.returncode)
log("--- stdout ---")
log(p.stdout.decode("utf-8", "replace")[-8000:])
log("--- stderr ---")
log(p.stderr.decode("utf-8", "replace")[-8000:])
log("=== run_calib done ===")
