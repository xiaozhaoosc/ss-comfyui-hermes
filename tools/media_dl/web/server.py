"""网页端：标准库 http.server + SSE，零新增依赖。

默认只监听 127.0.0.1:8765。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"

sys.path.insert(0, str(HERE.parent.parent))  # repo/tools
sys.path.insert(0, str(HERE.parent))         # repo/tools/media_dl -> 可 import core

from media_dl.core.jobs import JobManager  # noqa: E402
from media_dl.core.model import JobSpec, JobState  # noqa: E402
from media_dl.core.sites import ADAPTER  # noqa: E402

MGR = JobManager()
REDACT_KEYS = re.compile(r"(sessionid|csrftoken|ds_user_id|password|token)=([^;\s]+)", re.I)


def _redact(text: str) -> str:
    return REDACT_KEYS.sub(r"\1=<redacted>", str(text))


def _json(h, obj: dict, code: int = 200) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 静音默认日志
        pass

    # ---------------- GET ----------------
    def do_GET(self) -> None:
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)

        if path in ("/", "/index.html"):
            self._serve_file(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path == "/api/engines":
            self._engines()
            return
        if path == "/api/cdp":
            # 可选功能：只探测 9222，不改变任何行为
            from core.cookies import probe_cdp
            port = int((qs.get("port") or ["9222"])[0])
            user = (qs.get("user") or [""])[0]
            _json(self, probe_cdp(port, user))
            return
        if path == "/api/jobs":
            _json(self, {"jobs": MGR.list_jobs()})
            return
        m = re.fullmatch(r"/api/jobs/([0-9a-f]+)", path)
        if m:
            job = MGR.get(m.group(1))
            _json(self, job.snapshot() if job else {"error": "not found"},
                  200 if job else 404)
            return
        m = re.fullmatch(r"/api/jobs/([0-9a-f]+)/events", path)
        if m:
            self._sse(m.group(1))
            return
        m = re.fullmatch(r"/api/files/([0-9a-f]+)", path)
        if m:
            self._download(m.group(1), (qs.get("name") or [""])[0])
            return
        _json(self, {"error": "not found"}, 404)

    # ---------------- POST ----------------
    def do_POST(self) -> None:
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            data = {}

        if u.path == "/api/probe":
            url = data.get("url", "")
            try:
                d = ADAPTER.resolve(url)
                _json(self, d.as_dict())
            except Exception as exc:
                _json(self, {"error": str(exc)}, 400)
            return

        if u.path == "/api/jobs":
            spec = JobSpec(
                url=data.get("url", ""),
                out_dir=data.get("out_dir") or None,
                engine=data.get("engine", "auto"),
                media_filter=data.get("media", "all"),
                item_range=(f"1-{data['count']}" if data.get("count") else data.get("item_range")),
                days=data.get("days"),
                simulate=bool(data.get("simulate")),
                sleep_request=float(data.get("sleep", 3.0)),
                cookies_text=data.get("cookies_text") or None,
                cookies_file=data.get("cookies_file") or None,
                use_cdp=bool(data.get("use_cdp", True)),
                cdp_port=int(data.get("cdp_port", 9222)),
                total_hint=data.get("total_hint"),
            )
            if not spec.url:
                _json(self, {"error": "url 为空"}, 400)
                return
            job = MGR.submit(spec)
            _json(self, {"job_id": job.id})
            return

        m = re.fullmatch(r"/api/jobs/([0-9a-f]+)/cancel", u.path)
        if m:
            _json(self, {"ok": MGR.cancel(m.group(1))})
            return

        _json(self, {"error": "not found"}, 404)

    # ---------------- 具体实现 ----------------
    def _serve_file(self, path: Path, ctype: str) -> None:
        if not path.is_file():
            _json(self, {"error": "static missing"}, 404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _engines(self) -> None:
        from media_dl.core.engines import ENGINES
        info = {}
        for name, eng in ENGINES.items():
            ok, why = eng.available()
            info[name] = {"available": ok, "detail": _redact(why)}
        from media_dl.core.engines import default_ytdlp_exe
        _json(self, {"engines": info, "yt_dlp_exe": str(default_ytdlp_exe())})

    def _sse(self, job_id: str) -> None:
        job = MGR.get(job_id)
        if not job:
            _json(self, {"error": "not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = MGR.events(job_id)
        last_ping = time.time()
        try:
            while True:
                try:
                    ev = q.get(timeout=1.0)
                except Exception:
                    if job.state in (JobState.DONE, JobState.FAILED, JobState.CANCELLED):
                        break
                    if time.time() - last_ping > 15:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                        last_ping = time.time()
                    continue
                payload = json.dumps(_redact_json(ev), ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                last_ping = time.time()
                if ev.get("type") in ("done", "failed", "cancelled"):
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            MGR.bus.unsubscribe(job_id, q)

    def _download(self, job_id: str, name: str) -> None:
        job = MGR.get(job_id)
        if not job or not job.out_dir:
            _json(self, {"error": "not found"}, 404)
            return
        out = Path(job.out_dir).resolve()
        target = (out / name).resolve()
        # 目录穿越防护：必须在 out_dir 之下
        if not str(target).startswith(str(out)):
            _json(self, {"error": "invalid path"}, 403)
            return
        if not target.is_file():
            _json(self, {"error": "file missing"}, 404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition",
                         f'attachment; filename="{target.name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _redact_json(obj):
    if isinstance(obj, dict):
        return {k: _redact_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_json(v) for v in obj]
    if isinstance(obj, str):
        return _redact(obj)
    return obj


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="media_dl web")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv or [])

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"media_dl 网页端已启动： http://{args.host}:{args.port}")
    print("Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
