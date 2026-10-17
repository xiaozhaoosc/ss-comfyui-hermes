"""一次性诊断：点击 Start generation 后观察网络/控制台/画布变化。

用法: python tools/_diag_flow_click.py [port] [seconds]
不改动任何业务流程，仅观察。
"""
import json
import sys
import time
import urllib.request

import websocket

PORT = sys.argv[1] if len(sys.argv) > 1 else "9222"
WATCH = int(sys.argv[2]) if len(sys.argv) > 2 else 30

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
targets = json.loads(op.open("http://127.0.0.1:%s/json" % PORT, timeout=10).read())
pages = [t for t in targets if t.get("type") == "page" and "flow.google.com/project" in (t.get("url") or "")]
if not pages:
    print("NO_PROJECT_PAGE")
    sys.exit(1)

ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=40, suppress_origin=True)
seq = [0]


def send(method, params=None):
    seq[0] += 1
    ws.send(json.dumps({"id": seq[0], "method": method, "params": params or {}}))
    return seq[0]


def eval_js(expr):
    i = send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    t0 = time.time()
    while time.time() - t0 < 25:
        msg = json.loads(ws.recv())
        if msg.get("method"):  # 打印运行时事件
            handle_event(msg)
            continue
        if msg.get("id") == i:
            return msg.get("result", {}).get("result", {}).get("value")
    return None


def handle_event(msg):
    m = msg.get("method")
    p = msg.get("params", {})
    if m == "Runtime.consoleAPICalled" and p.get("type") in ("error", "warning"):
        txt = " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args", []))
        print("  [console.%s] %s" % (p.get("type"), txt[:300]))
    elif m == "Log.entryAdded":
        e = p.get("entry", {})
        if e.get("level") in ("error", "warning"):
            print("  [log.%s] %s %s" % (e.get("level"), e.get("text", "")[:200], (e.get("url") or "")[:120]))
    elif m == "Network.loadingFailed":
        print("  [net.fail] %s %s" % (p.get("type"), (p.get("errorText") or "")[:120]))
    elif m == "Network.responseReceived":
        r = p.get("response", {})
        if r.get("status", 0) >= 400:
            print("  [net.%s] %s" % (r.get("status"), (r.get("url") or "")[:160]))


for dom in ("Runtime.enable", "Log.enable", "Network.enable"):
    send(dom)
time.sleep(0.5)

state = eval_js(
    "JSON.stringify({gen:(function(){var b=document.querySelector(\"button[aria-label='Start generation']\");"
    "if(!b)return null;var r=b.getBoundingClientRect();"
    "return{x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),dis:b.disabled};})(),"
    "prompt:(document.querySelector('.ProseMirror')||{}).innerText?document.querySelector('.ProseMirror').innerText.trim().length:0,"
    "imgs:document.querySelectorAll(\"img[src*='flow.google.com/asb/'],img[src*='flow-content'],img[src*='googleusercontent']\").length})"
)
print("BEFORE:", state)
st = json.loads(state or "{}")
gen = st.get("gen")
if not gen:
    print("NO_BUTTON")
    sys.exit(2)
print("prompt chars:", st.get("prompt"), "| disabled:", gen["dis"])

for ev in ("mousePressed", "mouseReleased"):
    send("Input.dispatchMouseEvent", {"type": ev, "x": gen["x"], "y": gen["y"],
                                      "button": "left", "clickCount": 1})
print("CLICKED at", gen["x"], gen["y"])

t0 = time.time()
last_imgs = st.get("imgs")
while time.time() - t0 < WATCH:
    try:
        ws.settimeout(2)
        msg = json.loads(ws.recv())
        if msg.get("method"):
            handle_event(msg)
    except Exception:
        pass
    cur = eval_js(
        "JSON.stringify({imgs:document.querySelectorAll(\"img[src*='flow.google.com/asb/'],img[src*='flow-content'],img[src*='googleusercontent']\").length,"
        "words:(document.body.innerText||'').match(/Generating|Queued|Failed|Something went wrong|Try again|limit reached/gi)})"
    )
    if cur:
        c = json.loads(cur)
        if c.get("imgs") != last_imgs:
            print("  IMG COUNT %s -> %s" % (last_imgs, c.get("imgs")))
            last_imgs = c.get("imgs")
        if c.get("words"):
            print("  WORDS:", c.get("words"))
print("DONE, final imgs:", last_imgs)
ws.close()
