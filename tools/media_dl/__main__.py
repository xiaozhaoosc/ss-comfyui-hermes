"""media_dl 命令行入口。

    python tools/media_dl <url> [--count N|--days N] [--engine ...] [--simulate]
    python tools/media_dl web [--port 8765]
    python tools/media_dl qt
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 让 core 可 import

from media_dl.core.jobs import JobManager  # noqa: E402
from media_dl.core.model import JobSpec, JobState  # noqa: E402
from media_dl.core.sites import ADAPTER  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="media_dl", description="通用媒体下载器")
    p.add_argument("url", nargs="?", help="目标 URL（主页/帖子/播放列表）")
    p.add_argument("--count", type=int, help="只取最新 N 条（--item-range 的简写）")
    p.add_argument("--days", type=int, help="只取最近 N 天")
    p.add_argument("--engine", default="auto",
                   choices=["auto", "gallery-dl", "yt-dlp"], help="引擎，默认 auto")
    p.add_argument("--media", default="all", choices=["all", "video", "image"])
    p.add_argument("--simulate", action="store_true", help="只枚举不下载")
    p.add_argument("--out-dir", help="输出目录")
    p.add_argument("--sleep", type=float, default=3.0)
    p.add_argument("--total-hint", type=int, help="总条数提示（用于算百分比）")
    p.add_argument("--cookies-file", help="Netscape cookies.txt 路径")
    p.add_argument("--cookies-text-file", help="读取粘贴的 cookies 文本的文件")
    p.add_argument("--no-cdp", action="store_true", help="不尝试 Chrome CDP 取登录态")
    p.add_argument("--cdp-port", type=int, default=9222)
    p.add_argument("--probe-cdp", action="store_true",
                   help="只探测 Chrome 调试端口与 Instagram 登录态，不下载")
    p.add_argument("--probe-port", type=int, default=9222, help="配合 --probe-cdp 指定端口")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--json", action="store_true", help="最后以 JSON 输出结果")
    return p


def run_download(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    if not args.url:
        print("缺少 URL。用法：python tools/media_dl <url> [...]")
        return 2

    cookies_text = None
    if args.cookies_text_file:
        cookies_text = Path(args.cookies_text_file).read_text(encoding="utf-8", errors="replace")

    spec = JobSpec(
        url=args.url,
        out_dir=args.out_dir,
        engine=args.engine,
        media_filter=args.media,
        item_range=(f"1-{args.count}" if args.count else None),
        days=args.days,
        simulate=args.simulate,
        sleep_request=args.sleep,
        cookies_text=cookies_text,
        cookies_file=args.cookies_file,
        use_cdp=not args.no_cdp,
        cdp_port=args.cdp_port,
        total_hint=args.total_hint,
        timeout=args.timeout,
    )

    decision = ADAPTER.resolve(args.url)
    print(f"[识别] 站点={decision.rule.name}  引擎={list(decision.engines)}  "
          f"目录={decision.out_name}")

    mgr = JobManager()
    job = mgr.submit(spec)
    q = mgr.events(job.id)
    last = 0
    while True:
        try:
            ev = q.get(timeout=1.0)
        except Exception:
            if job.state in (JobState.DONE, JobState.FAILED, JobState.CANCELLED):
                break
            continue
        t = ev.get("type")
        if t == "log":
            print(f"    {ev.get('text', '')}")
        elif t == "progress":
            now = time.time()
            if now - last > 1.0:
                print(f"    进度 {ev.get('done')}/{ev.get('total') or '?'}", flush=True)
                last = now
        if t in ("done", "failed", "cancelled"):
            break

    while job.state in (JobState.PENDING, JobState.RUNNING):
        time.sleep(0.3)

    print()
    if args.json:
        print(json.dumps(job.snapshot(), ensure_ascii=False, indent=2))
    else:
        print(f"[状态] {job.state.value}")
        print(f"[已下载] {job.progress.done} 条（本次跳过 {job.progress.skipped} 条已存在）")
        print(f"[产物] {len(job.artifacts)} 个文件 -> {job.out_dir}")
        for a in job.artifacts[:15]:
            print(f"    {a.name}  ({a.size} 字节)")
        if job.error:
            print(f"[错误] {job.error}")
    return 0 if job.state == JobState.DONE else 1


def run_probe(argv: list[str]) -> int:
    """只探测 Chrome 9222，不下载。"""
    ap = argparse.ArgumentParser(prog="media_dl --probe-cdp")
    ap.add_argument("--probe-cdp", action="store_true")
    ap.add_argument("--probe-port", type=int, default=9222)
    ap.add_argument("--probe-user", default="", help="优先匹配含该用户名的 IG 标签页")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    from core.cookies import probe_cdp
    r = probe_cdp(a.probe_port, a.probe_user)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"[9222 探测] 端口 {r['port']}  可达={r['reachable']}  浏览器={r['browser'] or '-'}")
        print(f"  IG 页面 : {r['page_url'] or '未找到'}")
        print(f"  cookie  : {r['cookie_count']} 条")
        print(f"  已登录  : {r['logged_in']}   账号: {r['ig_username'] or '-'}")
        print(f"  结论    : {r['detail']}")
    return 0 if r["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--probe-cdp" in argv:
        return run_probe(argv)
    if argv and argv[0] in ("web", "serve"):
        from media_dl.web.server import main as web_main
        return web_main(argv[1:])
    if argv and argv[0] == "qt":
        from media_dl.qt.app import main as qt_main
        return qt_main(argv[1:])
    return run_download(argv)


if __name__ == "__main__":
    sys.exit(main())
