"""等待 ComfyUI 启动完成。"""
import urllib.request
import time
import sys

URL = "http://127.0.0.1:8188/system_stats"
MAX_TRIES = 40
INTERVAL = 5

for i in range(1, MAX_TRIES + 1):
    try:
        with urllib.request.urlopen(URL, timeout=3) as r:
            print(f"ComfyUI ready: HTTP {r.status}")
            sys.exit(0)
    except Exception:
        print(f"waiting... ({i}/{MAX_TRIES})")
        time.sleep(INTERVAL)

print("timeout: ComfyUI not ready")
sys.exit(1)
