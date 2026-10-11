"""登录态：CDP 自动取 / 粘贴文本 / 指定文件 → 统一成 Netscape 临时文件 → 用后即焚。

绝不把 cookie 值写进日志、JSON 或命令行回显。
"""
from __future__ import annotations

import atexit
import glob
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

# Netscape: domain  flag  path  secure  expires  name  value
RE_NETSCAPE = re.compile(
    r"^(?:#HttpOnly_)?(\S+)\t(\S+)\t(\S+)\t(TRUE|FALSE)\t(\d+)\t(\S+)\t(.*)$"
)

_TEMP_FILES: set[str] = set()


def _cleanup_all() -> None:
    for p in list(_TEMP_FILES):
        try:
            os.remove(p)
        except Exception:
            pass
        _TEMP_FILES.discard(p)


atexit.register(_cleanup_all)


def clean_stale(max_age: float = 3600.0) -> int:
    """清理本工具遗留超过 max_age 秒的临时 cookie 文件。"""
    removed = 0
    for p in glob.glob(os.path.join(tempfile.gettempdir(), "mdl_cookies_*")):
        try:
            if time.time() - os.path.getmtime(p) > max_age:
                os.remove(p)
                removed += 1
        except Exception:
            pass
    return removed


def validate_cookies_text(text: str) -> tuple[bool, str, int]:
    """返回 (是否可用, 说明, 解析出的行数)。"""
    lines = [l for l in (text or "").splitlines() if l.strip()]
    ok = 0
    for l in lines:
        if l.startswith("#") and not l.startswith("#HttpOnly_"):
            continue
        if RE_NETSCAPE.match(l) or re.match(r"^\s*[\w.\-]+\s*=\s*\S+\s*$", l):
            ok += 1
    if ok == 0:
        return False, "没解析到任何 cookie 行（需要 Netscape 格式或 name=value 对）", 0
    return True, f"解析到 {ok} 条 cookie", ok


def normalize_cookies_text(text: str, domain: str) -> list[str]:
    """把粘贴内容规范成 Netscape 行；裸 `name=value` 用 domain 补全。"""
    out = ["# Netscape HTTP Cookie File"]
    expire = int(time.time()) + 86400
    for line in (text or "").splitlines():
        line = line.rstrip("\r\n")
        if not line.strip():
            continue
        if line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        m = RE_NETSCAPE.match(line)
        if m:
            out.append(line)
            continue
        m2 = re.match(r"^\s*([\w.\-]+)\s*=\s*(.+?)\s*$", line)
        if m2 and domain:
            out.append(f"{domain}\tTRUE\t/\tTRUE\t{expire}\t{m2.group(1)}\t{m2.group(2)}")
    return out


def write_temp_cookies(rows: list[str]) -> Path:
    fd, path = tempfile.mkstemp(prefix="mdl_cookies_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + "\n")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    _TEMP_FILES.add(path)
    return Path(path)


def drop_temp(path: Path | str) -> None:
    """删除我们自己生成的临时 cookie 文件（用户自带的文件绝不能调这个）。"""
    p = str(path)
    try:
        os.remove(p)
    except Exception:
        pass
    _TEMP_FILES.discard(p)


def _import_ig():
    """惰性 import ig_download（它就在 tools/ 同级）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import ig_download as ig  # noqa: WPS433
    return ig


def cdp_cookies(port: int = 9222, url_hint: str = "") -> dict[str, str] | None:
    """从本机 Chrome 调试端口抓 Instagram cookie（失败返回 None）。"""
    try:
        return _import_ig().harvest_cookies(port, url_hint or "")
    except Exception:
        return None


def probe_cdp(port: int = 9222, username: str = "") -> dict:
    """**只探测** Chrome 9222，不下载、不改任何配置。

    返回（detail 已 redact，绝不含 cookie 值）：
      {ok, port, reachable, browser, ws_url,
       has_instagram_page, page_url, logged_in, ig_username,
       cookie_count, detail}
    """
    out: dict = {
        "ok": False, "port": port, "reachable": False, "browser": "",
        "ws_url": "", "has_instagram_page": False, "page_url": "",
        "logged_in": None, "ig_username": "", "cookie_count": 0, "detail": "",
    }
    try:
        ig = _import_ig()
    except Exception as exc:
        out["detail"] = f"无法加载 ig_download：{type(exc).__name__}: {exc}"
        return out

    REQUIRED = {"sessionid", "csrftoken"}

    # 1) 端口可达性（只在绕代理上下文中做，finally 自动还原）
    try:
        with ig.local_cdp_no_proxy():
            base, ver = ig.resolve_cdp_base(port)
            out["reachable"] = True
            out["browser"] = str(ver.get("Browser", ""))
            out["ws_url"] = str(ver.get("webSocketDebuggerUrl", ""))
    except Exception as exc:
        out["detail"] = f"调试端口 {port} 不可用（{type(exc).__name__}）。请用 --remote-debugging-port={port} 启动 Chrome"
        return out

    # 2) 是否有 instagram 页面
    try:
        with ig.local_cdp_no_proxy():
            tabs = ig._http_json(base, "/json/list")
            page = ig.pick_instagram_page(tabs, username)
            out["has_instagram_page"] = True
            out["page_url"] = str(page.get("url", ""))
    except Exception as exc:
        out["detail"] = f"端口可用，但没找到 instagram.com 页面（{type(exc).__name__}）"
        return out

    # 3) 取 cookie
    try:
        ck = ig.harvest_cookies(port, username)
    except Exception as exc:
        out["detail"] = f"取 cookie 失败：{type(exc).__name__}"
        return out
    out["cookie_count"] = len(ck)
    missing = REQUIRED - set(ck)
    if missing:
        out["detail"] = f"cookie 缺少必需项 {sorted(missing)}，请在该页面重新登录 Instagram"
        return out

    # 4) test_login() 才是真判据（is_logged_in 恒真不可信）
    try:
        from instaloader import Instaloader
        L = Instaloader(quiet=True, max_connection_attempts=1, request_timeout=30.0)
        L.load_session("__probe__", dict(ck))
        who = L.test_login()
        out["logged_in"] = bool(who)
        out["ig_username"] = who or ""
    except Exception as exc:
        out["detail"] = f"登录态校验异常：{type(exc).__name__}"
        return out

    if out["logged_in"]:
        out["ok"] = True
        out["detail"] = f"9222 可用，已登录 Instagram（{out['ig_username']}）"
    else:
        out["detail"] = "cookie 存在但已过期，请回浏览器刷新 Instagram 登录"
    return out
