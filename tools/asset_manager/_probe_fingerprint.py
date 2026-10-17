# -*- coding: utf-8 -*-
"""自动化指纹 A/B 实测：同一个 Chrome 实例，分别用「纯 CDP」与「chromedriver 附加」读取指纹。

目的：验证一个关键前提——把客户端从 chromedriver 换成 Playwright/CDP 客户端，
      会不会改变微信页面能观察到的自动化特征？

用法：
    venv/Scripts/python.exe tools/asset_manager/_probe_fingerprint.py 9600
"""
import importlib
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

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9600
BASE = f"http://127.0.0.1:{PORT}"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

FP_JS = """return (function(){
  var out = {
    webdriver: navigator.webdriver,
    webdriverInNav: ('webdriver' in navigator),
    plugins: navigator.plugins.length,
    languages: (navigator.languages || []).join(','),
    ua: navigator.userAgent,
    chromeObj: !!window.chrome,
    chromeRuntime: !!(window.chrome && window.chrome.runtime),
    permissionNotification: null,
    cdcVars: Object.keys(window).filter(function(k){ return /^\\$?cdc_/.test(k); }),
    hasCallPhantom: ('callPhantom' in window),
    hasWebdriverProps: Object.keys(document.documentElement).filter(function(k){ return /webdriver|selenium/i.test(k); })
  };
  return out;
})()"""


def cdp_eval(port, expr):
    pages = [t for t in json.loads(OPENER.open(f"http://127.0.0.1:{port}/json/list", timeout=8).read().decode())
             if t.get("type") == "page"]
    ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=10, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
        ws.settimeout(10)
        r = json.loads(ws.recv())
        return r.get("result", {}).get("result", {}).get("value")
    finally:
        ws.close()


def main():
    sb = importlib.import_module("backend.publishers.selenium_base")

    print(f"=== A. 纯 CDP 连接（port {PORT}）===")
    a = cdp_eval(PORT, FP_JS)
    print(json.dumps(a, ensure_ascii=False, indent=1))

    print(f"\n=== B. chromedriver 附加到同一个浏览器 ===")
    os.environ["_AM_TEST_PORT"] = str(PORT)
    driver = None
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        o = Options()
        o.add_experimental_option("debuggerAddress", f"127.0.0.1:{PORT}")
        driver = webdriver.Chrome(options=o)
        b = driver.execute_script(FP_JS)
        print(json.dumps(b, ensure_ascii=False, indent=1))

        print("\n=== C. 差异对比 ===")
        diffs = {k: (a.get(k), b.get(k)) for k in a if a.get(k) != b.get(k)}
        if diffs:
            for k, (x, y) in diffs.items():
                print(f"  {k}: 纯CDP={x!r}  chromedriver={y!r}")
        else:
            print("  完全一致 —— 客户端类型不改变页面可见的自动化特征")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
