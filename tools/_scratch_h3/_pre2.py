# -*- coding: utf-8 -*-
"""精确探活 ComfyUI：绕开系统代理 + 直接 socket 探测 + netstat 看谁在听 8188。"""
import io, os, socket, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_pre_out.txt")
L = []

# 0) 代理环境变量（502 的常见元凶）
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
          "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
    v = os.environ.get(k)
    if v:
        L.append("env %-12s = %s" % (k, v))
if not any(x.startswith("env ") for x in L):
    L.append("env: 无代理变量")

# 1) 裸 socket 探测
try:
    s = socket.create_connection(("127.0.0.1", 8188), timeout=4)
    s.close()
    L.append("socket 127.0.0.1:8188  OK  端口可连")
except Exception as e:
    L.append("socket 127.0.0.1:8188  FAIL %r" % (e,))

# 2) 绕代理的 HTTP 请求
def get(path, timeout=8):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    r = op.open("http://127.0.0.1:8188" + path, timeout=timeout)
    return r.status, r.read()[:400]

for path in ("/queue", "/object_info/KSampler"):
    try:
        st, body = get(path)
        L.append("GET %-22s -> %s  %s" % (path, st, body[:200]))
    except Exception as e:
        L.append("GET %-22s -> FAIL %r" % (path, e))

# 3) netstat 看 8188 监听者
try:
    p = subprocess.run("netstat -ano | findstr :8188", shell=True, capture_output=True)
    txt = p.stdout.decode("gbk", "replace")
    L.append("---- netstat ----")
    L.append(txt.strip() or "(无输出)")
except Exception as e:
    L.append("netstat FAIL %r" % (e,))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
