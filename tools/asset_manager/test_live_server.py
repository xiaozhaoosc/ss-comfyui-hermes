# -*- coding: utf-8 -*-
"""Test live TCP HTTP requests against a real running server process on port 8090."""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PYTHON_EXE = r"D:\ai_projects\ComfyUI\venv\Scripts\python.exe"
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def test_live_server():
    print("=" * 65)
    print(">>> Launching real Asset Manager server process on port 8090...")
    print("=" * 65)
    proc = subprocess.Popen(
        [PYTHON_EXE, "tools/asset_manager/run.py", "--port", "8090", "--no-browser"],
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for uvicorn to bind port
        time.sleep(4.0)
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            print("Process died early! Stderr:", stderr.decode('utf-8', errors='replace'))
            raise RuntimeError("Server process died early")

        # 1. Test live root HTML request
        print("1. Testing live GET http://127.0.0.1:8090/ ...")
        with urllib.request.urlopen("http://127.0.0.1:8090/", timeout=3) as resp:
            content = resp.read().decode("utf-8")
            assert resp.status == 200
            assert "AIGC Local Asset Hub" in content
            print("   [OK] Live SPA HTML received! Status: 200, length:", len(content))

        # 2. Test live API stats request
        print("2. Testing live GET http://127.0.0.1:8090/api/system/stats ...")
        with urllib.request.urlopen("http://127.0.0.1:8090/api/system/stats", timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            print("   [OK] Live API Stats received:", data)

        # 3. Test live static image request
        print("3. Testing live GET http://127.0.0.1:8090/static/characters/faces/char_duo/thumb.png ...")
        with urllib.request.urlopen("http://127.0.0.1:8090/static/characters/faces/char_duo/thumb.png", timeout=3) as resp:
            img_bytes = resp.read()
            assert resp.status == 200
            print("   [OK] Live Static Image received! Bytes:", len(img_bytes))

        print("\n" + "=" * 65)
        print(">>> REAL LIVE TCP NETWORK TEST PASSED 100%! <<<")
        print("=" * 65)

    finally:
        print("Terminating test server process...")
        proc.terminate()
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Test server cleanly stopped.")


if __name__ == "__main__":
    test_live_server()
