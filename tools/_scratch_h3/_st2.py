# -*- coding: utf-8 -*-
"""轻量状态检查：不动 cv2/insightface（避免 native 崩溃），只看服务、文件、日志。"""
import io, os, json, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_st2_out.txt")
GD = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard"


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


L = ["now=%s" % time.strftime("%Y-%m-%d %H:%M:%S")]

# 服务是否还活着
try:
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    r = op.open("http://127.0.0.1:8188/queue", timeout=8)
    q = json.loads(r.read())
    L.append("ComfyUI: ALIVE  running=%d pending=%d" % (
        len(q.get("queue_running", [])), len(q.get("queue_pending", []))))
except Exception as e:
    L.append("ComfyUI: DEAD  %r" % (e,))

# h3_guard 下的 mp4
L.append("")
L.append("=== h3_guard mp4 ===")
if os.path.isdir(GD):
    fs = [n for n in os.listdir(GD) if n.lower().endswith(".mp4")]
    fs.sort(key=lambda n: os.path.getmtime(os.path.join(GD, n)), reverse=True)
    for n in fs:
        p = os.path.join(GD, n)
        L.append("  %-42s %9d  %s" % (
            n, os.path.getsize(p),
            time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))))
else:
    L.append("  (目录不存在)")

# base 运行日志
L.append("")
L.append("=== _run_base.log 尾部 ===")
bp = os.path.join(GD, "_run_base.log")
if os.path.exists(bp):
    with open(bp, "rb") as f:
        t = dec(f.read()).replace("\x00", "")
    L.append(t[-2500:])
else:
    L.append("(无)")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
