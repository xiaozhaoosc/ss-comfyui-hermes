#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性探针：用 9222 已登录抖音页面打开目标 note，看它到底是图文还是视频、
媒体直链长什么样（为 media_dl 增加抖音支持取证）。

用法：
  <venv python> tools/_probe_douyin_note.py [note_url]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

NOTE = sys.argv[1] if len(sys.argv) > 1 else "https://www.douyin.com/note/7686812393779123898"
PORT = 9222

import ig_download as ig  # noqa: E402


def main() -> int:
    if ig.websocket is None:
        print("缺少 websocket-client")
        return 2

    with ig.local_cdp_no_proxy():
        base, ver = ig.resolve_cdp_base(PORT)
        tabs = ig._http_json(base, "/json/list")
    pages = [t for t in tabs if t.get("type") == "page"]
    douyin_tabs = []
    for t in pages:
        try:
            from urllib.parse import urlparse
            host = urlparse(t.get("url", "")).netloc
        except Exception:
            continue
        if host.endswith("douyin.com"):
            douyin_tabs.append(t)
    if not douyin_tabs:
        print("9222 没有 douyin.com 页面")
        return 3
    tab = douyin_tabs[0]
    print(f"[tab] {tab.get('title')} -> {tab.get('url')}")
    ws_url = tab["webSocketDebuggerUrl"]

    with ig.local_cdp_no_proxy():
        ws = ig.websocket.create_connection(ws_url, timeout=25, suppress_origin=True)
        try:
            net_events = []

            def send(mid, method, params=None):
                ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))

            send(1, "Network.enable")
            send(2, "Page.enable")
            send(3, "Page.navigate", {"url": NOTE})

            # 收集 12 秒内的网络响应
            deadline = time.time() + 12
            ws.settimeout(2)
            while time.time() < deadline:
                try:
                    raw = ws.recv()
                except Exception:
                    continue
                try:
                    d = json.loads(raw)
                except Exception:
                    continue
                m = d.get("method")
                if m == "Network.responseReceived":
                    p = d.get("params", {})
                    resp = p.get("response", {})
                    net_events.append({
                        "type": p.get("type"),
                        "mime": resp.get("mimeType"),
                        "url": resp.get("url", ""),
                    })

            # 页面 DOM 抓取
            expr = r"""JSON.stringify({
                title: document.title,
                imgs: Array.from(document.querySelectorAll('img')).map(i=>i.src).filter(Boolean),
                vids: Array.from(document.querySelectorAll('video')).map(v=>v.src||v.currentSrc||'').filter(Boolean),
                routerKeys: (window._ROUTER_DATA ? Object.keys(window._ROUTER_DATA) : []),
                hasRender: !!document.getElementById('RENDER_DATA')
            })"""
            ig._cdp_roundtrip(ws, 90, "Runtime.enable", {})
            res = ig._cdp_roundtrip(ws, 91, "Runtime.evaluate",
                                    {"expression": expr, "returnByValue": True, "awaitPromise": True})
            dom = res.get("result", {}).get("result", {}).get("value", "{}")
            try:
                dom = json.loads(dom)
            except Exception:
                dom = {"raw": dom}
        finally:
            try:
                ws.close()
            except Exception:
                pass

    media = [e for e in net_events if e["type"] in ("Image", "Media")
             or (e["mime"] or "").startswith(("image/", "video/"))]
    print(f"\n[网络] 共 {len(net_events)} 条响应，其中媒体类 {len(media)} 条")
    seen = set()
    for e in media:
        u = e["url"]
        if u in seen:
            continue
        seen.add(u)
        print(f"    {e['type']:6s} {e['mime']:12s} {u[:150]}")

    print(f"\n[DOM] title={dom.get('title')}")
    print(f"[DOM] routerKeys={dom.get('routerKeys')}  RENDER_DATA={dom.get('hasRender')}")
    imgs = [u for u in dom.get("imgs", []) if "douyinpic" in u or "byteimg" in u or "tos-cn" in u]
    print(f"[DOM] img 总数={len(dom.get('imgs', []))}，CDN 相关={len(imgs)}")
    for u in imgs[:20]:
        print(f"    IMG {u[:150]}")
    for v in dom.get("vids", [])[:10]:
        print(f"    VID {v[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
