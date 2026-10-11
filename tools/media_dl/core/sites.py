"""站点识别：URL → 站点 / 引擎优先级 / 输出目录名。

三层判定（前两层零网络请求）：
  1. HOST_RULES 精确或后缀匹配
  2. gallery_dl.extractor.find(url) 本地离线探测
  3. 兜底启发式（视频站 vs 图库）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class SiteRule:
    name: str
    hosts: tuple[str, ...]
    engines: tuple[str, ...] = ("gallery-dl", "yt-dlp")
    cookie_domain: str = ""
    filename_pattern: str = "{id}.{extension}"
    need_cookie: bool = False

    def out_name(self, url: str) -> str:
        """从 URL 推导输出目录名，如 instagram_ayano_fj。"""
        path = urlparse(url if "://" in url else "https://" + url).path.strip("/")
        seg = [s for s in path.split("/") if s and not s.startswith("?")]
        tail = seg[0] if seg else "download"
        tail = re.sub(r"[^A-Za-z0-9._-]", "_", tail)[:40] or "download"
        return f"{self.name}_{tail}"


# 视频平台优先 yt-dlp；图库/社交优先 gallery-dl
SITES: list[SiteRule] = [
    SiteRule("instagram", ("instagram.com",), ("gallery-dl", "yt-dlp", "instaloader"),
             cookie_domain=".instagram.com",
             filename_pattern="{date:%Y-%m-%d_%H-%M-%S}_{shortcode}_{num}.{extension}",
             need_cookie=True),
    SiteRule("tiktok", ("tiktok.com",), ("yt-dlp", "gallery-dl")),
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
        u = url if "://" in url else "https://" + url
        try:
            return (urlparse(u).netloc or "").lower().split(":")[0]
        except Exception:
            return ""

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
