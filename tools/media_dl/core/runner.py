"""流式执行外部引擎：Popen + 逐行回调 + 可取消 + 杀进程树。

替代 ig_download.py 里的 subprocess.run(capture_output=True) —— 那个是阻塞的，
UI 在任务结束前什么都看不到。
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

CANCELLED = -1
TIMEOUT = -2


def _kill_tree(proc: subprocess.Popen) -> None:
    """连同子进程树一起杀掉，避免留僵尸。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=20)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _pump(proc: subprocess.Popen, on_line: Callable[[str], None]) -> None:
    try:
        for line in proc.stdout:
            on_line(line.rstrip("\r\n"))
    except Exception:
        pass


def run_stream(
    cmd: list[str],
    on_line: Callable[[str], None],
    cancel: threading.Event,
    timeout: int = 1800,
    cwd: str | Path | None = None,
) -> int:
    """流式执行命令，逐行回调；返回退出码（或 CANCELLED / TIMEOUT）。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"          # Windows 中文路径不乱码
    env["PYTHONUNBUFFERED"] = "1"

    kw: dict = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,              # 合并：gallery-dl 的字节进度在 stderr
        text=True, encoding="utf-8", errors="replace",
        bufsize=1, env=env, cwd=str(cwd) if cwd else None,
    )
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kw)
    threading.Thread(target=_pump, args=(proc, on_line), daemon=True).start()

    deadline = time.time() + timeout
    while proc.poll() is None:
        if cancel.wait(0.2):
            _kill_tree(proc)
            return CANCELLED
        if time.time() > deadline:
            _kill_tree(proc)
            return TIMEOUT
    return int(proc.returncode or 0)
