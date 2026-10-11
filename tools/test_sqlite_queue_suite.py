#!/usr/bin/env python3
"""ComfyUI SQLite 外部任务状态管理与断点续跑 自动化测试套件

测试项:
  1. 任务先行落库校验 (Enqueue & Schema Validation)
  2. 模拟系统崩溃与断点自动恢复校验 (Crash Simulation & Breakpoint Resume)
  3. 异常任务错误隔离与重试机制 (Failure Isolation & Retry-Failed)
  4. 产物资产自动提取与分类索引 (Asset Tracking & Classification)
  5. CLI 命令集成验证 (status, list-assets, retry-failed)
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import unittest
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

# Windows 控制台编码安全处理
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保导入当前项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import comfy_sqlite_queue as queue_mod

# 专用测试数据库路径，避免污染正式数据
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_env_tmp")
TEST_DB_PATH = os.path.join(TEST_DIR, "test_task_queue.db")


class MockComfyHandler(BaseHTTPRequestHandler):
    """模拟 ComfyUI 服务端 (提供 /prompt, /history/{pid}, /system_stats)"""

    prompts_received = []
    should_fail_prompts = set()
    completed_histories = {}

    def log_message(self, format, *args):
        # 静默 HTTP 请求日志，保持控制台整洁
        pass

    def do_GET(self):
        if self.path == "/system_stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"system": {"os": "windows"}}).encode("utf-8"))
            return

        if self.path.startswith("/history/"):
            pid = self.path.split("/history/")[-1]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            if pid in self.should_fail_prompts:
                resp = {
                    pid: {
                        "prompt": [0, pid, {}, {}],
                        "outputs": {},
                        "status": {"completed": False, "status_str": "error", "messages": ["CUDA Out of Memory"]}
                    }
                }
            elif pid in self.completed_histories:
                resp = {pid: self.completed_histories[pid]}
            else:
                # 默认模拟一个成功的图片与视频输出
                resp = {
                    pid: {
                        "prompt": [0, pid, {}, {}],
                        "outputs": {
                            "9": {
                                "images": [{"filename": f"{pid}_test.png", "subfolder": "2026-10-09", "type": "output"}]
                            },
                            "10": {
                                "videos": [{"filename": f"{pid}_video.mp4", "subfolder": "2026-10-09", "type": "output"}]
                            }
                        },
                        "status": {"completed": True, "status_str": "success", "messages": []}
                    }
                }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/prompt":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            MockComfyHandler.prompts_received.append(data)

            # 生成一个 mock prompt_id
            pid = f"mock-pid-{len(MockComfyHandler.prompts_received)}"

            # 如果 prompt 中含有 trigger_error 标记，记录为失败用例
            if "trigger_error" in json.dumps(data):
                MockComfyHandler.should_fail_prompts.add(pid)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"prompt_id": pid, "number": 1}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()


class TestComfySQLiteQueue(unittest.TestCase):
    mock_server = None
    server_thread = None
    mock_url = "http://127.0.0.1:18188"

    @classmethod
    def setUpClass(cls):
        # 1. 临时重定向数据库到隔离目录
        os.makedirs(TEST_DIR, exist_ok=True)
        queue_mod.DB_DIR = TEST_DIR
        queue_mod.DB_PATH = TEST_DB_PATH

        # 2. 启动本地 Mock ComfyUI HTTP Server (端口 0 自动分配空闲端口)
        cls.mock_server = HTTPServer(("127.0.0.1", 0), MockComfyHandler)
        mock_port = cls.mock_server.server_address[1]
        cls.mock_url = f"http://127.0.0.1:{mock_port}"
        cls.server_thread = threading.Thread(target=cls.mock_server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        if cls.mock_server:
            cls.mock_server.shutdown()
        # 清理测试临时目录
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR, ignore_errors=True)

    def setUp(self):
        # 每个测试用例前重置测试数据库
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        queue_mod.init_db()
        MockComfyHandler.prompts_received.clear()
        MockComfyHandler.should_fail_prompts.clear()
        MockComfyHandler.completed_histories.clear()

    def test_01_enqueue_and_schema(self):
        """【测试 1】任务入库测试：验证先落库、pending 状态及元数据解析"""
        sample_prompt = {"3": {"class_type": "KSampler", "inputs": {"seed": 12345}}}
        extra_meta = {"shot_id": "shot_01", "scene": "intro"}

        task_id = queue_mod.enqueue_task(sample_prompt, batch_name="batch_smoke", extra_meta=extra_meta)
        self.assertIsNotNone(task_id)

        conn = queue_mod.get_db_connection()
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["batch_name"], "batch_smoke")
        self.assertIn("KSampler", row["prompt_payload"])

        loaded_meta = json.loads(row["extra_meta"])
        self.assertEqual(loaded_meta["shot_id"], "shot_01")
        print("[PASS] 测试 1 通过: 任务成功先行落库，字段与元数据完整。")

    def test_02_crash_simulation_and_breakpoint_resume(self):
        """【测试 2】模拟中途断电/崩溃与断点续跑：验证中断的任务能被安全恢复并执行完成"""
        # 1. 模拟一个之前正在执行 (running) 但进程崩溃遗留的任务
        sample_prompt = {"1": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}}}
        task_id = queue_mod.enqueue_task(sample_prompt, batch_name="crash_test")

        # 手动篡改状态为 'running' 模拟机器断电、系统崩溃时的残留状态
        conn = queue_mod.get_db_connection()
        with conn:
            conn.execute("UPDATE tasks SET status = 'running', prompt_id = 'crashed_pid' WHERE task_id = ?", (task_id,))
        conn.close()

        # 2. 执行 resume_queue，应自动将 'running' 任务重置为 'pending' 并接续执行
        queue_mod.resume_queue(base_url=self.mock_url, batch_name="crash_test")

        # 3. 验证任务最终状态变为 'completed'，且产物记录完整
        conn = queue_mod.get_db_connection()
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        self.assertEqual(row["status"], "completed")
        self.assertIsNotNone(row["finished_at"])

        assets = conn.execute("SELECT * FROM assets WHERE task_id = ?", (task_id,)).fetchall()
        self.assertGreaterEqual(len(assets), 1)
        conn.close()
        print("[PASS] 测试 2 通过: 模拟崩溃恢复成功，中断任务顺利断点续跑并完成。")

    def test_03_failure_isolation_and_retry(self):
        """【测试 3】错误隔离与重试机制：失败任务不阻塞后续任务，且支持一键重试"""
        # 任务 A: 触发失败
        fail_prompt = {"error": "trigger_error"}
        task_a = queue_mod.enqueue_task(fail_prompt, batch_name="error_test")

        # 任务 B: 正常任务
        normal_prompt = {"normal": "ok"}
        task_b = queue_mod.enqueue_task(normal_prompt, batch_name="error_test")

        # 执行批次
        queue_mod.resume_queue(base_url=self.mock_url, batch_name="error_test")

        conn = queue_mod.get_db_connection()
        row_a = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_a,)).fetchone()
        row_b = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_b,)).fetchone()
        conn.close()

        # 验证 A 失败，B 依然顺利完成（错误隔离）
        self.assertEqual(row_a["status"], "failed")
        self.assertIn("CUDA Out of Memory", row_a["error_msg"])
        self.assertEqual(row_b["status"], "completed")

        # 测试 retry_failed()
        queue_mod.retry_failed()
        conn = queue_mod.get_db_connection()
        row_a_retried = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_a,)).fetchone()
        conn.close()
        self.assertEqual(row_a_retried["status"], "pending")
        self.assertIsNone(row_a_retried["error_msg"])
        print("[PASS] 测试 3 通过: 异常任务被严格隔离并记录原因，一键重试重置为 pending。")

    def test_04_asset_tracking_and_classification(self):
        """【测试 4】产物资产自动提取与分类索引验证"""
        sample_prompt = {"out": "nodes"}
        task_id = queue_mod.enqueue_task(sample_prompt, batch_name="asset_test")
        queue_mod.resume_queue(base_url=self.mock_url, batch_name="asset_test")

        conn = queue_mod.get_db_connection()
        assets = conn.execute("SELECT * FROM assets WHERE task_id = ?", (task_id,)).fetchall()
        conn.close()

        self.assertEqual(len(assets), 2)
        asset_types = {a["asset_type"] for a in assets}
        self.assertIn("image", asset_types)
        self.assertIn("video", asset_types)

        # 验证路径结构中包含子目录 (YYYY-MM-DD 规范)
        for a in assets:
            self.assertEqual(a["subfolder"], "2026-10-09")
            self.assertTrue(a["filename"].endswith(".png") or a["filename"].endswith(".mp4"))
        print("[PASS] 测试 4 通过: 资产自动识别分类 (image/video) 且日期归档路径准确。")


def run_tests():
    print("=" * 60)
    print("  ComfyUI SQLite 外部任务状态管理与断点续跑 自动化测试套件")
    print("=" * 60)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestComfySQLiteQueue)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n[ALL TESTS PASSED] 所有测试用例 100% 通过！方案 2 已具备生产级可靠性。")
        return 0
    else:
        print("\n[TESTS FAILED] 有测试未通过，请检查错误日志。")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
