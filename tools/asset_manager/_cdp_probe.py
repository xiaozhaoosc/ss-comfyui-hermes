# -*- coding: utf-8 -*-
"""调试 Chrome 的 CDP 直连探针（绕开 chromedriver，用于排查附加挂起）。

提供：
- close_unresponsive_tabs(port)：关闭对 CDP 无响应的僵尸标签页（被其它自动化脚本 import 调用）
- 命令行直接跑 = 人工排查用

用法：
    venv/Scripts/python.exe tools/asset_manager/_cdp_probe.py
    python -c "import sys;sys.path.insert(0,'tools/asset_manager');import _cdp_probe as c;c.close_unresponsive_tabs(9527)"
"""
import json
import os
import sys
import time
import urllib.request

import websocket

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k in list(os.environ):
    if k.lower().endswith("_proxy"):
        os.environ.pop(k)


def _base(port):
    return f"http://127.0.0.1:{port}"


def close_unresponsive_tabs(port=9527, keep_first=True, timeout=4, verbose=False):
    """关闭对 CDP Runtime.evaluate 无响应的标签页。

    僵尸页会让 webdriver.Chrome() 建会话无限挂起（>120s 无报错），
    这里只关"无响应"的页——能响应的页一律保留，避免误伤用户正在编辑的页面。
    返回 (保留页数, 关闭页数)。
    """
    base = _base(port)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # 先开一个空白页垫底：关掉最后一个标签页会把整个 Chrome 带走，
    # 之后 schtasks 拉起又可能被沙箱拦截，整个通道就废了。
    try:
        opener.open(base + "/json/new?about:blank", timeout=5).read()
    except Exception:
        pass
    try:
        pages = [t for t in json.loads(opener.open(base + "/json/list", timeout=8).read().decode("utf-8"))
                 if t.get("type") == "page"]
    except Exception as e:
        if verbose:
            print(f"  [cdp] 无法连接 {base}: {type(e).__name__}")
        return 0, 0

    kept, closed = [], 0
    for t in pages:
        if "about:blank" in (t.get("url") or ""):
            kept.append(t["id"])
            continue
        alive = False
        try:
            ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=timeout, suppress_origin=True)
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                "params": {"expression": "1+1", "returnByValue": True}}))
            ws.settimeout(timeout)
            alive = json.loads(ws.recv()).get("result", {}).get("result", {}).get("value") == 2
            ws.close()
        except Exception:
            alive = False
        if alive and (keep_first is False or not kept):
            kept.append(t["id"])
            if verbose:
                print(f"  [cdp] 保留 {t['id'][:8]} {(t.get('url') or '')[:60]}")
            continue
        if not alive:
            try:
                opener.open(f"{base}/json/close/{t['id']}", timeout=5).read()
                closed += 1
                if verbose:
                    print(f"  [cdp] 关闭僵尸页 {t['id'][:8]} {(t.get('url') or '')[:60]}")
            except Exception:
                pass
    return len(kept), closed


PORT = 9527
BASE = f"http://127.0.0.1:{PORT}"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(path):
    return json.loads(opener.open(BASE + path, timeout=10).read().decode("utf-8"))


def cdp(ws_url, method, params=None, timeout=12):
    # Chrome 155 默认拒绝携带 Origin 头的 WS 连接（403），必须抑制 Origin
    ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            ws.settimeout(deadline - time.time())
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                return msg
        return {"error": "timeout"}
    finally:
        ws.close()


def main():
    for port in (9527, 9528):
        print(f"\n=== 端口 {port} 僵尸页清理 ===")
        kept, closed = close_unresponsive_tabs(port, keep_first=True, verbose=True)
        print(f"  保留 {kept} 页，关闭 {closed} 页")

    print("\n=== 登录态探测（9527） ===")
    ver = http_json("/json/version")
    print("Browser:", ver.get("Browser"))

    # 1. 已有页面是否有未处理的原生对话框（会让 chromedriver 建会话时挂死）
    for t in http_json("/json/list"):
        if t.get("type") != "page":
            continue
        ws = t.get("webSocketDebuggerUrl")
        print(f"\n[已有页] {t.get('title')[:30]} | {t.get('url')[:80]}")
        try:
            ws2 = websocket.create_connection(ws, timeout=6, suppress_origin=True)
            ws2.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                 "params": {"expression": "1+1", "returnByValue": True}}))
            ws2.settimeout(6)
            r = json.loads(ws2.recv())
            ws2.close()
            print("  Runtime.evaluate 正常:", r.get("result", {}).get("result", {}).get("value"))
        except Exception as e:
            print("  !! 该页无响应（疑似被原生对话框阻塞）:", type(e).__name__, str(e)[:120])

    # 2. 开一个新标签页验证登录态，不受旧页对话框影响
    print("\n[新标签页] 打开公众号首页检查登录态")
    req = urllib.request.Request(BASE + "/json/new?https://mp.weixin.qq.com/", method="PUT")
    try:
        newt = json.loads(opener.open(req, timeout=10).read().decode("utf-8"))
    except Exception:
        req = urllib.request.Request(BASE + "/json/new?https://mp.weixin.qq.com/")
        newt = json.loads(opener.open(req, timeout=10).read().decode("utf-8"))
    print("  new target:", newt.get("url", "")[:80])
    time.sleep(4)

    ws = newt.get("webSocketDebuggerUrl")
    for attempt in range(6):
        r = cdp(ws, "Runtime.evaluate", {"expression": """
            (function(){
              var nick = document.querySelector('.weui-desktop-account__nickname');
              var m = location.href.match(/token=(\\d+)/);
              return JSON.stringify({
                url: location.href.slice(0,120),
                title: document.title,
                nickname: nick ? nick.innerText.trim() : null,
                token: m ? m[1] : null,
                needLogin: document.body.innerText.indexOf('扫码登录') >= 0 || location.href.indexOf('/login') >= 0
              });
            })()
        """, "returnByValue": True})
        val = r.get("result", {}).get("result", {}).get("value")
        if val:
            print("  ->", val)
            break
        time.sleep(2)
    else:
        print("  未取得结果：", r)

    try:
        opener.open(f"{BASE}/json/close/{newt.get('id')}", timeout=5).read()
        print("  (已关闭临时标签页)")
    except Exception as e:
        print("  关闭临时标签页失败（可忽略）:", type(e).__name__)


if __name__ == "__main__":
    main()
