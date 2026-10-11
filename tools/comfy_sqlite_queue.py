#!/usr/bin/env python3
"""ComfyUI SQLite 外部任务状态与资产管理模块 (断点续跑 & 灾备系统)

功能:
  1. 任务落库先于执行：所有 Prompt/工作流在提交前先落库 (status='pending')，断电重启不丢失。
  2. 断点续跑恢复：ComfyUI 崩溃或系统关机重启后，自动从 SQLite 恢复未完成任务继续执行。
  3. 资产与产物归档：自动抓取执行产物 (图片/视频)，记录到 assets 表，符合 output/YYYY-MM-DD/ 规范。
  4. CLI 运维工具：支持状态查询、一键续跑、重试失败任务、资产导出。

命令行示例:
  python tools/comfy_sqlite_queue.py status                 # 查看当前任务统计
  python tools/comfy_sqlite_queue.py resume                 # 恢复所有未完成的任务
  python tools/comfy_sqlite_queue.py retry-failed           # 重置失败任务为 pending 并重跑
  python tools/comfy_sqlite_queue.py list-assets            # 查看已登记的资产列表
  python tools/comfy_sqlite_queue.py enqueue <wf.json>      # 将某个 workflow 登记入库
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, Any, List

# Windows 控制台编码安全处理
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 数据库存储路径（默认存放在 user 目录中）
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user")
DB_PATH = os.path.join(DB_DIR, "task_queue.db")
COMFY_BASE_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")


def get_db_connection() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 启用 WAL 模式提高并发与抗崩溃能力
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    """初始化 SQLite 任务表与资产表"""
    conn = get_db_connection()
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            batch_name TEXT DEFAULT '',
            prompt_id TEXT,
            status TEXT DEFAULT 'pending', -- pending, submitted, running, completed, failed
            prompt_payload TEXT NOT NULL,  -- JSON 格式的 ComfyUI API Prompt
            extra_meta TEXT,               -- 自定义元数据 (如分镜编号、剧集等)
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            error_msg TEXT
        );
        """)
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        """)
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_batch ON tasks(batch_name);
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            prompt_id TEXT,
            batch_name TEXT DEFAULT '',
            asset_type TEXT,                -- image, video, audio, other
            subfolder TEXT,
            filename TEXT NOT NULL,
            abs_path TEXT NOT NULL,
            meta_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id)
        );
        """)
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_assets_task ON assets(task_id);
        """)
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at);
        """)
    conn.close()


def enqueue_task(prompt_dict: Dict[str, Any], batch_name: str = "", extra_meta: Optional[Dict] = None) -> str:
    """【核心落库】在向 ComfyUI 提交前，先将任务存入 SQLite"""
    init_db()
    task_id = str(uuid.uuid4())
    conn = get_db_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO tasks (task_id, batch_name, status, prompt_payload, extra_meta, created_at)
            VALUES (?, ?, 'pending', ?, ?, ?)
            """,
            (
                task_id,
                batch_name,
                json.dumps(prompt_dict, ensure_ascii=False),
                json.dumps(extra_meta or {}, ensure_ascii=False),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
    conn.close()
    return task_id


def is_comfy_healthy(base_url: str = COMFY_BASE_URL) -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/system_stats", headers={"User-Agent": "comfy-queue-guard"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_until_comfy_ready(base_url: str = COMFY_BASE_URL, max_wait: int = 300) -> bool:
    print(f"[*] 检查 ComfyUI 服务健康状态 ({base_url})...")
    start = time.time()
    while time.time() - start < max_wait:
        if is_comfy_healthy(base_url):
            print(f"[OK] ComfyUI 已在线就绪")
            return True
        time.sleep(3)
    return False


def _submit_to_comfy(prompt_dict: Dict[str, Any], base_url: str = COMFY_BASE_URL) -> str:
    payload = {"prompt": prompt_dict, "client_id": str(uuid.uuid4())}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["prompt_id"]


def _poll_history(prompt_id: str, base_url: str = COMFY_BASE_URL, timeout: int = 3600) -> Optional[Dict[str, Any]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = f"{base_url}/history/{prompt_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "comfy-queue-guard"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if prompt_id in data:
                    item = data[prompt_id]
                    status_dict = item.get("status", {})
                    if status_dict.get("completed", False):
                        return item
                    if status_dict.get("status_str") == "error":
                        raise RuntimeError(f"ComfyUI 执行报错: {status_dict.get('messages', [])}")
        except urllib.error.URLError as e:
            # ComfyUI 可能在渲染过程中短暂无响应或重启
            pass
        time.sleep(5)
    return None


def _record_assets(conn: sqlite3.Connection, task_id: str, prompt_id: str, batch_name: str, history_item: Dict[str, Any]):
    outputs = history_item.get("outputs", {})
    # 查找 ComfyUI 根目录以及 output 根目录
    comfy_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_root = os.path.join(comfy_root, "output")

    for node_id, node_out in outputs.items():
        for key, val_list in node_out.items():
            if not isinstance(val_list, list):
                continue
            for item in val_list:
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename")
                subfolder = item.get("subfolder", "")
                item_type = item.get("type", "output")
                if not filename:
                    continue

                abs_path = os.path.join(output_root, subfolder, filename) if item_type == "output" else filename
                ext = os.path.splitext(filename)[1].lower()
                if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    asset_type = "image"
                elif ext in [".mp4", ".mov", ".webm", ".avi", ".gif"]:
                    asset_type = "video"
                elif ext in [".mp3", ".wav", ".flac", ".ogg"]:
                    asset_type = "audio"
                else:
                    asset_type = "other"

                conn.execute(
                    """
                    INSERT INTO assets (task_id, prompt_id, batch_name, asset_type, subfolder, filename, abs_path, meta_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        prompt_id,
                        batch_name,
                        asset_type,
                        subfolder,
                        filename,
                        abs_path,
                        json.dumps(item, ensure_ascii=False),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                )


def run_single_task(task_row: sqlite3.Row, base_url: str = COMFY_BASE_URL, timeout: int = 3600) -> bool:
    """执行单个任务并全程更新 SQLite 状态"""
    task_id = task_row["task_id"]
    batch_name = task_row["batch_name"]
    prompt_payload = json.loads(task_row["prompt_payload"])
    conn = get_db_connection()

    try:
        # 1. 提交到 ComfyUI
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt_id = _submit_to_comfy(prompt_payload, base_url)
        with conn:
            conn.execute(
                """
                UPDATE tasks
                SET prompt_id = ?, status = 'running', started_at = ?
                WHERE task_id = ?
                """,
                (prompt_id, now_str, task_id)
            )
        print(f"[*] 任务 {task_id[:8]} 已提交，Prompt ID: {prompt_id}")

        # 2. 等待执行完成
        history_item = _poll_history(prompt_id, base_url, timeout=timeout)
        if not history_item:
            raise TimeoutError(f"任务等待超时 ({timeout}s)")

        # 3. 产物落库 & 标记成功
        fin_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            _record_assets(conn, task_id, prompt_id, batch_name, history_item)
            conn.execute(
                """
                UPDATE tasks
                SET status = 'completed', finished_at = ?, error_msg = NULL
                WHERE task_id = ?
                """,
                (fin_str, task_id)
            )
        print(f"[OK] 任务 {task_id[:8]} (PID: {prompt_id}) 顺利完成并记录资产！")
        return True

    except Exception as e:
        err_msg = str(e)
        fin_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'failed', retry_count = retry_count + 1, finished_at = ?, error_msg = ?
                WHERE task_id = ?
                """,
                (fin_str, err_msg, task_id)
            )
        print(f"[FAIL] 任务 {task_id[:8]} 执行失败: {err_msg}")
        return False
    finally:
        conn.close()


def resume_queue(base_url: str = COMFY_BASE_URL, batch_name: Optional[str] = None, max_tasks: Optional[int] = None):
    """【断点续跑】处理所有 pending 或中断的 running 任务"""
    init_db()
    if not wait_until_comfy_ready(base_url):
        print("[!] 无法连接到 ComfyUI 实例，退出。")
        return

    conn = get_db_connection()
    # 先将之前因进程异常退出的 'running' 任务恢复为 'pending'
    with conn:
        conn.execute("UPDATE tasks SET status = 'pending' WHERE status = 'running';")

    query = "SELECT * FROM tasks WHERE status = 'pending'"
    params = []
    if batch_name:
        query += " AND batch_name = ?"
        params.append(batch_name)
    query += " ORDER BY created_at ASC"
    if max_tasks:
        query += f" LIMIT {int(max_tasks)}"

    tasks = conn.execute(query, params).fetchall()
    conn.close()

    total = len(tasks)
    print(f"[*] 发现待处理/待恢复任务: {total} 个")
    if total == 0:
        return

    success_cnt = 0
    fail_cnt = 0
    for idx, t in enumerate(tasks, 1):
        print(f"\n--- [{idx}/{total}] 正在处理任务: {t['task_id']} (Batch: {t['batch_name'] or 'default'}) ---")
        ok = run_single_task(t, base_url=base_url)
        if ok:
            success_cnt += 1
        else:
            fail_cnt += 1

    print(f"\n==========================================")
    print(f"[*] 批次执行结束: 成功 {success_cnt} 个，失败 {fail_cnt} 个")
    print(f"==========================================")


def print_status():
    """打印当前队列的统计情况"""
    init_db()
    conn = get_db_connection()
    stats = conn.execute("""
        SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status
    """).fetchall()
    total_assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    conn.close()

    print("\n========== ComfyUI SQLite 任务统计 ==========")
    if not stats:
        print("暂无任务记录。")
    else:
        for row in stats:
            print(f"  - 状态 [{row['status']}]: {row['cnt']} 个")
    print(f"  - 登记资产总数: {total_assets} 个")
    print(f"  - 数据库文件: {DB_PATH}")
    print("=============================================\n")


def print_assets(limit: int = 20):
    """查看最新登记的资产"""
    init_db()
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, asset_type, filename, abs_path, created_at
        FROM assets
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    conn.close()

    print(f"\n========== 最近登记资产 (前 {limit} 条) ==========")
    if not rows:
        print("暂无资产记录。")
    else:
        for r in rows:
            print(f"[{r['created_at']}] [{r['asset_type']}] {r['filename']} -> {r['abs_path']}")
    print("==================================================\n")


def backfill_assets(root_dir: Optional[str] = None, batch_prefix: str = "backfill") -> None:
    """扫描 output/ 目录，把未登记的存量媒体文件补录进 assets 表（幂等，可重复执行）。

    每个顶层子目录会创建一个 batch_name 为 {batch_prefix}_{目录名} 的占位任务，
    产物挂在该任务下，便于后续按批次 purge 清理。
    """
    init_db()
    comfy_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_root = root_dir or os.path.join(comfy_root, "output")
    if not os.path.isdir(output_root):
        print(f"[!] 目录不存在: {output_root}")
        return

    ext_map = {}
    for t, exts in [
        ("image", [".png", ".jpg", ".jpeg", ".webp"]),
        ("video", [".mp4", ".mov", ".webm", ".avi", ".gif"]),
        ("audio", [".mp3", ".wav", ".flac", ".ogg"]),
    ]:
        for e in exts:
            ext_map[e] = t

    conn = get_db_connection()
    registered = conn.execute("SELECT DISTINCT abs_path FROM assets").fetchall()
    known_paths = {r["abs_path"] for r in registered}
    print(f"[*] 已有资产记录 {len(known_paths)} 条，开始扫描 {output_root} ...")

    total_new = 0
    for dirpath, dirnames, filenames in os.walk(output_root):
        rel_dir = os.path.relpath(dirpath, output_root)
        top_dir = rel_dir.split(os.sep)[0]
        batch_name = f"{batch_prefix}_{top_dir}" if top_dir != "." else batch_prefix

        placeholders = conn.execute(
            "SELECT task_id FROM tasks WHERE batch_name = ? AND prompt_payload = '{}' LIMIT 1",
            (batch_name,),
        ).fetchall()
        if placeholders:
            task_id = placeholders[0]["task_id"]
        else:
            task_id = str(uuid.uuid4())
            with conn:
                conn.execute(
                    """
                    INSERT INTO tasks (task_id, batch_name, status, prompt_payload, extra_meta, created_at)
                    VALUES (?, ?, 'completed', '{}', '{"source": "backfill_placeholder"}', ?)
                    """,
                    (task_id, batch_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )

        batch_new = 0
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            asset_type = ext_map.get(ext)
            if not asset_type:
                continue
            abs_path = os.path.abspath(os.path.join(dirpath, fn))
            if abs_path in known_paths:
                continue
            known_paths.add(abs_path)
            subfolder = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
            mtime = datetime.fromtimestamp(os.path.getmtime(abs_path)).strftime("%Y-%m-%d %H:%M:%S")
            with conn:
                conn.execute(
                    """
                    INSERT INTO assets (task_id, prompt_id, batch_name, asset_type, subfolder, filename, abs_path, meta_json, created_at)
                    VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        batch_name,
                        asset_type,
                        subfolder,
                        fn,
                        abs_path,
                        json.dumps({"bytes": os.path.getsize(abs_path), "backfill": True}, ensure_ascii=False),
                        mtime,
                    ),
                )
            batch_new += 1

        if batch_new:
            print(f"  [+] {batch_name}: 补录 {batch_new} 个")
            total_new += batch_new

    conn.close()
    print(f"\n[OK] 回填完成，共新登记 {total_new} 个资产。")


def retry_failed():
    """将失败的任务重置为 pending 以便重新执行"""
    init_db()
    conn = get_db_connection()
    with conn:
        cur = conn.execute("UPDATE tasks SET status = 'pending', error_msg = NULL WHERE status = 'failed'")
        affected = cur.rowcount
    conn.close()
    print(f"[OK] 已重置 {affected} 个失败任务为 pending 状态。")


def purge_tasks(batch_name: Optional[str] = None, status: Optional[str] = None):
    """清理指定批次或指定状态的任务"""
    init_db()
    conn = get_db_connection()
    with conn:
        q = "DELETE FROM tasks WHERE 1=1"
        params = []
        if batch_name:
            q += " AND batch_name = ?"
            params.append(batch_name)
        if status:
            q += " AND status = ?"
            params.append(status)
        cur = conn.execute(q, params)
        deleted = cur.rowcount
    conn.close()
    print(f"[OK] 已清理 {deleted} 条任务记录。")


def main():
    parser = argparse.ArgumentParser(description="ComfyUI SQLite 任务队列与资产持久化管理")
    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="查看任务与资产统计")

    # resume
    p_resume = subparsers.add_parser("resume", help="恢复执行未完成的任务")
    p_resume.add_argument("--batch", type=str, default=None, help="指定批次名称")
    p_resume.add_argument("--limit", type=int, default=None, help="最大执行任务数")
    p_resume.add_argument("--url", type=str, default=COMFY_BASE_URL, help="ComfyUI 基础地址")

    # retry-failed
    subparsers.add_parser("retry-failed", help="重置失败任务为 pending 并可继续 resume")

    # purge
    p_purge = subparsers.add_parser("purge", help="清理任务记录")
    p_purge.add_argument("--batch", type=str, default=None, help="指定批次名称")
    p_purge.add_argument("--status", type=str, default=None, help="指定状态 (pending/completed/failed)")

    # list-assets
    p_assets = subparsers.add_parser("list-assets", help="列出最近生成的资产")
    p_assets.add_argument("--limit", type=int, default=20, help="显示数量")

    # backfill
    p_bf = subparsers.add_parser("backfill", help="扫描 output/ 目录补录存量资产（幂等）")
    p_bf.add_argument("--root", type=str, default=None, help="指定扫描根目录（默认 output/）")
    p_bf.add_argument("--batch-prefix", type=str, default="backfill", help="占位批次名前缀")

    # enqueue
    p_enqueue = subparsers.add_parser("enqueue", help="将 workflow JSON 文件或 API Prompt 入库")
    p_enqueue.add_argument("file", help="JSON 文件路径")
    p_enqueue.add_argument("--batch", type=str, default="", help="批次名称")

    args = parser.parse_args()

    if args.command == "status":
        print_status()
    elif args.command == "resume":
        resume_queue(base_url=args.url, batch_name=args.batch, max_tasks=args.limit)
    elif args.command == "retry-failed":
        retry_failed()
    elif args.command == "purge":
        purge_tasks(batch_name=args.batch, status=args.status)
    elif args.command == "list-assets":
        print_assets(limit=args.limit)
    elif args.command == "backfill":
        backfill_assets(root_dir=args.root, batch_prefix=args.batch_prefix)
    elif args.command == "enqueue":
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        tid = enqueue_task(data, batch_name=args.batch)
        print(f"[OK] 任务已落库入队，Task ID: {tid}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
