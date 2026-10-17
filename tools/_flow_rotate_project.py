#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动轮换 Google Flow 当日项目（画布过重导致项目页渲染卡死时使用）。

背景（2026-10-17 多次实测）：项目页累积几十张图后，导航到该 project URL 必挂
（Runtime.evaluate 12s 超时），而 flow.google.com 首页 / about:blank 0.01s 正常。
恢复手段是新建项目并改写 output/flow_daily_projects.json 的当日条目。

用法：
  venv/Scripts/python.exe tools/_flow_rotate_project.py [--date 2026-10-17] [--note "..."]

成功时打印 NEW_URL 并将旧值备份到 `<date>_prev<N>`。
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _flow_cdp import Page  # noqa: E402

BASE = "http://127.0.0.1:9222"
PROJECTS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "output", "flow_daily_projects.json")

# Flow 首页的 "New project" 是一个 mdc-fab 悬浮按钮，文案渲染成 `add\nNew project`
# （`add` 是 Material 图标 ligature）。坐标点击会被 FAB 上层元素吃掉，必须走元素级 click()。
JS_CLICK_NEW_PROJECT = """
(() => {
  const els = [...document.querySelectorAll('button, a, [role=button]')];
  const el = els.find(e => /^(add\\s+)?new project$/i.test((e.innerText || '').replace(/\\s+/g, ' ').trim()));
  if (!el) return 'no_element';
  el.click();
  return 'clicked';
})()
"""


def no_proxy_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def rotate(note=""):
    op = no_proxy_opener()
    req = urllib.request.Request(BASE + "/json/new?https://flow.google.com/", method="PUT")
    tab = json.loads(op.open(req, timeout=20).read().decode())
    tab_id = tab["id"]
    print(f"[+] 首页标签页: {tab_id}")
    time.sleep(8)

    pg = Page(tab["webSocketDebuggerUrl"], timeout=25)
    new_url = None
    try:
        print(f"[+] 首页标题: {pg.eval('document.title')}")
        if pg.eval(JS_CLICK_NEW_PROJECT) != "clicked":
            print("[!] 未找到 New project 按钮")
            return None
        for _ in range(25):
            time.sleep(1)
            cur = pg.eval("window.location.href") or ""
            if "/project/" in cur and not cur.rstrip("/").endswith("/project"):
                new_url = cur
                break
        if not new_url:
            print(f"[!] 点击后未跳转，当前 URL: {pg.eval('window.location.href')}")
            return None
        print(f"[+] 新项目: {new_url}")
    finally:
        pg.ws.close()

    # 关掉其它 flow 项目页，避免旧画布继续占用渲染进程
    try:
        tabs = json.loads(op.open(BASE + "/json", timeout=8).read().decode())
        for t in tabs:
            if t.get("id") != tab_id and "/project/" in (t.get("url") or ""):
                try:
                    op.open(BASE + "/json/close/" + t["id"], timeout=8).read()
                    print(f"[+] 关闭旧项目页: {t['id']}")
                except Exception:
                    pass
    except Exception as e:
        print(f"[!] 关闭旧项目页失败(忽略): {e}")

    data = {}
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    today = datetime.date.today().strftime("%Y-%m-%d")
    old = data.get(today)
    if old:
        n = 2
        while f"{today}_prev{n}" in data:
            n += 1
        data[f"{today}_prev{n}"] = old
        print(f"[+] 旧项目已备份为 {today}_prev{n}: {old.get('project_url')}")
    data[today] = {
        "project_url": new_url,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": note or f"Google Flow Daily Project {today}",
    }
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[+] 已写入 {PROJECTS_FILE}")
    return new_url


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    url = rotate(a.note)
    if not url:
        sys.exit(1)
    print("NEW_URL: " + url)
