# -*- coding: utf-8 -*-
"""ComfyUI Agent HTTP Webhook & API Bridge.

A lightweight HTTP server designed for AI Agent frameworks (Dify, n8n, Coze, LangChain, etc.)
to trigger local character and garment generation pipelines and retrieve execution results.

Default Port: 8095
Endpoints:
- GET  /health           : Health check
- POST /tasks/character  : Trigger character generation (JSON body: {"count": 1, "async": false})
- POST /tasks/garment    : Trigger garment generation   (JSON body: {"count": 1, "async": false})
- GET  /tasks/status     : Get latest generated assets & database stats
"""

import os
import sys
import json
import time
import subprocess
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Set UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMFY_ROOT = Path(__file__).resolve().parent.parent.parent
PYTHON_EXE = COMFY_ROOT / "venv" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

PORT = 8095
RUNNING_LOCK = threading.Lock()
TASK_STATUS = {
    "current_running": None,
    "last_character_run": None,
    "last_garment_run": None
}


def execute_script(script_name, count=1):
    with RUNNING_LOCK:
        TASK_STATUS["current_running"] = script_name
        start_time = time.time()
        try:
            cmd = [str(PYTHON_EXE), str(COMFY_ROOT / "tools" / script_name), "--count", str(count)]
            res = subprocess.run(
                cmd,
                cwd=str(COMFY_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            elapsed = round(time.time() - start_time, 2)
            record = {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "elapsed_seconds": elapsed,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "stdout_tail": res.stdout[-800:] if res.stdout else "",
                "stderr_tail": res.stderr[-800:] if res.stderr else ""
            }
            if "character" in script_name:
                TASK_STATUS["last_character_run"] = record
            else:
                TASK_STATUS["last_garment_run"] = record
            return record
        finally:
            TASK_STATUS["current_running"] = None


class AgentBridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/health"]:
            self._send_json(200, {
                "status": "healthy",
                "service": "ComfyUI-Agent-Bridge",
                "comfy_root": str(COMFY_ROOT),
                "python_exe": str(PYTHON_EXE),
                "is_busy": TASK_STATUS["current_running"] is not None
            })
        elif parsed.path == "/tasks/status":
            char_idx = COMFY_ROOT / "character_library" / "index.json"
            garment_idx = COMFY_ROOT / "garment_library" / "index.json"
            char_count = len(json.loads(char_idx.read_text(encoding="utf-8"))) if char_idx.exists() else 0
            garment_count = len(json.loads(garment_idx.read_text(encoding="utf-8"))) if garment_idx.exists() else 0
            
            self._send_json(200, {
                "task_status": TASK_STATUS,
                "library_counts": {
                    "characters": char_count,
                    "garments": garment_count
                }
            })
        else:
            self._send_json(404, {"error": "Not found", "path": parsed.path})

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_len > 0:
            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
            except Exception:
                pass

        count = body.get("count", 1)
        is_async = body.get("async", False)

        if parsed.path in ["/tasks/character", "/tasks/generate-character"]:
            if TASK_STATUS["current_running"] is not None:
                self._send_json(429, {"error": "Another task is already running", "running": TASK_STATUS["current_running"]})
                return
            if is_async:
                t = threading.Thread(target=execute_script, args=("hourly_character_task.py", count))
                t.daemon = True
                t.start()
                self._send_json(202, {"status": "accepted", "task": "character_generation", "async": True})
            else:
                res = execute_script("hourly_character_task.py", count)
                self._send_json(200 if res["success"] else 500, res)

        elif parsed.path in ["/tasks/garment", "/tasks/generate-garment"]:
            if TASK_STATUS["current_running"] is not None:
                self._send_json(429, {"error": "Another task is already running", "running": TASK_STATUS["current_running"]})
                return
            if is_async:
                t = threading.Thread(target=execute_script, args=("hourly_garment_task.py", count))
                t.daemon = True
                t.start()
                self._send_json(202, {"status": "accepted", "task": "garment_generation", "async": True})
            else:
                res = execute_script("hourly_garment_task.py", count)
                self._send_json(200 if res["success"] else 500, res)
        else:
            self._send_json(404, {"error": "Endpoint not recognized", "path": parsed.path})


def run_server():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, AgentBridgeHandler)
    print(f"[*] ComfyUI Agent HTTP Bridge running on http://127.0.0.1:{PORT}")
    print("    Ready to receive triggers from Dify / n8n / Coze / LangGraph...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Agent Bridge...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
