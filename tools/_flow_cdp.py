#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轻量 CDP 客户端（原生 WebSocket），用于接管 Flow 页面。

背景（2026-10-11 实测）：
  Playwright 1.61 的 connect_over_cdp 对本机 Chrome 154 会在 `<ws connected>` 之后卡死
  （180s 超时）；而同一端点用原生 CDP WebSocket 完全正常（Browser.getVersion 即时返回）。
  故本模块绕过 Playwright，直连**页面级** WebSocket（取自 /json/list 的 webSocketDebuggerUrl）。

用法：
  from _flow_cdp import resolve_base, list_pages, Page
  base = resolve_base()                     # 自动探测 127.0.0.1 / localhost / [::1]
  pg   = attach_flow_page(base)             # 取（或新建）flow.google.com 页面
  pg.eval("document.title")
  pg.navigate("https://flow.google.com/project/xxx")
  pg.screenshot(r"out.png")
  pg.close()
"""

import base64
import json
import time

import requests
import websocket


def resolve_base(port=9222):
    """返回第一个可用的 CDP HTTP 端点（/json/version 返回 200）。"""
    for u in (f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"http://[::1]:{port}"):
        try:
            if requests.get(f"{u}/json/version", timeout=3).status_code == 200:
                return u
        except Exception:
            continue
    return None


def list_pages(base):
    """列出所有 page 类型目标。"""
    try:
        return [p for p in requests.get(base + "/json/list", timeout=6).json()
                if p.get("type") == "page"]
    except Exception:
        return []


class Page:
    """页面级 CDP 会话。"""

    def __init__(self, ws_url, timeout=20):
        self.ws_url = ws_url
        self.ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
        self._id = 0

    def call(self, method, params=None, timeout=30):
        """发一条 CDP 命令并等待同 id 响应（跳过事件消息）。"""
        self._id += 1
        mid = self._id
        self.ws.settimeout(timeout)
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout + 2
        while time.time() < deadline:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method} -> {msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(f"{method} 无响应")

    def eval(self, expr, await_promise=False, timeout=30):
        """执行 JS 表达式并返回其值（returnByValue）。"""
        r = self.call("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
            "userGesture": True,
        }, timeout=timeout)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            raise RuntimeError(f"JS exception: {d.get('text')} {d.get('exception', {}).get('description', '')[:300]}")
        return r.get("result", {}).get("value")

    def navigate(self, url, settle_ms=6000):
        self.call("Page.navigate", {"url": url}, timeout=40)
        time.sleep(settle_ms / 1000.0)

    def screenshot(self, path, full_page=False):
        r = self.call("Page.captureScreenshot",
                      {"format": "png", "captureBeyondViewport": bool(full_page)}, timeout=40)
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))
        return path

    def insert_text(self, text):
        """向当前焦点元素插入文本（对 ProseMirror 有效，远快于逐字敲键）。"""
        self.call("Input.insertText", {"text": text}, timeout=60)

    def click_at(self, x, y):
        """在视口坐标派发真实鼠标事件（Angular Material 需要，JS .click() 不触发其事件流）。"""
        for type_, btn in (("mouseMoved", "none"), ("mousePressed", "left"), ("mouseReleased", "left")):
            self.call("Input.dispatchMouseEvent", {
                "type": type_, "x": int(x), "y": int(y),
                "button": btn, "clickCount": 1 if btn != "none" else 0,
            }, timeout=15)
            time.sleep(0.05)

    def click_selector(self, js_find, scroll=True):
        """用 JS 取元素中心坐标，再以真实鼠标事件点击。

        js_find 应返回目标元素的 selector 或表达式结果（单个元素）。
        """
        rect = self.eval(f"""
(() => {{
  const el = ({js_find});
  if (!el) return null;
  if ({'true' if scroll else 'false'}) el.scrollIntoView({{block:'center'}});
  const r = el.getBoundingClientRect();
  return JSON.stringify({{x: r.x + r.width/2, y: r.y + r.height/2}});
}})()
""")
        if not rect:
            return False
        import json as _json
        pos = _json.loads(rect)
        self.click_at(pos["x"], pos["y"])
        return True

    def key(self, key, code=None, key_code=None, modifiers=0):
        """派发一次按键（rawKeyDown + keyUp）。"""
        params = {"key": key, "modifiers": modifiers}
        if code:
            params["code"] = code
        if key_code:
            params["windowsVirtualKeyCode"] = key_code
            params["nativeVirtualKeyCode"] = key_code
        self.call("Input.dispatchKeyEvent", dict(params, type="rawKeyDown"), timeout=15)
        self.call("Input.dispatchKeyEvent", dict(params, type="keyUp"), timeout=15)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def attach_flow_page(base, navigate_url=None, timeout=20):
    """取已打开的 flow.google.com 页面；没有则新建标签页。

    navigate_url 非空时，若当前页面不在目标 project 路径下则导航过去。
    """
    pages = list_pages(base)
    flow = [p for p in pages if "flow.google.com" in (p.get("url") or "")]
    if flow:
        # 优先选已在 project 路径下的页面
        target = None
        for p in flow:
            if "/project/" in (p.get("url") or ""):
                target = p
                break
        target = target or flow[0]
        pg = Page(target["webSocketDebuggerUrl"], timeout=timeout)
        cur = pg.eval("location.href")
        if navigate_url and "/project/" not in (cur or ""):
            pg.navigate(navigate_url)
            cur = pg.eval("location.href")
        pg.__dict__["url"] = cur
        return pg
    # 没有 Flow 页：用 /json/new 建一个
    try:
        p = requests.put(base + f"/json/new?{navigate_url or 'https://flow.google.com/'}", timeout=10).json()
    except Exception:
        p = requests.get(base + f"/json/new?{navigate_url or 'https://flow.google.com/'}", timeout=10).json()
    pg = Page(p["webSocketDebuggerUrl"], timeout=timeout)
    time.sleep(6)
    pg.__dict__["url"] = pg.eval("location.href")
    return pg