#!/usr/bin/env python3
"""等待 H3 走秀任务完成，然后混入原生音频生成最终成片"""
import json, urllib.request, time, os, glob, subprocess

BASE = "http://127.0.0.1:8188"
PID = "8410e14e-04d9-41ac-b850-7829e61dabb9"
DIR = r"D:\ai_projects\ComfyUI\output\h3_runway"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"

print(f"等待 pid={PID[:13]} ...", flush=True)
t0 = time.time()
done = False
while time.time() - t0 < 7200:
    try:
        h = json.loads(urllib.request.urlopen(f"{BASE}/history/{PID}", timeout=15).read())
        rec = h.get(PID)
        if rec:
            st = rec.get("status", {})
            if st.get("status_str") == "success" or st.get("completed") or rec.get("outputs"):
                done = True; break
            if st.get("status_str") == "error":
                print("执行出错:", json.dumps(st, ensure_ascii=False)[:500]); break
    except Exception as e:
        print("查询异常:", e)
    el = int(time.time() - t0)
    print(f"  ⏱ {el//60}m{el%60:02d}s", flush=True)
    time.sleep(30)

if not done:
    print("超时或失败，未混音"); raise SystemExit(1)

os.makedirs(DIR, exist_ok=True)
mp4 = sorted(glob.glob(os.path.join(DIR, "runway_*.mp4")), key=os.path.getmtime)
flac = sorted(glob.glob(os.path.join(DIR, "runway_*.flac")), key=os.path.getmtime)
print("视频:", [os.path.basename(f) for f in mp4], "音频:", [os.path.basename(f) for f in flac])
if not mp4 or not flac:
    print("产物不完整，跳过混音"); raise SystemExit(1)
v, a = mp4[-1], flac[-1]
out = os.path.join(DIR, "runway_fashion_c02_9x16_full.mp4")
r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", v, "-i", a,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out],
                   capture_output=True, text=True)
print("ffmpeg 混音退出码:", r.returncode)
print("⏰ 用时", f"{int(time.time()-t0)}s")
if os.path.exists(out):
    print(f"\n✅ 成片: {out} ({os.path.getsize(out)/1024/1024:.1f} MB)")
else:
    print("混音失败:", (r.stderr or "")[-800:])