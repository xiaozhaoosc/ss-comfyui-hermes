"""统一续传档案。

gallery-dl 的 --download-archive 原生就是 SQLite（表 archive(entry TEXT PRIMARY KEY)，
check_same_thread=False），我们直接把主库路径给它，就能并发 SELECT COUNT(*) 当进度源。
yt-dlp 只吃纯文本，所以走「跑前导出预热 → 跑后回灌」的桥接。
"""
from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path

CREATE_SQL = "CREATE TABLE IF NOT EXISTS archive (entry TEXT PRIMARY KEY) WITHOUT ROWID"


class Archive:
    def __init__(self, out_dir: Path, namespace: str = "") -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = self.out_dir / "_media_dl_archive.sqlite"
        self.text_path = self.out_dir / "_ytdlp_archive.txt"
        self.namespace = namespace
        self._init_db()

    # ---------------- 基础 ----------------
    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.sqlite_path), timeout=60, check_same_thread=False)

    def _init_db(self) -> None:
        con = self._conn()
        try:
            con.execute(CREATE_SQL)
            con.commit()
        finally:
            con.close()

    def _key(self, key: str) -> str:
        return f"{self.namespace}{key}" if self.namespace else key

    def contains(self, key: str) -> bool:
        con = self._conn()
        try:
            row = con.execute("SELECT 1 FROM archive WHERE entry=?", (self._key(key),)).fetchone()
            return row is not None
        finally:
            con.close()

    def add(self, key: str) -> None:
        con = self._conn()
        try:
            con.execute("INSERT OR IGNORE INTO archive(entry) VALUES(?)", (self._key(key),))
            con.commit()
        finally:
            con.close()

    def count(self) -> int:
        """进度唯一可信源：已完成（含历史）条目数。"""
        try:
            con = self._conn()
            try:
                return int(con.execute("SELECT COUNT(*) FROM archive").fetchone()[0])
            finally:
                con.close()
        except Exception:
            return 0

    def keys(self) -> set[str]:
        con = self._conn()
        try:
            return {r[0] for r in con.execute("SELECT entry FROM archive")}
        finally:
            con.close()

    # ---------------- yt-dlp 文本桥接 ----------------
    def export_to_text(self) -> None:
        """跑 yt-dlp 前：把主库已有 key 写成 "<ns> <id>" 预热其文本 archive。"""
        try:
            keys = self.keys()
            if not keys:
                return
            ns = self.namespace or "download"
            with open(self.text_path, "w", encoding="utf-8") as fh:
                for k in sorted(keys):
                    base = k[len(ns):] if ns and k.startswith(ns) else k
                    fh.write(f"{ns} {base}\n")
        except Exception:
            pass

    def sync_from_text(self) -> int:
        """跑 yt-dlp 后：把新增文本行合并回主库，返回新增条数。"""
        added = 0
        if not self.text_path.is_file():
            return 0
        ns = self.namespace or "download"
        try:
            for line in self.text_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                key = parts[1] if len(parts) == 2 else parts[0]
                if not self.contains(key):
                    self.add(key)
                    added += 1
        except Exception:
            pass
        return added

    # ---------------- 旧资产迁移 ----------------
    def import_legacy(self, legacy_sqlite: Path | None = None,
                      legacy_state_json: Path | None = None) -> int:
        """迁移 ig_download.py 时代的归档，保证「已下过的」不重复下载。"""
        added = 0
        for p in (legacy_sqlite, self.out_dir / "_gallery_archive.txt"):
            if p and Path(p).is_file():
                added += self._import_sqlite(Path(p))
        for p in (legacy_state_json, self.out_dir / "_ig_state.json"):
            if p and Path(p).is_file():
                added += self._import_state_json(Path(p))
        return added

    def _is_sqlite(self, path: Path) -> bool:
        try:
            with open(path, "rb") as fh:
                return fh.read(16).startswith(b"SQLite format 3")
        except Exception:
            return False

    def _import_sqlite(self, path: Path) -> int:
        if not self._is_sqlite(path):
            return 0
        added = 0
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                rows = [r[0] for r in con.execute("SELECT entry FROM archive")]
            finally:
                con.close()
            for entry in rows:
                base = entry
                if self.namespace and entry.startswith(self.namespace):
                    base = entry[len(self.namespace):]
                if not self.contains(base):
                    self.add(base)
                    added += 1
        except Exception:
            pass
        return added

    def _import_state_json(self, path: Path) -> int:
        import json
        added = 0
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            for sc in data.get("done", []):
                if not self.contains(sc):
                    self.add(sc)
                    added += 1
        except Exception:
            pass
        return added
