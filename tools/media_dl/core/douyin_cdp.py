#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抖音「图文笔记」(/note/) 下载引擎（子进程 CLI）。

为什么需要它：
  * gallery-dl 没有 douyin 解析器；
  * yt-dlp 的 Douyin 解析器只认 /video/，/note/ 会被回退到 generic 然后失败；
  * 图文笔记的真实图片直链只在**已登录浏览器渲染后**才出现（CDN 带签名）。

所以它走 CDP：接管 9222 上已登录的抖音页面 → 打开笔记 → 翻轮播收全图 →
用页面自身的 cookie 直连下载。

用法：
  python core/douyin_cdp.py <note_url> --out-dir DIR [--port 9222] [--simulate]

输出（每行一条，父进程流式解析）：
  [info] ...     进度说明
  [media] <url>  发现一个媒体直链
  [save] <path>  已落盘一个文件
  [done] N       结束，共保存 N 个文件
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tools/，供 import ig_download

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")

# 图文图片的强特征：业务标签就是 aweme_images
IMG_MARK = "biz_tag=aweme_images"


def log(text: str) -> None:
    print(text, flush=True)


# --------------------------------------------------------------------------- #
# CDP 最小封装（自己管事件收集，ig_download 的 _cdp_roundtrip 会丢事件）
# --------------------------------------------------------------------------- #
class Cdp:
    def __init__(self, ws) -> None:
        self.ws = ws
        self.events: list[dict] = []
        self._mid = 0

    def call(self, method: str, params: dict | None = None, timeout: float = 15.0) -> dict:
        self._mid += 1
        mid = self._mid
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        end = time.time() + timeout
        self.ws.settimeout(1)
        while time.time() < end:
            try:
                raw = self.ws.recv()
            except Exception:
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if d.get("method") == "Network.responseReceived":
                self.events.append(d.get("params", {}))
                continue
            if d.get("id") == mid:
                return d
        return {}

    def pump(self, seconds: float) -> None:
        end = time.time() + seconds
        self.ws.settimeout(1)
        while time.time() < end:
            try:
                raw = self.ws.recv()
            except Exception:
                continue
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if d.get("method") == "Network.responseReceived":
                self.events.append(d.get("params", {}))

    def evaluate(self, expr: str, timeout: float = 20.0):
        res = self.call("Runtime.evaluate",
                        {"expression": expr, "returnByValue": True, "awaitPromise": True},
                        timeout=timeout)
        val = res.get("result", {}).get("result", {}).get("value")
        return val


def press_arrow_right(cdp: Cdp) -> None:
    for typ in ("keyDown", "keyUp"):
        cdp.call("Input.dispatchKeyEvent", {
            "type": typ, "key": "ArrowRight", "code": "ArrowRight",
            "windowsVirtualKeyCode": 39, "nativeVirtualKeyCode": 39,
        }, timeout=5)


EXPR_COLLECT = r"""(function(){
  var imgs = Array.from(document.querySelectorAll('img'))
      .map(function(i){return i.src||'';})
      .filter(function(u){return u && u.indexOf('__MARK__') >= 0;});
  var vids = Array.from(document.querySelectorAll('video'))
      .map(function(v){return v.src||v.currentSrc||'';})
      .filter(function(u){return u && u.indexOf('blob:') !== 0;});
  return JSON.stringify({imgs: imgs, vids: vids});
})()""".replace("__MARK__", IMG_MARK)


def collect_dom(cdp: Cdp) -> tuple[list[str], list[str]]:
    val = cdp.evaluate(EXPR_COLLECT)
    if not val:
        return [], []
    try:
        d = json.loads(val)
    except Exception:
        return [], []
    return list(d.get("imgs") or []), list(d.get("vids") or [])


def from_network(cdp: Cdp) -> tuple[list[str], list[str]]:
    """从网络响应里补漏（DOM 还没渲染出来的图、以及视频直链）。"""
    imgs: list[str] = []
    vids: list[str] = []
    for p in cdp.events:
        resp = p.get("response", {}) or {}
        url = resp.get("url", "") or ""
        mime = (resp.get("mimeType") or "").lower()
        if not url:
            continue
        if mime.startswith("image/"):
            if IMG_MARK in url and "douyinpic.com" in url:
                imgs.append(url)
        elif mime.startswith("video/"):
            vids.append(url)
    return imgs, vids


def dedup(seq: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for u in seq:
        key = u.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def ext_of(url: str, content_type: str) -> str:
    tail = url.split("?")[0].lower()
    for e in (".webp", ".jpeg", ".jpg", ".png", ".heic", ".mp4", ".mov"):
        if e in tail[-12:]:
            return e.lstrip(".")
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in ("image/webp", "image/jpeg", "image/png", "video/mp4"):
        return {"image/webp": "webp", "image/jpeg": "jpg",
                "image/png": "png", "video/mp4": "mp4"}[ctype]
    guessed = mimetypes.guess_extension(ctype or "") or ""
    return guessed.lstrip(".") or "bin"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--max-slides", type=int, default=40)
    a = ap.parse_args()

    try:
        import ig_download as ig
    except Exception as exc:
        log(f"[info] 无法加载 ig_download（CDP 依赖）：{type(exc).__name__}: {exc}")
        return 2
    if getattr(ig, "websocket", None) is None:
        log("[info] 缺少 websocket-client，无法接管 9222")
        return 2

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    note_id = [s for s in urlparse(a.url).path.split("/") if s][-1]

    # 选标签页：优先已登录的抖音页
    try:
        with ig.local_cdp_no_proxy():
            base, _ver = ig.resolve_cdp_base(a.port)
            tabs = ig._http_json(base, "/json/list")
    except Exception as exc:
        log(f"[info] 9222 不可用：{type(exc).__name__}: {exc}")
        return 3
    pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        log("[info] 9222 没有可用页面")
        return 3
    tab = next((t for t in pages if "douyin.com" in (t.get("url") or "")), pages[0])
    log(f"[info] 接管页面：{tab.get('title','')[:40]}")

    with ig.local_cdp_no_proxy():
        ws = ig.websocket.create_connection(tab["webSocketDebuggerUrl"],
                                            timeout=25, suppress_origin=True)
        try:
            cdp = Cdp(ws)
            cdp.call("Network.enable")
            cdp.call("Page.enable")
            cdp.call("Page.navigate", {"url": a.url})
            cdp.pump(7.0)

            imgs, vids = collect_dom(cdp)
            all_imgs, all_vids = list(imgs), list(vids)

            # 翻轮播，把未加载的图补齐
            stale = 0
            for _ in range(a.max_slides):
                press_arrow_right(cdp)
                cdp.pump(1.3)
                imgs, vids = collect_dom(cdp)
                before = len(all_imgs)
                for u in imgs + vids:
                    target = all_imgs if u in imgs else all_vids
                    if u not in target:
                        target.append(u)
                if len(all_imgs) == before:
                    stale += 1
                    if stale >= 3:
                        break
                else:
                    stale = 0

            n_imgs, n_vids = from_network(cdp)
            for u in n_imgs:
                if u not in all_imgs:
                    all_imgs.append(u)
            for u in n_vids:
                if u not in all_vids:
                    all_vids.append(u)

            # 取页面 cookie，供直连下载用
            cookies: dict[str, str] = {}
            try:
                res = cdp.call("Network.getCookies",
                               {"urls": ["https://www.douyin.com/"]}, timeout=15)
                for c in res.get("result", {}).get("cookies", []):
                    if c.get("name") and c.get("value"):
                        cookies[c["name"]] = c["value"]
            except Exception:
                pass
        finally:
            try:
                ws.close()
            except Exception:
                pass

    # 笔记页常有个 <video> 挂着 BGM mp3，不算用户要的"图片或视频"
    audio_ext = (".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac")
    all_vids = [u for u in all_vids
                if not u.split("?")[0].lower().endswith(audio_ext)]

    images = dedup(all_imgs)
    videos = dedup(all_vids)
    log(f"[info] 发现 {len(images)} 张图片、{len(videos)} 个视频（cookie {len(cookies)} 条）")
    if not images and not videos:
        log("[info] 没有解析到任何媒体直链（可能未登录，或该笔记已删除/仅好友可见）")
        return 4

    media = [(u, "image") for u in images] + [(u, "video") for u in videos]
    for u, _kind in media:
        log(f"[media] {u}")

    if a.simulate:
        log(f"[done] 0（simulate，未下载）")
        return 0

    # 下载必须在 no_proxy 上下文之外，才能走系统代理出网
    import requests
    headers = {"User-Agent": UA, "Referer": "https://www.douyin.com/",
               "Accept": "*/*"}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

    saved = 0
    for idx, (url, kind) in enumerate(media, 1):
        # CDP 引擎不走 gallery-dl 的 archive，靠"已存在且非空"保证重跑不重复下载
        if any(out_dir.glob(f"{note_id}_{idx:02d}.*")):
            saved += 1
            log(f"[skip] 已存在，跳过第 {idx:02d} 个")
            continue
        try:
            r = requests.get(url, headers=headers, timeout=60, stream=True)
            r.raise_for_status()
            ext = ext_of(url, r.headers.get("Content-Type", ""))
            name = f"{note_id}_{idx:02d}.{ext}"
            dest = out_dir / name
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(65536):
                    if chunk:
                        fh.write(chunk)
            if dest.stat().st_size <= 0:
                dest.unlink(missing_ok=True)
                log(f"[info] 空文件已丢弃：{name}")
                continue
            saved += 1
            log(f"[save] {dest}")
        except Exception as exc:
            log(f"[info] 下载失败 {url[:80]}：{type(exc).__name__}")
    log(f"[done] {saved}")
    return 0 if saved else 5


if __name__ == "__main__":
    sys.exit(main())
