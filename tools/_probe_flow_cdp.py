import json, time, urllib.request
import websocket

BASE = "http://127.0.0.1:9222"
pages = json.loads(urllib.request.urlopen(BASE + "/json", timeout=5).read().decode())
for p in pages:
    u = p.get("url", "")
    if "flow.google.com/project" in u:
        print("TARGET:", p.get("title"), u)
        ws = websocket.create_connection(p["webSocketDebuggerUrl"], timeout=12, suppress_origin=True)
        t0 = time.time()
        try:
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                "params": {"expression": "document.title + '|' + document.readyState", "returnByValue": True}}))
            while True:
                d = json.loads(ws.recv())
                if d.get("id") == 1:
                    print("EVAL OK %.2fs ->" % (time.time() - t0), d.get("result", {}).get("result", {}).get("value"))
                    break
        except Exception as e:
            print("EVAL FAIL %.2fs ->" % (time.time() - t0), type(e).__name__, e)
        try:
            ws.close()
        except Exception:
            pass
