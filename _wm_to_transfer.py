"""临时守护：等白模视频生成后，自动提交"小G3(5) + 新白模驱动"的动作迁移任务。
（pass1 在队列里要排很久，用它把后半步接上，避免人工守着）
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
WM = os.path.join(ROOT, "input", "wm_202610.mp4")
DEADLINE = time.time() + 3 * 3600

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
print("[watch] 等待白模视频:", WM, flush=True)
while time.time() < DEADLINE:
    if os.path.exists(WM) and os.path.getsize(WM) > 80 * 1024:
        time.sleep(8)  # 等写盘收尾
        print("[watch] 白模已就绪 size=%.2fMB" % (os.path.getsize(WM) / 1048576), flush=True)
        break
    time.sleep(15)
else:
    print("[watch] 超时未等到白模视频", flush=True)
    sys.exit(1)

cmd = [sys.executable, os.path.join(ROOT, "tools", "submit_h3_duozhi_fix.py"),
       "--ref", "5", "--driver", "wm_202610", "--variant", "base",
       "--seconds", "8.7"]
print("[watch] 提交迁移任务:", " ".join(cmd), flush=True)
r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout, flush=True)
print(r.stderr, flush=True)
print("[watch] 退出码:", r.returncode, flush=True)
