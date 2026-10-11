# -*- coding: utf-8 -*-
"""统一的运行状态查看：渲染日志尾 + 产物目录 + ComfyUI 队列。"""
import io, os, time, json, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_status_out.txt")
RUNLOG = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard\_run_full.log"
GDIR = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard"


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

# 1) 渲染日志尾
L.append("")
L.append("======== _run_full.log 尾部 ========")
if os.path.exists(RUNLOG):
    with open(RUNLOG, "rb") as f:
        f.seek(0, 2)
        n = f.tell()
        f.seek(max(0, n - 5000))
        raw = f.read()
    t = dec(raw).replace("\x00", "")
    L.append("(文件大小 %d 字节)" % n)
    L.append(t)
else:
    L.append("(日志还没生成)")

# 2) 产物目录
L.append("")
L.append("======== h3_guard 产物 ========")
if os.path.isdir(GDIR):
    for n in sorted(os.listdir(GDIR)):
        p = os.path.join(GDIR, n)
        L.append("   %-46s %10d  %s" % (
            n, os.path.getsize(p),
            time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p)))))
else:
    L.append("(目录不存在)")

# 3) 队列
L.append("")
L.append("======== ComfyUI 队列 ========")
try:
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    r = op.open("http://127.0.0.1:8188/queue", timeout=8)
    q = json.loads(r.read())
    L.append("running=%d  pending=%d" % (len(q.get("queue_running", [])),
                                         len(q.get("queue_pending", []))))
except Exception as e:
    L.append("queue FAIL %r" % (e,))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
