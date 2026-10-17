"""强制重载 Flow 项目页（禁缓存），并等待生成面板真正可用。

用法: python tools/_reload_flow.py [port] [wait_sec]
判定标准：Start generation 按钮存在 + 其所在面板已绑定（点击前的 innerText 含 submit-controls 文案）。
"""
import json
import sys
import time
import urllib.request

import websocket

PORT = sys.argv[1] if len(sys.argv) > 1 else "9222"
WAIT = int(sys.argv[2]) if len(sys.argv) > 2 else 60

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
targets = json.loads(op.open("http://127.0.0.1:%s/json" % PORT, timeout=10).read())
pages = [t for t in targets if t.get("type") == "page" and "flow.google.com" in (t.get("url") or "")]
if not pages:
    print("NO_FLOW_PAGE")
    sys.exit(1)
url = pages[0]["url"]
ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=40, suppress_origin=True)
seq = [0]
errors = []


def send(method, params=None):
    seq[0] += 1
    ws.send(json.dumps({"id": seq[0], "method": method, "params": params or {}}))
    return seq[0]


def wait_id(want, budget=30):
    t0 = time.time()
    while time.time() - t0 < budget:
        msg = json.loads(ws.recv())
        m = msg.get("method")
        if m == "Log.entryAdded" and msg["params"]["entry"].get("level") == "error":
            errors.append(msg["params"]["entry"].get("text", "")[:120])
        if msg.get("id") == want:
            return msg
    return None


send("Runtime.enable")
send("Log.enable")
send("Network.enable")
wait_id(seq[0], 5)
send("Network.setCacheDisabled", {"cacheDisabled": True})
wait_id(seq[0], 5)
print("RELOAD:", url)
send("Page.reload", {"ignoreCache": True})
wait_id(seq[0], 10)
ws.close()

time.sleep(8)
ws = websocket.create_connection(
    json.loads(op.open("http://127.0.0.1:%s/json" % PORT, timeout=10).read())[0]["webSocketDebuggerUrl"]
    if False else
    [t for t in json.loads(op.open("http://127.0.0.1:%s/json" % PORT, timeout=10).read())
     if t.get("type") == "page" and "flow.google.com" in (t.get("url") or "")][0]["webSocketDebuggerUrl"],
    timeout=40, suppress_origin=True)
seq[0] = 0


def ev(expr):
    i = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    r = wait_id(i, 25)
    return r["result"]["result"].get("value") if r and "result" in r else None


t0 = time.time()
while time.time() - t0 < WAIT:
    st = ev(
        "JSON.stringify({ready:document.readyState,"
        "gen:(function(){var b=document.querySelector(\"button[aria-label='Start generation']\");"
        "return b?{dis:b.disabled}:null;})(),"
        "loading:(document.body.innerText||'').includes('L o a d i n g'),"
        "submit:!!document.querySelector('.submit-controls')})"
    )
    print("%02ds %s" % (int(time.time() - t0), st))
    try:
        s = json.loads(st or "{}")
    except Exception:
        s = {}
    if s.get("gen") is not None and not s.get("loading") and s.get("submit"):
        print("PANEL_READY")
        break
    time.sleep(5)
print("console errors:", len(errors))
for e in errors[:6]:
    print("  ", e)
