import json, sys, urllib.request, websocket
PORT = sys.argv[1] if len(sys.argv) > 1 else "9222"
EXPR = sys.argv[2] if len(sys.argv) > 2 else "document.title"

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
targets = json.loads(op.open(f"http://127.0.0.1:{PORT}/json", timeout=10).read())
pages = [t for t in targets if t.get("type") == "page" and "flow.google.com" in (t.get("url") or "")]
if not pages:
    print("NO_FLOW_PAGE")
    sys.exit(1)
p = pages[0]
ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=25, suppress_origin=True)
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                    "params": {"expression": EXPR, "returnByValue": True, "awaitPromise": True}}))
while True:
    msg = json.loads(ws.recv())
    if msg.get("id") == 1:
        r = msg.get("result", {}).get("result", {})
        print(json.dumps(r.get("value") if "value" in r else r, ensure_ascii=False)[:4000])
        break
ws.close()
