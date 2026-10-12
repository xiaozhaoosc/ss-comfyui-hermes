"""引擎抽象：命令构造 + stdout 解析成进度事件。

GalleryDl：图库 / 社交（pixiv / reddit / 微博 / 小红书 / Instagram / X）
YtDlp    ：视频平台（YouTube / B站 / Vimeo / TikTok / 抖音）
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

RE_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
RE_YTDLP_ITEM = re.compile(r"Downloading item (\d+) of (\d+)")
RE_YTDLP_PCT = re.compile(r"\[download\]\s+(\d{1,3}(?:\.\d+)?)%")
RE_YTDLP_DST = re.compile(r"^\[download\]\s+Destination:\s+(.+)$")
RE_YTDLP_SKIP = re.compile(r"already been downloaded|already in archive", re.I)
# 抖音图文笔记：yt-dlp 的 Douyin 只认 /video/，/note/ 必须走 CDP
RE_DOUYIN_NOTE = re.compile(r"douyin\.com/(?:note|slides)/\d+")


@dataclass
class EngineCtx:
    out_dir: Path
    cookie_file: Path | None
    archive_sqlite: Path
    archive_text: Path
    python_exe: str = sys.executable
    yt_dlp_exe: Path | None = None
    filename_pattern: str = "{id}.{extension}"
    ytdlp_template: str = ""      # 站点定制的 yt-dlp 输出模板，留空用默认
    ytdlp_format: str = ""        # 站点定制的 yt-dlp 格式选择器，留空用默认


CORE_DIR = Path(__file__).resolve().parent


class Engine:
    name = "base"

    def available(self, url: str = "") -> tuple[bool, str]:
        """url 可选：个别引擎（如 douyin-cdp）只对特定 URL 形态可用。"""
        return False, "未实现"

    def build_cmd(self, url: str, spec, ctx: EngineCtx) -> list[str]:  # pragma: no cover
        raise NotImplementedError

    @staticmethod
    def parse_line(line: str) -> dict:
        return {"type": "log", "text": line}


class GalleryDlEngine(Engine):
    name = "gallery-dl"

    def available(self, url: str = "") -> tuple[bool, str]:
        try:
            import importlib.util
            return (True, "gallery-dl 已安装") if importlib.util.find_spec("gallery_dl") else (False, "未安装")
        except Exception:
            return False, "未安装"

    def build_cmd(self, url: str, spec, ctx: EngineCtx) -> list[str]:
        cmd = [
            ctx.python_exe, "-m", "gallery_dl",
            "--sleep-request", str(max(spec.sleep_request, 3.0)),
            "-D", str(ctx.out_dir),
            "-f", ctx.filename_pattern,
        ]
        if ctx.cookie_file:
            cmd += ["--cookies", str(ctx.cookie_file)]
        if not spec.simulate and ctx.archive_sqlite:
            cmd += ["--download-archive", str(ctx.archive_sqlite)]
        if spec.item_range:
            cmd += ["--post-range", spec.item_range.replace(":", "-")]
        if spec.days:
            cutoff = time.time() - spec.days * 86400
            cmd += ["--post-filter", f"date.timestamp() >= {cutoff}"]
        if spec.media_filter == "video":
            cmd += ["--filter", "extension in ('mp4','webm','mov')"]
        elif spec.media_filter == "image":
            cmd += ["--filter", "extension in ('jpg','jpeg','png','webp','gif')"]
        if spec.simulate:
            cmd += ["--simulate"]
        cmd.append(url)
        return cmd

    @staticmethod
    def parse_line(line: str) -> dict:
        clean = RE_ANSI.sub("", line).strip()
        if not clean:
            return {"type": "skip"}
        # gallery-dl 非 TTY 时每行就是一个文件路径（skip / success 同形，故只作"当前项"提示）
        if clean.startswith("["):
            return {"type": "log", "text": clean}
        # --simulate 输出带 "# " 前缀，去掉再当文件名
        return {"type": "item", "current_item": clean.lstrip("#").strip()}


REPO_ROOT = Path(__file__).resolve().parents[3]


def default_ytdlp_exe() -> Path:
    """tools/yt-dlp/yt-dlp.exe（它是独立 exe，不在 PATH 里）。"""
    return REPO_ROOT / "tools" / "yt-dlp" / "yt-dlp.exe"


class YtDlpEngine(Engine):
    name = "yt-dlp"

    @staticmethod
    def _as_module() -> bool:
        """当前解释器里是否有 yt_dlp 模块。

        优先走 `python -m yt_dlp`：仓库自带的 tools/yt-dlp/yt-dlp.exe 是裁剪版，
        没有 DouyinIE（只有 TikTok），抖音 URL 会被回退到 generic 而失败。
        """
        try:
            import importlib.util
            return importlib.util.find_spec("yt_dlp") is not None
        except Exception:
            return False

    def available(self, url: str = "") -> tuple[bool, str]:
        if self._as_module():
            return True, "yt-dlp 模块（python -m yt_dlp，含完整解析器）"
        exe = default_ytdlp_exe()
        if exe.is_file():
            return True, str(exe)
        p = shutil.which("yt-dlp")
        if p:
            return True, p
        return False, f"未找到 yt-dlp（期望 {exe}）"

    def build_cmd(self, url: str, spec, ctx: EngineCtx) -> list[str]:
        if self._as_module():
            cmd = [ctx.python_exe, "-m", "yt_dlp"]
        else:
            cmd = [str(ctx.yt_dlp_exe or default_ytdlp_exe())]
        cmd += [
            url,
            "-o", str(Path(ctx.out_dir) / (ctx.ytdlp_template
                                           or "%(upload_date>%Y-%m-%d)s_%(id)s.%(ext)s")),
            "--no-overwrites", "--retries", "2", "--fragment-retries", "2",
            "--sleep-request", "3", "--no-warnings",
            "-f", "bestvideo*+bestaudio/best", "--merge-output-format", "mp4",
            "--newline",
        ]
        if ctx.cookie_file:
            cmd += ["--cookies", str(ctx.cookie_file)]
        if not spec.simulate and ctx.archive_text:
            cmd += ["--download-archive", str(ctx.archive_text)]
        if spec.item_range:
            cmd += ["--playlist-items", spec.item_range.replace("-", ":")]
        if spec.days:
            from datetime import datetime, timedelta
            cmd += ["--dateafter", (datetime.now() - timedelta(days=spec.days)).strftime("%Y%m%d")]
        if spec.simulate:
            cmd += ["--simulate", "--flat-playlist"]
        return cmd

    @staticmethod
    def parse_line(line: str) -> dict:
        clean = RE_ANSI.sub("", line).strip()
        if not clean:
            return {"type": "skip"}
        m = RE_YTDLP_ITEM.search(clean)
        if m:
            return {"type": "item", "index": int(m.group(1)), "total": int(m.group(2)),
                    "text": clean}
        m = RE_YTDLP_PCT.search(clean)
        if m:
            return {"type": "byte", "byte_percent": float(m.group(1)), "text": clean}
        m = RE_YTDLP_DST.search(clean)
        if m:
            return {"type": "item", "current_item": m.group(1), "text": clean}
        if RE_YTDLP_SKIP.search(clean):
            return {"type": "log", "text": clean, "skipped": True}
        return {"type": "log", "text": clean}


class DouyinNoteEngine(Engine):
    """抖音图文笔记（/note/、/slides/）：接管 9222 已登录页面渲染取直链。"""

    name = "douyin-cdp"

    def available(self, url: str = "") -> tuple[bool, str]:
        if not url or not RE_DOUYIN_NOTE.search(url):
            return False, "非抖音图文笔记（/video/ 交给 yt-dlp）"
        try:
            import importlib.util
            if importlib.util.find_spec("websocket") is None:
                return False, "缺少 websocket-client"
        except Exception:
            return False, "缺少 websocket-client"
        return True, f"CDP 直取（{CORE_DIR / 'douyin_cdp.py'}）"

    def build_cmd(self, url: str, spec, ctx: EngineCtx) -> list[str]:
        cmd = [ctx.python_exe, str(CORE_DIR / "douyin_cdp.py"), url,
               "--out-dir", str(ctx.out_dir), "--port", str(spec.cdp_port)]
        if spec.simulate:
            cmd.append("--simulate")
        return cmd

    @staticmethod
    def parse_line(line: str) -> dict:
        clean = RE_ANSI.sub("", line).strip()
        if not clean:
            return {"type": "skip"}
        if clean.startswith("[save] "):
            return {"type": "item", "current_item": clean[7:].strip(), "text": clean}
        return {"type": "log", "text": clean}


ENGINES = {"gallery-dl": GalleryDlEngine(), "yt-dlp": YtDlpEngine(),
           "douyin-cdp": DouyinNoteEngine()}


def pick_engines(prefer: tuple[str, ...] | list[str], chosen: str = "auto") -> list[Engine]:
    """按优先级返回可用引擎列表。"""
    if chosen in ENGINES:
        return [ENGINES[chosen]]
    ordered = [ENGINES[n] for n in prefer if n in ENGINES]
    for n, e in ENGINES.items():
        if e not in ordered:
            ordered.append(e)
    return ordered
