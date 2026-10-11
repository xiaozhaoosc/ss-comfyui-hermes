import os
import subprocess
import glob

audit_dir = "output/2026-10-09/yangjiajiang_ep03/audit_debug"
os.makedirs(audit_dir, exist_ok=True)

# 1. 抽取拼装后的 muse 成片的前几秒帧
full_muse_mp4 = "output/2026-10-09/yangjiajiang_ep03/final/北宋杨家将_第03集_全集正剧母带_muse_720p.mp4"
if os.path.exists(full_muse_mp4):
    for sec, name in [(2, "full_muse_at_2s.jpg"), (7, "full_muse_at_7s.jpg"), (12, "full_muse_at_12s.jpg"), (25, "full_muse_at_25s.jpg")]:
        out_p = os.path.join(audit_dir, name)
        cmd = ["ffmpeg", "-y", "-ss", str(sec), "-i", full_muse_mp4, "-vframes", "1", "-q:v", "2", out_p]
        subprocess.run(cmd, capture_output=True)
        print(f"Extracted {name}")

# 2. 抽取 muse_videos 原始单镜
for sid in [1, 2, 3, 4, 10, 20]:
    raw_muse = f"output/2026-10-09/yangjiajiang_ep03/muse_videos/muse_shot{sid:02d}.mp4"
    if os.path.exists(raw_muse):
        out_p = os.path.join(audit_dir, f"raw_muse_shot{sid:02d}.jpg")
        cmd = ["ffmpeg", "-y", "-ss", "1.5", "-i", raw_muse, "-vframes", "1", "-q:v", "2", out_p]
        subprocess.run(cmd, capture_output=True)
        print(f"Extracted raw_muse_shot{sid:02d}.jpg")

# 3. 抽取本地 ComfyUI 对应单镜
for sid in [1, 2, 3, 4, 10, 20]:
    raw_comfy = f"output/2026-10-09/yangjiajiang_ep03/yang_ep03_shot{sid:02d}_00001_.mp4"
    if os.path.exists(raw_comfy):
        out_p = os.path.join(audit_dir, f"raw_comfy_shot{sid:02d}.jpg")
        cmd = ["ffmpeg", "-y", "-ss", "1.5", "-i", raw_comfy, "-vframes", "1", "-q:v", "2", out_p]
        subprocess.run(cmd, capture_output=True)
        print(f"Extracted raw_comfy_shot{sid:02d}.jpg")

print("All sample frames extracted successfully!")
