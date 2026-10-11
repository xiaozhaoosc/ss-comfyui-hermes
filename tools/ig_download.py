#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ig_download.py — Instagram 博主主页下载器

引擎分工：
  * instaloader  —— 主页枚举 + 图片/视频/轮播下载 + 元数据
  * yt-dlp       —— 【单帖】视频兜底（yt-dlp 的 instagram:user 主页枚举器官方标注已损坏，不可承担枚举）

登录态：从本机 Chrome 的 CDP 端口抓取 Instagram cookie 字典，注入 instaloader。
        全程不索要、不接收、不存储密码；cookie 只活在内存 pd，不入日志。

三种模式：
  --count N   按发布时间倒序取前 N 个帖子（规避旧置顶帖）
  --days N    取最近 N×24 小时内发布的帖子
  都不给      全量

用法：
  python tools/ig_download.py ayano.fj --count 2 --dry-run
  python tools/ig_download.py ayano.fj --count 2 --sleep 3
  python tools/ig_download.py ayano.fj --days 7
  python tools/ig_download.py ayano.fj            # 全量
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_YTDLP = REPO_ROOT / "tools" / "yt-dlp" / "yt-dlp.exe"
ANACONDA_PY = r"C:\Users\kenzhao\anaconda3\python.exe"

try:
    from instaloader import Instaloader, Profile, Post
except ImportError:
    sys.stderr.write(
        "[FATAL] 缺少 instaloader。请用隔离解释器运行：\n"
        "  C:/Users/kenzhao/.workbuddy/binaries/python/envs/default/Scripts/python.exe\n"
    )
    raise

from instaloader.exceptions import (  # noqa: E402
    AbortDownloadException,
    ConnectionException,
    InstaloaderException,
    LoginRequiredException,
    PrivateProfileNotFollowedException,
    ProfileNotExistsException,
    QueryReturnedForbiddenException,
    TooManyRequestsException,
)

try:
    import requests  # noqa: E402
except ImportError:
    requests = None

try:
    import websocket  # noqa: E402  (websocket-client)
except ImportError:
    websocket = None


class AuthError(Exception):
    """登录态不可用（缺失/过期），需人工回浏览器处理。"""


class CdpError(Exception):
    """本机 Chrome 调试端口不可用或未找到 Instagram 页面。"""


# --------------------------------------------------------------------------- #
# 日志：绝不打印 cookie 值
# --------------------------------------------------------------------------- #
_SECRET_VALUES: set[str] = set()


def note_secret(value: str | None) -> None:
    if value and len(value) >= 6:
        _SECRET_VALUES.add(value)


def redact(text: str) -> str:
    out = str(text)
    for secret in _SECRET_VALUES:
        out = out.replace(secret, "<redacted>")
    return out


def log(msg: str = "") -> None:
    print(redact(str(msg)), flush=True)


# --------------------------------------------------------------------------- #
# 代理上下文：连 localhost 要绕代理，但出外网必须保留代理 —— 用完立刻还原
# --------------------------------------------------------------------------- #
_CDP_ENV_KEYS = [
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
]
_MISSING = object()


@contextmanager
def local_cdp_no_proxy():
    """仅在访问本机 CDP 端口时临时禁用代理，finally 中逐项还原。

    不还原的话，Instaloader 后续访问 Instagram 会失去出网能力。
    """
    prev = {k: os.environ.get(k, _MISSING) for k in _CDP_ENV_KEYS}
    try:
        for k in _CDP_ENV_KEYS:
            os.environ.pop(k, None)
        os.environ["NO_PROXY"] = "*"
        yield
    finally:
        for k, v in prev.items():
            if v is _MISSING:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --------------------------------------------------------------------------- #
# 目标归一化 / 输出目录
# --------------------------------------------------------------------------- #
def normalize_username(target: str) -> str:
    raw = (target or "").strip().strip("@").strip()
    if raw.lower().startswith(("http://", "https://")):
        path = urlparse(raw).path.strip("/")
        raw = path.split("/")[0] if path else raw
        raw = raw.split("?")[0]
    raw = raw.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,50}", raw):
        raise ValueError(f"无法从 {target!r} 解析出合法 Instagram 用户名")
    return raw


def safe_dirname(username: str) -> str:
    return "instagram_" + re.sub(r"[^A-Za-z0-9_-]", "_", username)


def resolve_out_dir(username: str, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    today = dt.date.today().isoformat()
    return (REPO_ROOT / "output" / today / safe_dirname(username)).resolve()


# --------------------------------------------------------------------------- #
# CDP：从已登录 Chrome 取 Instagram cookie
# --------------------------------------------------------------------------- #
COOKIE_KEEP = {
    "sessionid", "csrftoken", "ds_user_id", "mid", "ig_did",
    "datr", "rur", "wd", "dpr", "ps_l", "ps_n",
}
REQUIRED_COOKIES = {"sessionid", "csrftoken"}


def _http_json(base: str, path: str, timeout: float = 8.0):
    if requests is None:
        raise CdpError("缺少 requests，无法访问 CDP HTTP 端点")
    resp = requests.get(base.rstrip("/") + path, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def resolve_cdp_base(port: int) -> tuple[str, dict]:
    last_err = None
    for host in ("127.0.0.1", "localhost"):
        base = f"http://{host}:{port}"
        try:
            ver = _http_json(base, "/json/version")
            if ver.get("webSocketDebuggerUrl"):
                return base, ver
        except Exception as exc:
            last_err = exc
    raise CdpError(
        f"本机 Chrome 调试端口 {port} 不可用（{type(last_err).__name__}）。\n"
        f"  请用 --remote-debugging-port={port} 启动 Chrome 并确认 Instagram 已登录。\n"
        f"  参考：tools/launch_flow_cdp_chrome.bat"
    )


def pick_instagram_page(tabs: list[dict], username: str) -> dict:
    pages = [t for t in tabs if t.get("type") == "page"]
    ig_pages = []
    for t in pages:
        try:
            host = urlparse(t.get("url", "")).netloc
        except Exception:
            continue
        if host.endswith("instagram.com"):
            ig_pages.append(t)
    if not ig_pages:
        raise CdpError("9222 浏览器里没有已打开的 instagram.com 页面，请先打开目标主页")
    needle = username.lower()
    for t in ig_pages:
        if needle and needle in t.get("url", "").lower():
            return t
    return ig_pages[0]


def _cdp_roundtrip(ws, msg_id: int, method: str, params: dict, timeout: float = 25.0):
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        ws.settimeout(5)
        try:
            raw = ws.recv()
        except Exception:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if data.get("id") != msg_id:
            continue  # 跳过事件推送
        if "error" in data:
            raise CdpError(f"CDP {method} 失败：{data['error'].get('message')}")
        return data
    raise CdpError(f"CDP {method} 响应超时")


def _is_expired(cookie: dict) -> bool:
    exp = cookie.get("expires", -1)
    try:
        exp = float(exp)
    except Exception:
        return False
    if exp <= 0:  # -1 = 会话 cookie
        return False
    return exp <= time.time()


def _score(cookie: dict) -> int:
    s = 0
    domain = cookie.get("domain", "")
    if domain == "www.instagram.com":
        s += 4
    elif domain == ".instagram.com":
        s += 3
    elif domain == "instagram.com":
        s += 2
    if cookie.get("path") == "/":
        s += 1
    return s


def harvest_cookies(port: int, username: str) -> dict[str, str]:
    """从 9222 已登录 Chrome 取 Instagram cookie 字典（值不落盘、不打印）。"""
    if websocket is None:
        raise CdpError("缺少 websocket-client，请 pip install websocket-client 到隔离 venv")
    with local_cdp_no_proxy():
        base, _ver = resolve_cdp_base(port)
        tabs = _http_json(base, "/json/list")
        page = pick_instagram_page(tabs, username)
        ws_url = page.get("webSocketDebuggerUrl")
        if not ws_url:
            raise CdpError("目标页面缺少 webSocketDebuggerUrl")
        ws = websocket.create_connection(ws_url, timeout=20, suppress_origin=True)
        try:
            _cdp_roundtrip(ws, 1, "Network.enable", {})
            try:
                res = _cdp_roundtrip(ws, 2, "Network.getCookies",
                                     {"urls": ["https://www.instagram.com/",
                                               "https://i.instagram.com/"]})
            except CdpError:
                res = _cdp_roundtrip(ws, 3, "Network.getCookies", {})
            raw_cookies = res.get("result", {}).get("cookies", [])
        finally:
            try:
                ws.close()
            except Exception:
                pass

    out: dict[str, str] = {}
    for c in raw_cookies:
        name = c.get("name")
        domain = c.get("domain", "")
        if name not in COOKIE_KEEP:
            continue
        if not (domain == "instagram.com" or domain.endswith(".instagram.com")):
            continue
        if _is_expired(c):
            continue
        value = c.get("value", "")
        if not value:
            continue
        if name in out and _score(out.get(f"__meta_{name}__", {})) >= _score(c):
            continue
        out[f"__meta_{name}__"] = c  # 只比较用，导出时会剔除
        out[name] = value
        note_secret(value)
    return {k: v for k, v in out.items() if not k.startswith("__meta_")}


def write_netscape_cookies(cookies: dict[str, str]) -> Path:
    """CDP cookie 字典 → Netscape cookies.txt，供 gallery-dl / yt-dlp 使用。

    只用系统临时目录（不落 repo、不落产物目录），返回值不入日志；调用方须在 finally 删除。
    """
    fd, path = tempfile.mkstemp(prefix="ig_cookies_", suffix=".txt")
    try:
        expire = int(time.time()) + 3600
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("# Netscape HTTP Cookie File\n")
            for name, value in cookies.items():
                if not value:
                    continue
                fh.write(f".instagram.com\tTRUE\t/\tTRUE\t{expire}\t{name}\t{value}\n")
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.remove(path)
        except Exception:
            pass
        raise
    return Path(path)


def drop_cookie_file(path: Path | None, ours: bool = True) -> None:
    """用后即焚：删除**我们自己生成**的临时 cookie 文件。

    ours=False 表示文件是用户通过 --cookies-file 提供的，绝不能删。
    """
    if not path or not ours:
        return
    try:
        os.remove(path)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 引擎：gallery-dl（主）/ yt-dlp（次）/ instaloader（兜底）
# --------------------------------------------------------------------------- #
def gallery_dl_cmd(args, username: str, out_dir: Path, cookie_file: Path | None) -> list[str]:
    """构造 gallery-dl 命令。三模式映射：
       全量     -> 不加过滤
       前 N 条  -> --post-range 1-N
       最近 N 天-> --post-filter date.timestamp() >= cutoff
       dry-run  -> -s/--simulate
    """
    cmd = [
        sys.executable, "-m", "gallery_dl",
        "--sleep-request", str(max(args.sleep, 3.0)),
        "-D", str(out_dir),
        "-f", "{date:%Y-%m-%d_%H-%M-%S}_{shortcode}_{num}.{extension}",
    ]
    if cookie_file:
        cmd += ["--cookies", str(cookie_file)]
    if args.resume and not args.dry_run:
        cmd += ["--download-archive", str(out_dir / "_gallery_archive.txt")]
    if args.count is not None:
        cmd += ["--post-range", f"1-{args.count}"]
    if args.days is not None:
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).timestamp()
        cmd += ["--post-filter", f"date.timestamp() >= {cutoff}"]
    if args.videos_only:
        cmd += ["--filter", "extension in ('mp4')"]
    elif args.images_only:
        cmd += ["--filter", "extension in ('jpg','png','webp')"]
    if args.dry_run:
        cmd += ["--simulate"]
    cmd.append(f"https://www.instagram.com/{username}/")
    return cmd


def ytdlp_profile_cmd(args, username: str, out_dir: Path, cookie_file: Path | None) -> list[str]:
    """构造 yt-dlp 命令（新版 instagram:user 已修复，可枚举主页）。
       前 N 条 -> --playlist-items 1:N
       最近 N 天-> --dateafter YYYYMMDD
    """
    exe = Path(args.yt_dlp_path)
    cmd = [
        str(exe), f"https://www.instagram.com/{username}/",
        "-o", str(out_dir / "%(upload_date>%Y-%m-%d)s_%(id)s.%(ext)s"),
        "--no-overwrites", "--retries", "2", "--fragment-retries", "2",
        "--sleep-request", "3", "--no-warnings",
        "-f", "bestvideo*+bestaudio/best", "--merge-output-format", "mp4",
    ]
    if cookie_file:
        cmd += ["--cookies", str(cookie_file)]
    if args.resume and not args.dry_run:
        cmd += ["--download-archive", str(out_dir / "_ytdlp_archive.txt")]
    if args.count is not None:
        cmd += ["--playlist-items", f"1:{args.count}"]
    if args.days is not None:
        cut = dt.datetime.now() - dt.timedelta(days=args.days)
        cmd += ["--dateafter", cut.strftime("%Y%m%d")]
    if args.dry_run:
        cmd += ["--simulate"]
    return cmd


def run_cli_engine(name: str, cmd: list[str], out_dir: Path, args) -> int:
    """执行外部下载引擎并判断成败。返回 0 = 拿到数据。"""
    safe = " ".join(str(c) for c in cmd if not str(c).endswith(".txt"))
    log(f"[{name}] 命令：{redact(safe)[:260]}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception as exc:
        log(f"[{name}] 调用失败：{type(exc).__name__}: {exc}")
        return 1
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if args.verbose and stderr:
        log(f"[{name}] stderr: {redact(stderr)[-600:]}")

    lines = [l.strip() for l in stdout.splitlines() if l.strip()]
    if args.dry_run:
        # gallery-dl --simulate 每行输出 "<路径>"（可能带 '#' 前缀），有行即算枚举成功
        entries = [l.lstrip("#").strip() for l in lines if l.lstrip("#").strip()]
        log(f"[{name}] 枚举到 {len(entries)} 条")
        for l in entries[:10]:
            log(f"    {l[:120]}")
        return 0 if entries else 1

    if proc.returncode != 0:
        log(f"[{name}] 退出码 {proc.returncode}")
        if stderr:
            log(f"[{name}] 错误：{redact(stderr)[-300:]}")
    media = collect_media(out_dir)
    log(f"[{name}] 落盘 {len(media)} 个媒体文件")
    return 0 if media else 1


def collect_media(out_dir: Path) -> list[Path]:
    if not out_dir.is_dir():
        return []
    exts = {".jpg", ".jpeg", ".png", ".webp", ".mp4"}
    return sorted(p for p in out_dir.rglob("*")
                  if p.is_file() and p.suffix.lower() in exts)


def run_gallery_dl(args, username: str, out_dir: Path, cookie_file: Path | None) -> int:
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
    rc = run_cli_engine("gallery-dl", gallery_dl_cmd(args, username, out_dir, cookie_file),
                        out_dir, args)
    if rc == 0 and (args.stories or args.highlights):
        for tag, url in (
            ("Story", f"https://www.instagram.com/stories/{username}/") if args.stories else (None, None),
            ("Highlight", f"https://www.instagram.com/{username}/highlights/") if args.highlights else (None, None),
        ):
            if not url:
                continue
            sub = [sys.executable, "-m", "gallery_dl", "--sleep-request", "3",
                   "-D", str(out_dir / tag.lower())]
            if cookie_file:
                sub += ["--cookies", str(cookie_file)]
            if args.dry_run:
                sub += ["--simulate"]
            sub.append(url)
            run_cli_engine(f"gallery-dl:{tag}", sub, out_dir / tag.lower(), args)
    return rc


def run_ytdlp_profile(args, username: str, out_dir: Path, cookie_file: Path | None) -> int:
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
    exe = Path(args.yt_dlp_path)
    if not exe.is_file():
        log("[yt-dlp] 可执行文件不存在，跳过该引擎")
        return 1
    return run_cli_engine("yt-dlp", ytdlp_profile_cmd(args, username, out_dir, cookie_file),
                          out_dir, args)


# --------------------------------------------------------------------------- #
# instaloader 构建与鉴权
# --------------------------------------------------------------------------- #
def build_loader(args, dirname_pattern: str) -> Instaloader:
    pictures = not args.videos_only
    videos = not args.images_only
    thumbs = not (args.videos_only or args.images_only)
    return Instaloader(
        sleep=True,                          # 保持内建限速
        quiet=not args.verbose,
        download_pictures=pictures,
        download_videos=videos,
        download_video_thumbnails=thumbs,
        download_geotags=False,              # 不拉地理位置
        download_comments=False,             # 不拉评论
        save_metadata=True,
        compress_json=False,                 # 明文 json 便于核对
        post_metadata_txt_pattern="{caption}",
        max_connection_attempts=2,
        request_timeout=60.0,
        resume_prefix="iterator" if args.resume else None,
        check_resume_bbd=args.resume,
        fatal_status_codes=[429],            # 429 立即停机，不轰炸
        sanitize_paths=True,
        dirname_pattern=dirname_pattern,
        filename_pattern="{date_utc}_{shortcode}",
    )


def authenticate(loader: Instaloader, cookies: dict[str, str]) -> str:
    missing = REQUIRED_COOKIES - set(cookies)
    if missing:
        raise AuthError(
            f"Chrome 登录态缺少必要 cookie：{sorted(missing)}。"
            f"请在浏览器打开 https://www.instagram.com/ 重新登录后再试。"
        )
    loader.load_session("__cdp_probe__", dict(cookies))
    try:
        who = loader.test_login()
    except Exception as exc:
        raise AuthError(f"登录态校验失败（{type(exc).__name__}）: {redact(str(exc))}")
    if not who:
        raise AuthError("Chrome 里的 Instagram 登录态已过期，请在浏览器刷新登录后重试")
    loader.load_session(who, dict(cookies))
    return who


# --------------------------------------------------------------------------- #
# 选帖：三模式 + 早停
# --------------------------------------------------------------------------- #
def _aware(d: dt.datetime) -> dt.datetime:
    # Post.date_utc = datetime.utcfromtimestamp(...) → 无时区 UTC
    if d.tzinfo is None:
        return d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def _by_newest(post: Post):
    return _aware(post.date_utc)


def select_posts(profile: Profile, count: int | None, days: int | None):
    """返回 (posts, mode)。三种模式都会尽早停止分页，避免浪费请求、保护账号。"""
    if count is not None:
        wanted = count + 3          # 多取 3 条以规避置顶帖，仍落在第一页(12节点)内
        cands: list[Post] = []
        for post in profile.get_posts():
            cands.append(post)
            if len(cands) >= wanted:
                break
        cands.sort(key=_by_newest, reverse=True)
        return cands[:count], f"前 {count} 条"

    if days is not None:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
        picked: list[Post] = []
        seen = 0
        for post in profile.get_posts():
            seen += 1
            when = _aware(post.date_utc)
            if when >= cutoff:
                picked.append(post)
            elif seen > 3:          # 前 3 条即使过期也不停（可能是置顶帖）
                break
        picked.sort(key=_by_newest, reverse=True)
        return picked, f"最近 {days} 天"

    posts = list(profile.get_posts())
    return posts, "全量"


def expected_media(post: Post, videos_only: bool, images_only: bool) -> tuple[int, int]:
    """返回 (期望图片/缩略图数, 期望视频数)。"""
    if post.typename == "GraphSidecar":
        flags = post.get_is_videos()
        n_video = sum(1 for f in flags if f)
        n_image = len(flags) if not videos_only else 0
        return n_image, n_video
    if post.is_video:
        return (1 if not videos_only else 0), 1 if not images_only else 0
    return (1 if not images_only else 0), 0


# --------------------------------------------------------------------------- #
# 产物校验
# --------------------------------------------------------------------------- #
def verify_image(path: Path) -> tuple[bool, str]:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False, "文件缺失或为空"
        head = path.open("rb").read(32)
    except Exception as exc:
        return False, f"读取失败: {exc}"
    if head.startswith(b"\xff\xd8\xff"):
        return True, "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True, "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True, "webp"
    return False, "图片文件头异常"


def _cv2_probe(path: Path) -> tuple[bool, str] | None:
    """用 cv2 做深校验；本机隔离 venv 无 cv2 时借 anaconda 子进程。返回 None 表示环境不支持。"""
    code = (
        "import sys, cv2\n"
        "cap = cv2.VideoCapture(sys.argv[1])\n"
        "if not cap.isOpened():\n"
        "    print('FAIL open')\n"
        "    sys.exit(0)\n"
        "n = int(cap.get(cv2.CAP_PROP_FRACT_COUNT) if False else cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)\n"
        "w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)\n"
        "h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)\n"
        "ok1, f1 = cap.read()\n"
        "cap.set(cv2.CAP_PROP_POS_FRAMES, max(n // 2, 0))\n"
        "ok2, f2 = cap.read()\n"
        "decoded = bool(ok1 or ok2)\n"
        "mean = float(f2.mean()) if ok2 and f2 is not None else (float(f1.mean()) if ok1 and f1 is not None else -1.0)\n"
        "cap.release()\n"
        "print('OK' if (n > 0 and decoded and w > 0 and h > 0) else 'FAIL frames', n, w, h, round(mean, 3))\n"
    )
    try:
        proc = subprocess.run(
            [ANACONDA_PY, "-c", code, str(path)],
            capture_output=True, text=True, timeout=90,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return None
    parts = out.split()
    if parts[0] != "OK":
        return False, f"无法解码帧（{out}）"
    mean = float(parts[4]) if len(parts) >= 5 else -1.0
    detail = f"{parts[2]}x{parts[3]}, {parts[1]} 帧"
    if 0.0 <= mean < 1.0:
        return True, detail + "（疑似黑屏，仅警告）"
    return True, detail


def verify_video(path: Path, deep: bool = True) -> tuple[bool, str]:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False, "文件缺失或为空"
        head = path.open("rb").read(4096)
    except Exception as exc:
        return False, f"读取失败: {exc}"
    if b"ftyp" not in head:
        return False, "非 MP4（缺少 ftyp box）"
    if not deep:
        return True, "mp4 结构正常（未做深校验）"
    probe = _cv2_probe(path)
    if probe is None:
        return True, "mp4 结构正常（本机无 cv2，跳过验帧）"
    return probe


# --------------------------------------------------------------------------- #
# yt-dlp 单帖兜底（不传 cookie，不打印命令）
# --------------------------------------------------------------------------- #
def ytdlp_fallback(post_url: str, out_dir: Path, name_base: str, args) -> tuple[bool, str]:
    exe = Path(args.yt_dlp_path)
    if not exe.is_file():
        return False, f"yt-dlp 不存在: {exe}"
    cmd = [
        str(exe), post_url,
        "-o", str(out_dir / f"{name_base}_yt.%(ext)s"),
        "--no-overwrites",
        "--retries", "2",
        "--fragment-retries", "2",
        "--no-warnings",
        "-f", "bestvideo*+bestaudio/best",
        "--merge-output-format", "mp4",
    ]
    if args.chrome_profile:
        cmd += ["--cookies-from-browser", f"chrome:{args.chrome_profile}"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as exc:
        return False, f"yt-dlp 调用失败: {exc}"
    if proc.returncode == 0:
        return True, "yt-dlp 兜底成功"
    tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
    return False, f"yt-dlp 失败: {tail[0][:160]}"


# --------------------------------------------------------------------------- #
# 单实例互斥（保护账号，禁止并发多跑）
# --------------------------------------------------------------------------- #
@contextmanager
def account_mutex(username: str, enabled: bool = True):
    handle = None
    if enabled and sys.platform == "win32":
        try:
            import ctypes
            name = f"Local\\ig_download_{re.sub(r'[^A-Za-z0-9_-]', '_', username)}"
            handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
            if handle and ctypes.windll.kernel32.GetLastError() == 183:
                ctypes.windll.kernel32.CloseHandle(handle)
                raise RuntimeError(f"账号 {username} 已有下载实例在运行，禁止并发（会触发风控）")
        except RuntimeError:
            raise
        except Exception:
            handle = None
    try:
        yield
    finally:
        if handle:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# 状态文件（只记 shortcode，绝不记 cookie）
# --------------------------------------------------------------------------- #
def load_state(out_dir: Path, enabled: bool) -> set[str]:
    p = out_dir / "_ig_state.json"
    if not enabled:
        return set()
    if p.is_file():
        try:
            return set(json.loads(p.read_text(encoding="utf-8")).get("done", []))
        except Exception:
            return set()
    return set()


def save_state(out_dir: Path, done: set[str], enabled: bool) -> None:
    if not enabled:
        return
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "_ig_state.json").write_text(
            json.dumps({"updated": dt.datetime.now().isoformat(timespec="seconds"),
                        "done": sorted(done)}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ig_download.py",
        description="Instagram 博主主页下载器（instaloader 主 + yt-dlp 单帖视频兜底）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python tools/ig_download.py ayano.fj --count 2 --dry-run\n"
            "  python tools/ig_download.py ayano.fj --count 2 --sleep 3\n"
            "  python tools/ig_download.py ayano.fj --days 7\n"
            "  python tools/ig_download.py ayano.fj\n"
        ),
    )
    p.add_argument("target", help="用户名 / @用户名 / 主页 URL")
    p.add_argument("--count", type=int, help="下载最新的前 N 个帖子（按发布时间倒序）")
    p.add_argument("--days", type=int, help="只下载最近 N 天内发布的帖子")
    p.add_argument("--dry-run", action="store_true", help="只枚举不下载")
    p.add_argument("--videos-only", action="store_true", help="只下载视频（含 Reels）")
    p.add_argument("--images-only", action="store_true", help="只下载静态图片")
    p.add_argument("--stories", action="store_true", help="额外下载当前 Story（默认关）")
    p.add_argument("--highlights", action="store_true", help="额外下载精选 Highlight（默认关）")
    p.add_argument("--out-dir", help=f"输出目录，默认 output/<YYYY-MM-DD>/instagram_<用户名>/")
    p.add_argument("--sleep", type=float, default=3.0, help="每帖最小间隔秒（下限 1，默认 3）")
    p.add_argument("--cdp-port", type=int, default=9222, help="Chrome 调试端口，默认 9222")
    p.add_argument("--anonymous", action="store_true",
                   help="不使用浏览器登录态（当前网络下必然被 429 拦截，仅供验证）")
    p.add_argument("--cookies-file",
                   help="直接指定 Netscape 格式 cookies.txt（优先于 CDP；该文件不会被删除）")
    p.add_argument("--no-yt-dlp-fallback", action="store_true", help="关闭视频兜底")
    p.add_argument("--yt-dlp-path", default=str(DEFAULT_YTDLP), help="yt-dlp 可执行文件路径")
    p.add_argument("--chrome-profile", help="传给 yt-dlp 的 Chrome profile 名（不含 cookie 值）")
    p.add_argument("--no-resume", action="store_true", help="忽略已完成记录")
    p.add_argument("--engine", choices=["auto", "gallery-dl", "yt-dlp", "instaloader"],
                   default="auto",
                   help="下载引擎，默认 auto（gallery-dl → yt-dlp → instaloader 择优）")
    p.add_argument("--verbose", action="store_true", help="打印引擎原始日志")
    return p


def validate_args(args) -> None:
    if args.count is not None and args.days is not None:
        raise SystemExit("--count 与 --days 互斥")
    if args.videos_only and args.images_only:
        raise SystemExit("--videos-only 与 --images-only 互斥")
    if args.count is not None and args.count <= 0:
        raise SystemExit("--count 必须为正整数")
    if args.days is not None and args.days <= 0:
        raise SystemExit("--days 必须为正整数")
    if args.sleep < 1.0:
        log("[warn] --sleep 低于 1 秒不利于账号安全，已抬升到 1 秒")
        args.sleep = 1.0


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_args(args)
    args.resume = not args.no_resume

    username = normalize_username(args.target)
    out_dir = resolve_out_dir(username, args.out_dir)

    log(f"[账号] {username}")
    log(f"[输出] {out_dir}")
    if args.dry_run:
        log("[模式] dry-run：只枚举，不建目录、不下载")

    cookies: dict[str, str] = {}
    cookie_file: Path | None = None
    owns_cookie_file = True          # False = 用户自带文件，退出时绝不删除

    if args.cookies_file:
        p = Path(args.cookies_file).expanduser()
        if not p.is_file():
            return _fail(f"--cookies-file 指向的文件不存在：{p}")
        cookie_file, owns_cookie_file = p, False
        log(f"[登录态] 使用用户提供的 cookies 文件（不会删除）：{p.name}")
    elif not args.anonymous:
        try:
            cookies = harvest_cookies(args.cdp_port, username)
            log(f"[登录态] 已从 Chrome {args.cdp_port} 取得 {len(cookies)} 个 Instagram cookie "
                f"（取值不打印）")
        except CdpError as exc:
            return _fail(f"登录态获取失败：{exc}")
        cookie_file = write_netscape_cookies(cookies)
        log("[登录态] 已生成临时 cookies 文件（系统临时目录，退出即删）")
    else:
        log("[登录态] 匿名模式：预计会被 Instagram 限速")

    # 非 instaloader 引擎：直接走 CLI，不需要构建 loader
    if args.engine in ("gallery-dl", "yt-dlp"):
        try:
            if args.engine == "gallery-dl":
                rc = run_gallery_dl(args, username, out_dir, cookie_file)
            else:
                rc = run_ytdlp_profile(args, username, out_dir, cookie_file)
            if rc == 0 and not args.dry_run:
                report_done(out_dir)
            return rc
        except KeyboardInterrupt:
            log("\n[中断] 用户中止。")
            return 130
        finally:
            drop_cookie_file(cookie_file, owns_cookie_file)

    # dirname_pattern 用相对目录名，配合 cwd 切换，避免 Windows 路径被 sanitize 改写
    loader = build_loader(args, dirname_pattern=out_dir.name)
    login_as = None
    if cookies:
        try:
            login_as = authenticate(loader, cookies)
            log(f"[登录态] 校验通过，当前登录账号：{login_as}")
        except AuthError as exc:
            drop_cookie_file(cookie_file, owns_cookie_file)
            return _fail(str(exc))

    old_cwd = os.getcwd()
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(out_dir.parent)

    try:
        # auto：先试 gallery-dl，再 yt-dlp，最后 instaloader
        if args.engine == "auto":
            for name, fn in (("gallery-dl", run_gallery_dl),
                             ("yt-dlp", run_ytdlp_profile)):
                log(f"\n[引擎] 尝试 {name} ...")
                try:
                    if fn(args, username, out_dir, cookie_file) == 0:
                        if not args.dry_run:
                            report_done(out_dir)
                        return 0
                except Exception as exc:
                    log(f"[引擎] {name} 异常：{redact(str(exc))[:200]}")
                log(f"[引擎] {name} 没拿到数据，降级下一个")
            log("\n[引擎] 落到 instaloader（已知其 web_profile_info 端点易被 429）")
        return run_profile(args, loader, username, out_dir, login_as)
    except AbortDownloadException as exc:
        log("")
        log("=" * 64)
        log("[停机] Instagram 返回致命状态码（很可能是 429 限流）。")
        log(f"       原因：{redact(str(exc))}")
        log("       已停止请求，未完成部分可稍后用相同命令续跑（默认开启断点续传）。")
        log("       建议冷却 >= 15 分钟；期间请勿在 Instagram App 内频繁操作。")
        log("=" * 64)
        return 3
    except TooManyRequestsException:
        log("\n[停机] 触发 429 Too Many Requests，已保存进度，请冷却后再续跑。")
        return 3
    except QueryReturnedForbiddenException:
        log("\n[停机] Instagram 返回 403（登录态失效或权限不足），请回浏览器刷新登录。")
        return 4
    except LoginRequiredException:
        log("\n[停机] 该内容需要登录，当前登录态无效，请回浏览器刷新登录。")
        return 4
    except PrivateProfileNotFollowedException:
        log(f"\n[停机] {username} 是私密账号且当前登录账号未关注，不做绕过。")
        return 5
    except ProfileNotExistsException:
        log(f"\n[停机] 账号 {username} 不存在。")
        return 5
    except ConnectionException as exc:
        log(f"\n[停机] 网络异常：{redact(str(exc))}")
        return 6
    except InstaloaderException as exc:
        log(f"\n[停机] Instaloader 异常：{redact(str(exc))}")
        return 6
    except KeyboardInterrupt:
        log("\n[中断] 用户中止，已保存进度。")
        return 130
    finally:
        drop_cookie_file(cookie_file, owns_cookie_file)
        try:
            os.chdir(old_cwd)
        except Exception:
            pass


def report_done(out_dir: Path, verified: int | None = None) -> None:
    media = collect_media(out_dir)
    log("")
    log("=" * 64)
    log(f"[完成] 落盘 {len(media)} 个媒体文件")
    for p in media[:10]:
        log(f"    {p.name}  ({p.stat().st_size} 字节)")
    if len(media) > 10:
        log(f"    ... 其余 {len(media) - 10} 个")
    log(f"[产物] {out_dir}")
    log("=" * 64)


def run_profile(args, loader: Instaloader, username: str, out_dir: Path, login_as: str | None) -> int:
    with account_mutex(username):
        profile = Profile.from_username(loader.context, username)
        log(f"[主页] {username}｜粉丝 {profile.followers}｜帖子 {profile.mediacount}")

        posts, mode = select_posts(profile, args.count, args.days)
        log(f"[模式] {mode}｜命中 {len(posts)} 个帖子")

        if not posts:
            log("[结果] 没有符合筛选条件的帖子，未下载任何内容。")
            return 0

        for i, post in enumerate(posts, 1):
            when = _aware(post.date_utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
            n_img, n_vid = expected_media(post, args.videos_only, args.images_only)
            kind = post.typename.replace("Graph", "")
            log(f"  [{i}/{len(posts)}] {when}  {kind:8s} "
                f"图{n_img}/视频{n_vid}  {post.shortcode}  https://www.instagram.com/p/{post.shortcode}/")

        if args.dry_run:
            log("[dry-run] 枚举完成，未下载。去掉 --dry-run 即可实跑。")
            return 0

        done = load_state(out_dir, args.resume)
        todo = [p for p in posts if p.shortcode not in done]
        skipped = len(posts) - len(todo)
        if skipped:
            log(f"[续传] 跳过已完成 {skipped} 个，待处理 {len(todo)} 个")

        ok_count = corrupt = 0
        for i, post in enumerate(todo, 1):
            base_name = f"{post.date_utc:%Y-%m-%d_%H-%M-%S}_{post.shortcode}"
            log(f"[下载 {i}/{len(todo)}] {post.shortcode} ...")
            try:
                loader.download_post(post, target=username.lower())
            except Exception as exc:
                log(f"    ! 下载异常：{redact(str(exc))}")
            if review_post(out_dir, post, args, base_name):
                ok_count += 1
            else:
                corrupt += 1
            done.add(post.shortcode)
            save_state(out_dir, done, args.resume)
            if i < len(todo):
                _rest(args.sleep)

        if args.stories:
            log("[Story] 下载当前 Story ...")
            try:
                loader.download_stories(userids=[profile], fast_update=True)
            except Exception as exc:
                log(f"    ! Story 下载失败：{redact(str(exc))}")
        if args.highlights:
            log("[Highlight] 下载精选 ...")
            try:
                loader.download_highlights(user=profile, fast_update=True)
            except Exception as exc:
                log(f"    ! Highlight 下载失败：{redact(str(exc))}")

        log("")
        log("=" * 64)
        log(f"[完成] 成功 {ok_count} 个，异常 {corrupt} 个")
        log(f"[产物] {out_dir}")
        log("=" * 64)
        return 0 if corrupt == 0 else 2


def review_post(out_dir: Path, post: Post, args, base_name: str) -> bool:
    """校验单帖产物完整性，必要时用 yt-dlp 兜底视频。返回是否全部通过。"""
    n_img, n_vid = expected_media(post, args.videos_only, args.images_only)
    pattern = re.compile(rf"^{re.escape(base_name)}(_\d+)?\.(jpg|png|webp|mp4)$", re.I)
    found = sorted(p for p in out_dir.iterdir() if pattern.match(p.name))

    imgs = [p for p in found if p.suffix.lower() in (".jpg", ".png", ".webp")]
    vids = [p for p in found if p.suffix.lower() == ".mp4"]

    problems: list[str] = []
    for p in imgs:
        ok, why = verify_image(p)
        if not ok:
            problems.append(f"{p.name}: {why}")
    for p in vids:
        ok, why = verify_video(p)
        if not ok:
            problems.append(f"{p.name}: {why}")
        else:
            log(f"    视频 {p.name} → {why}")

    if n_vid > 0 and len(vids) < n_vid and not args.no_yt_dlp_fallback:
        url = f"https://www.instagram.com/p/{post.shortcode}/"
        ok, why = ytdlp_fallback(url, out_dir, base_name, args)
        log(f"    视频缺失（期望 {n_vid}，实得 {len(vids)}）→ {why}")
        if ok:
            for p in sorted(out_dir.glob(f"{base_name}_yt.*")):
                v, msg = verify_video(p)
                log(f"    兜底产物 {p.name} → {'OK' if v else 'FAIL'} {msg}")
                if not v:
                    problems.append(f"{p.name}: 兜底产物校验失败")
        else:
            problems.append(f"视频缺失且兜底失败：期望 {n_vid}，实得 {len(vids)}")

    if not imgs and n_img > 0 and not args.videos_only:
        problems.append(f"图片缺失：期望 {n_img}，实得 0")

    for p in out_dir.glob("*.part"):
        problems.append(f"残留未完成文件 {p.name}")

    if problems:
        for msg in problems:
            log(f"    ! {msg}")
        return False
    return True


def _rest(seconds: float) -> None:
    """帖子之间的随机退避，降低被风控概率。"""
    time.sleep(seconds * random.uniform(0.8, 1.2))


def _fail(msg: str) -> int:
    log(f"\n[失败] {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
