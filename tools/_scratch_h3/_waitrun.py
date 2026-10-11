# -*- coding: utf-8 -*-
"""轮询渲染日志，直到出现「已完成」/「未完成」，或超时。"""
import io, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_waitrun_out.txt")
LOG = (sys.argv[1] if len(sys.argv) > 1 else
       r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard\_run_full.log")

DONE_MARK = "\u5df2\u5b8c\u6210"      # 已完成
FAIL_MARK = "\u672a\u5b8c\u6210"      # 未完成


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


t0 = time.time()
status = "timeout"
last = ""

while time.time() - t0 < 3000:          # 最多 50 分钟
    if os.path.exists(LOG):
        with open(LOG, "rb") as f:
            raw = f.read()
        last = dec(raw).replace("\x00", "")
        if FAIL_MARK in last:
            status = "FAILED"
            break
        if DONE_MARK in last:
            status = "OK"
            break
    time.sleep(10)

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("status=%s  elapsed=%.0fs\n" % (status, time.time() - t0))
    f.write(last[-5000:])
    f.write("\n")
