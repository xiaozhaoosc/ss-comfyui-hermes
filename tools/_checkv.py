# -*- coding: utf-8 -*-
"""检查指定视频是否真有画面（逐帧 mean/std），并报告日志尾部。"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np          # noqa: F401
import cv2

GD = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard"
L = []


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


# 1) 列出 h3_guard 下所有 mp4（按时间倒序）
L.append("=== h3_guard 下的 mp4 ===")
if os.path.isdir(GD):
    fs = [n for n in os.listdir(GD) if n.lower().endswith(".mp4")]
    fs.sort(key=lambda n: os.path.getmtime(os.path.join(GD, n)), reverse=True)
    for n in fs:
        p = os.path.join(GD, n)
        L.append("  %-44s %9d" % (n, os.path.getsize(p)))

# 2) 逐个检查（只看最近 3 个）
L.append("")
L.append("=== 画面检查 ===")
for n in fs[:3]:
    p = os.path.join(GD, n)
    cap = cv2.VideoCapture(p)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    means = []
    idx = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        means.append(float(fr.mean()))
        if idx == 0:
            cv2.imwrite(os.path.join(HERE, "_chk_%s_f000.png" % n[:24]), fr)
        idx += 1
    cap.release()
    if means:
        L.append("  %s" % n)
        L.append("     frames=%d  mean 首=%.1f 中=%.1f 尾=%.1f  max=%.1f  nonblack=%d/%d" % (
            idx, means[0], means[len(means) // 2], means[-1], max(means),
            sum(1 for m in means if m > 1.0), len(means)))
    else:
        L.append("  %s  frames=%d  读不到帧" % (n, total))

# 3) 测试日志尾部
L.append("")
L.append("=== _run_test.log 尾部 ===")
lp = os.path.join(GD, "_run_test.log")
if os.path.exists(lp):
    with open(lp, "rb") as f:
        L.append(dec(f.read()).replace("\x00", "")[-2500:])
else:
    L.append("(无)")

with io.open(os.path.join(HERE, "_checkv_out.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
