"""任务管理：提交 / 状态 / 取消 / 并发控制 / 事件分发。

进度唯一可信源 = Archive.count()（gallery-dl 的 skip 与 success 输出同形，不能靠 stdout 计数）。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

from .archive import Archive
from .engines import EngineCtx, pick_engines
from .model import Artifact, EventBus as _EventBus, Job, JobSpec, JobState, new_job_id
from .runner import CANCELLED, TIMEOUT, run_stream
from .sites import ADAPTER

REPO_ROOT = Path(__file__).resolve().parents[3]
MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mov", ".m4a"}


def resolve_out_dir(spec: JobSpec, site_name: str, out_name: str) -> Path:
    if spec.out_dir:
        return Path(spec.out_dir).resolve()
    today = datetime.now().strftime("%Y-%m-%d")
    return (REPO_ROOT / "output" / today / out_name).resolve()


def collect_artifacts(out_dir: Path) -> list[Artifact]:
    if not out_dir.is_dir():
        return []
    arts = []
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in MEDIA_EXTS and p.stat().st_size > 0:
            arts.append(Artifact(name=p.name, size=p.stat().st_size, path=str(p)))
    return arts


class JobManager:
    def __init__(self) -> None:
        self.bus = _EventBus()
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._sem = threading.Semaphore(1)      # 全局串行，保护账号不被风控
        self._threads: dict[str, threading.Thread] = {}

    # ---------------- 对外接口 ----------------
    def submit(self, spec: JobSpec) -> Job:
        job = Job(id=new_job_id(), spec=spec)
        with self._lock:
            self.jobs[job.id] = job
        t = threading.Thread(target=self._run, args=(job,), daemon=True)
        self._threads[job.id] = t
        t.start()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return [j.snapshot() for j in sorted(self.jobs.values(), key=lambda x: x.created_at)]

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        job.cancel()
        return True

    def events(self, job_id: str):
        return self.bus.subscribe(job_id)

    # ---------------- 内部 ----------------
    def _emit(self, job: Job, ev: dict) -> None:
        if ev.get("type") == "log":
            job.log.append(ev.get("text", ""))
        self.bus.publish(job.id, ev)

    def _resolve_cookie(self, job: Job) -> tuple[Path | None, bool]:
        """返回 (cookie 文件路径, 是否由我们创建需要删除)。"""
        from . import cookies as ck

        spec = job.spec
        if spec.cookies_file:
            p = Path(spec.cookies_file).expanduser()
            return (p, False) if p.is_file() else (None, False)

        if spec.cookies_text:
            ok, msg, _ = ck.validate_cookies_text(spec.cookies_text)
            if not ok:
                self._emit(job, {"type": "log", "text": f"[cookies] {msg}"})
                return None, False
            domain = ""
            try:
                domain = ADAPTER.resolve(spec.url).rule.cookie_domain
            except Exception:
                pass
            rows = ck.normalize_cookies_text(spec.cookies_text, domain or ".example.com")
            return ck.write_temp_cookies(rows), True

        if spec.use_cdp:
            got = ck.cdp_cookies(spec.cdp_port, spec.url)
            if got:
                self._emit(job, {"type": "log",
                                 "text": f"[cookies] 已从 Chrome {spec.cdp_port} 取得登录态"})
                rows = ck.normalize_cookies_text(
                    "\n".join(f"{k}={v}" for k, v in got.items()),
                    ADAPTER.resolve(spec.url).rule.cookie_domain or ".instagram.com")
                return ck.write_temp_cookies(rows), True
            self._emit(job, {"type": "log",
                             "text": "[cookies] CDP 不可用，转为匿名（可能被限流）"})
        return None, False

    def _run(self, job: Job) -> None:
        from . import cookies as ck

        with self._sem:
            job.state = JobState.RUNNING
            job.started_at = time.time()
            self._emit(job, {"type": "state", "state": "running"})
            cookie_path = None
            ours = False
            try:
                decision = ADAPTER.resolve(job.spec.url)
                out_dir = resolve_out_dir(job.spec, decision.rule.name, decision.out_name)
                out_dir.mkdir(parents=True, exist_ok=True)
                job.out_dir = str(out_dir)
                self._emit(job, {"type": "log",
                                 "text": f"[识别] {decision.rule.name} → 引擎 {list(decision.engines)}"})
                self._emit(job, {"type": "log", "text": f"[输出] {out_dir}"})

                archive = Archive(out_dir, namespace=decision.rule.name)
                migrated = archive.import_legacy()
                if migrated:
                    self._emit(job, {"type": "log",
                                     "text": f"[续传] 已迁移 {migrated} 条历史记录"})
                base_done = archive.count()
                self._emit(job, {"type": "log", "text": f"[续传] 已有 {base_done} 条已下载记录"})

                cookie_path, ours = self._resolve_cookie(job)

                # 进度轮询：done 只认 Archive.count()（skip/success 输出同形，不能数 stdout）
                stop = threading.Event()

                def _poll() -> None:
                    while not stop.wait(0.5):
                        job.progress.done = archive.count()
                        total = job.progress.total or job.spec.total_hint or 0
                        self.bus.publish(job.id, {"type": "progress",
                                                  "done": job.progress.done, "total": total})

                threading.Thread(target=_poll, daemon=True).start()

                ctx = EngineCtx(
                    out_dir=out_dir,
                    cookie_file=cookie_path,
                    archive_sqlite=archive.sqlite_path,
                    archive_text=archive.text_path,
                    yt_dlp_exe=REPO_ROOT / "tools" / "yt-dlp" / "yt-dlp.exe",
                    filename_pattern=decision.rule.filename_pattern,
                )

                engines = pick_engines(decision.engines, job.spec.engine)
                rc = None
                for eng in engines:
                    ok, why = eng.available()
                    if not ok:
                        self._emit(job, {"type": "log", "text": f"[引擎] {eng.name} 不可用：{why}"})
                        continue
                    self._emit(job, {"type": "log", "text": f"[引擎] 使用 {eng.name}"})
                    if eng.name == "yt-dlp":
                        archive.export_to_text()
                    cmd = eng.build_cmd(job.spec.url, job.spec, ctx)

                    def on_line(line: str, _eng=eng) -> None:
                        ev = _eng.parse_line(line)
                        t = ev.get("type")
                        if t == "skip":
                            return
                        if t == "item":
                            job.progress.current_item = ev.get("current_item", "")
                            if ev.get("total"):
                                job.progress.total = ev["total"]
                        elif t == "byte":
                            job.progress.byte_percent = ev.get("byte_percent", 0.0)
                        elif t == "log" and ev.get("skipped"):
                            job.progress.skipped += 1
                        if ev.get("text"):
                            job.log.append(ev["text"])
                        self.bus.publish(job.id, ev)

                    rc = run_stream(cmd, on_line, job._cancel, timeout=job.spec.timeout)
                    if eng.name == "yt-dlp":
                        archive.sync_from_text()

                    if job.cancelled:
                        job.state = JobState.CANCELLED
                        self._emit(job, {"type": "cancelled"})
                        return
                    if archive.count() > base_done or job.spec.simulate:
                        break
                    self._emit(job, {"type": "log",
                                     "text": f"[引擎] {eng.name} 没有新增，降级下一个"})

                job.progress.done = archive.count()
                job.artifacts = collect_artifacts(out_dir)
                job.progress.total = job.progress.total or job.spec.total_hint or 0
                if job.spec.simulate:
                    job.state = JobState.DONE
                    self._emit(job, {"type": "done", "simulated": True})
                elif job.artifacts:
                    job.state = JobState.DONE
                    self._emit(job, {"type": "done"})
                else:
                    job.state = JobState.FAILED
                    job.error = f"未产出任何媒体文件（退出码 {rc}）"
                    self._emit(job, {"type": "failed", "error": job.error})
            except Exception as exc:
                job.state = JobState.FAILED
                job.error = f"{type(exc).__name__}: {exc}"
                self._emit(job, {"type": "failed", "error": job.error})
            finally:
                try:
                    stop.set()
                except Exception:
                    pass
                if cookie_path and ours:
                    ck.drop_temp(cookie_path)
                job.progress.done = archive.count() if "archive" in dir() else job.progress.done
                job.ended_at = time.time()
                self._emit(job, {"type": "state", "state": job.state.value})
