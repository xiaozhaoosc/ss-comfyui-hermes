import os
import glob
import json
import urllib.request

out_dir = r"output/2026-10-08/yangjiajiang_ep02"
mp4s = sorted(glob.glob(os.path.join(out_dir, "yang_ep02_shot*.mp4")))
print(f"Rendered MP4 count: {len(mp4s)} / 54")
if mp4s:
    print(f"First: {os.path.basename(mp4s[0])}")
    print(f"Latest: {os.path.basename(mp4s[-1])}")

try:
    req = urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=5)
    q = json.loads(req.read())
    running = len(q.get("queue_running", []))
    pending = len(q.get("queue_pending", []))
    print(f"ComfyUI Queue: Running={running}, Pending={pending}")
except Exception as e:
    print(f"ComfyUI Queue check error: {e}")
