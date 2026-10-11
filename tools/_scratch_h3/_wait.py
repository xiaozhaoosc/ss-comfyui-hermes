# -*- coding: utf-8 -*-
"""等待 ComfyUI 就绪（绕开代理），并把启动日志尾部落盘。"""
import io, os, socket, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_wait_out.txt")
STARTLOG = r"D:\ai_projects\ComfyUI\output\_comfyui_start.log"


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def port_open():
    try:
        s = socket.create_connection(("127.0.0.1", 8188), timeout=2)
        s.close()
        return True
    except Exception:
        return False


def http_ok():
    try:
        r = opener().open("http://127.0.0.1:8188/queue", timeout=6)
        return r.status == 200, r.status
    except Exception as e:
        return False, repr(e)


t0 = time.time()
ready = False
last = ""
while time.time() - t0 < 420:          # 最多等 7 分钟
    if port_open():
        ok, info = http_ok()
        if ok:
            ready = True
            break
        last = info
    time.sleep(4)

tail = ""
if os.path.exists(STARTLOG):
    with open(STARTLOG, "rb") as f:
        f.seek(0, 2)
        n = f.tell()
        f.seek(max(0, n - 3000))
        raw = f.read()
    for enc in ("utf-8", "gbk", "utf-16", "utf-16-le"):
        try:
            t = raw.decode(enc)
        except Exception:
            continue
        # 跳过「解码成功但满是 NUL」的假成功（典型是 UTF-16 被当 UTF-8 解）
        if t.count("\x00") > len(t) * 0.1:
            continue
        tail = t
        break
    else:
        tail = raw.decode("utf-8", "replace")
    tail = tail.replace("\x00", "")   # 保险：清掉残余 NUL

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("ready=%s  用时=%.1fs\n" % (ready, time.time() - t0))
    if last:
        f.write("最后一次 HTTP 错误: %s\n" % last)
    f.write("startlog exists=%s size=%s\n" % (
        os.path.exists(STARTLOG),
        os.path.getsize(STARTLOG) if os.path.exists(STARTLOG) else "-"))
    f.write("---- 启动日志尾部 ----\n")
    f.write(tail[-2500:])
    f.write("\n")
