import subprocess
import os

def extract_shot02_frames():
    vid = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/muse_shot02.mp4")
    out_dir = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison/muse_shot02_frames")
    os.makedirs(out_dir, exist_ok=True)
    
    for sec in [1, 2, 3]:
        out_img = os.path.join(out_dir, f"frame_{sec}s.jpg")
        cmd = ["ffmpeg", "-y", "-ss", f"00:00:0{sec}", "-i", vid, "-vframes", "1", out_img]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Sec {sec}: {os.path.exists(out_img)} ({os.path.getsize(out_img) if os.path.exists(out_img) else 0} bytes)")

if __name__ == "__main__":
    extract_shot02_frames()
