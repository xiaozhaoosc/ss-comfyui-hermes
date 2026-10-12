"""站点识别：URL → 站点 / 引擎优先级 / 输出目录名。

三层判定（前两层零网络请求）：
  1. HOST_RULES 精确或后缀匹配
  2. gallery_dl.extractor.find(url) 本地离线探测
  3. 兜底启发式（视频站 vs 图库）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse


def host_of(url: str) -> str:
    """URL → 小写主机名（不含端口）。"""
    u = url if "://" in url else "https://" + url
    try:
        return (urlparse(u).netloc or "").lower().split(":")[0]
    except Exception:
        return ""


@dataclass
class SiteRule:
    name: str
    hosts: tuple[str, ...]
    engines: tuple[str, ...] = ("gallery-dl", "yt-dlp")
    cookie_domain: str = ""
    filename_pattern: str = "{id}.{extension}"
    need_cookie: bool = False
    # yt-dlp 专用输出模板；留空则用 engines.py 里的默认模板
    ytdlp_template: str = ""
    # yt-dlp 格式选择器；留空用默认 bestvideo*+bestaudio/best（图文笔记无视频流，需放宽为 best）
    ytdlp_format: str = ""

    def out_name(self, url: str) -> str:
        """从 URL 推导输出目录名，如 instagram_ayano_fj。

        跳过 /watch、/p、/en、/users 这类通用段，尽量取到真正的标识。
        """
        full = url if "://" in url else "https://" + url
        parsed = urlparse(full)
        segs = [s for s in parsed.path.split("/") if s]
        generic = {"watch", "video", "v", "p", "reel", "reels", "tv", "en", "zh",
                   "users", "user", "u", "media", "posts", "stories", "highlights",
                   "photo", "channel", "c", "note", "slides"}
        tail = ""
        for s in segs:
            if s.lower() not in generic:
                tail = s
                break
        if not tail:
            # YouTube 之类：/watch?v=ID，ID 在 query 里
            qid = parse_qs(parsed.query).get("v", [""])[0]
            tail = qid or (segs[-1] if segs else parsed.netloc.split(":")[0])
        # 统一用下划线，保证与 ig_download.py 的产物目录名一致（续传才连得上）
        tail = re.sub(r"[^A-Za-z0-9_-]", "_", tail)[:40] or "download"
        return f"{self.name}_{tail}"


# 视频平台优先 yt-dlp；图库/社交优先 gallery-dl
SITES: list[SiteRule] = [
    SiteRule("instagram", ("instagram.com",), ("gallery-dl", "yt-dlp", "instaloader"),
             cookie_domain=".instagram.com",
             filename_pattern="{date:%Y-%m-%d_%H-%M-%S}_{shortcode}_{num}.{extension}",
             need_cookie=True),
    SiteRule("tiktok", ("tiktok.com",), ("yt-dlp", "gallery-dl")),
    SiteRule("douyin", ("douyin.com",), ("douyin-cdp", "yt-dlp", "gallery-dl"),
             cookie_domain=".douyin.com",
             # 图文笔记同一 id 会有多张图，必须带 autonumber，否则只有第一张能落盘
             ytdlp_template="%(upload_date>%Y-%m-%d)s_%(id)s_%(autonumber)02d.%(ext)s",
             ytdlp_format="best",
             need_cookie=True),
    SiteRule("youtube", ("youtube.com", "youtu.be"), ("yt-dlp",), filename_pattern="%(title)s.%(ext)s"),
    SiteRule("bilibili", ("bilibili.com",), ("yt-dlp", "gallery-dl")),
    SiteRule("twitter", ("twitter.com", "x.com"), ("gallery-dl", "yt-dlp"),
             cookie_domain=".twitter.com", need_cookie=True),
    SiteRule("pixiv", ("pixiv.net",), ("gallery-dl",), cookie_domain=".pixiv.net"),
    SiteRule("reddit", ("reddit.com",), ("gallery-dl", "yt-dlp")),
    SiteRule("weibo", ("weibo.com",), ("gallery-dl",)),
    SiteRule("xiaohongshu", ("xiaohongshu.com",), ("gallery-dl",)),
    SiteRule("danbooru", ("danbooru.donmai.us",), ("gallery-dl",)),
]

VIDEO_HOST_HINTS = (
    "youtube", "youtu.be", "bilibili", "vimeo", "tiktok", "douyin",
    "dailymotion", "twitch", "niconico", "acfun",
)

DEFAULT_RULE = SiteRule("download", (), ("gallery-dl", "yt-dlp"))


@dataclass
class SiteDecision:
    rule: SiteRule
    engines: tuple[str, ...]
    out_name: str
    need_cookie: bool

    def as_dict(self) -> dict:
        return {
            "site": self.rule.name,
            "engines": list(self.engines),
            "out_name": self.out_name,
            "need_cookie": self.need_cookie,
            "cookie_domain": self.rule.cookie_domain,
        }


class SiteAdapter:
    def __init__(self, rules: list[SiteRule] | None = None) -> None:
        self.rules = list(rules or SITES)

    def _host(self, url: str) -> str:
        return host_of(url)

    def resolve(self, url: str) -> SiteDecision:
        host = self._host(url)

        # 1) 规则表匹配
        for rule in self.rules:
            for h in rule.hosts:
                if host == h or host.endswith("." + h):
                    return SiteDecision(rule, rule.engines, rule.out_name(url), rule.need_cookie)

        # 2) gallery-dl 本地离线探测（零网络请求）
        try:
            from gallery_dl import extractor as _gd_extractor
            found = _gd_extractor.find(url)
            if found:
                name = getattr(found, "category", "") or "gallery-dl"
                rule = SiteRule(name or "gallery-dl", (host,), ("gallery-dl", "yt-dlp"))
                return SiteDecision(rule, rule.engines, rule.out_name(url), False)
        except Exception:
            pass

        # 3) 兜底启发式
        engines: tuple[str, ...]
        if any(h in host for h in VIDEO_HOST_HINTS):
            engines = ("yt-dlp", "gallery-dl")
        else:
            engines = ("gallery-dl", "yt-dlp")
        rule = SiteRule("download", (host,), engines)
        return SiteDecision(rule, engines, rule.out_name(url), False)


ADAPTER = SiteAdapter()
