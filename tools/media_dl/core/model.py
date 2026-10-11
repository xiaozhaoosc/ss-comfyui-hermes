"""数据模型：JobSpec / Job / Progress / Artifact / EventBus。"""
from __future__ import annotations

import queue
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Progress:
    done: int = 0            # 已完成条目数（来自 Archive.count，唯一可信源）
    total: int = 0           # 0 = 未知 → UI 显示不确定态
    percent: float = 0.0
    current_item: str = ""
    byte_percent: float = 0.0
    skipped: int = 0

    def as_dict(self) -> dict[str, Any]:
        total = self.total or 0
        pct = (self.done / total * 100.0) if total else 0.0
        return {
            "done": self.done, "total": total, "percent": round(pct, 1),
            "current_item": self.current_item,
            "byte_percent": round(self.byte_percent, 1),
            "skipped": self.skipped,
        }


@dataclass
class Artifact:
    name: str
    size: int
    path: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "size": self.size, "path": self.path}


@dataclass
class JobSpec:
    url: str = ""
    out_dir: str | None = None
    engine: str = "auto"                 # auto | gallery-dl | yt-dlp | instaloader
    media_filter: str = "all"            # all | video | image
    item_range: str | None = None        # "1-20"
    days: int | None = None              # 最近 N 天
    simulate: bool = False               # 只枚举不下载
    sleep_request: float = 3.0
    cookies_text: str | None = None      # 粘贴的 cookies.txt 全文（仅内存）
    cookies_file: str | None = None      # 已存在的 cookies 文件路径
    use_cdp: bool = True                 # 默认优先从 Chrome 9222 取
    cdp_port: int = 9222
    total_hint: int | None = None
    timeout: int = 1800


@dataclass
class Job:
    id: str
    spec: JobSpec
    state: JobState = JobState.PENDING
    progress: Progress = field(default_factory=Progress)
    log: deque = field(default_factory=lambda: deque(maxlen=2000))
    artifacts: list[Artifact] = field(default_factory=list)
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    ended_at: float | None = None
    out_dir: str = ""
    _cancel: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "url": self.spec.url,
            "engine": self.spec.engine,
            "out_dir": self.out_dir,
            "progress": self.progress.as_dict(),
            "artifacts": [a.as_dict() for a in self.artifacts],
            "error": self.error,
            "log_tail": list(self.log)[-50:],
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


class EventBus:
    """线程安全的发布-订阅：每个订阅者一个 Queue。"""

    def __init__(self) -> None:
        self._subs: dict[str, list[queue.Queue]] = {}
        self._lock = threading.Lock()
        self._history: dict[str, deque] = {}

    def subscribe(self, job_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=5000)
        with self._lock:
            self._subs.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: queue.Queue) -> None:
        with self._lock:
            subs = self._subs.get(job_id, [])
            if q in subs:
                subs.remove(q)

    def publish(self, job_id: str, event: dict[str, Any]) -> None:
        event.setdefault("ts", time.time())
        with self._lock:
            hist = self._history.setdefault(job_id, deque(maxlen=500))
            hist.append(event)
            subs = list(self._subs.get(job_id, []))
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    def history(self, job_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history.get(job_id, deque()))


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]
