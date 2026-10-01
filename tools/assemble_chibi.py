#!/usr/bin/env python3
"""「赤壁夜袭」最终装配：拼接标题卡 + 2.39:1 遮幅"""
import subprocess, os

D = r"D:\ai_projects\ComfyUI\output\chibi"
FULL = os.path.join(D, "chibi_full.mp4")
TITLE = os.path.join(D, "title_card.mp4")
TITLE_SIL = os.path.join(D, "title_card_silent.mp4")
FINAL_169 = os.path.join(D, "chibi_final.mp4")
FINAL_239 = os.path.join(D, "chibi_final_239.mp4")

# 1. 标题卡加静音音轨（32kHz 立体声，匹配正片）
cmd1 = ["ffmpeg", "-y", "-i", TITLE,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=32000",
        "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", TITLE_SIL]
r1 = subprocess.run(cmd1, capture_output=True, text=True)
print("加静音音轨退出码:", r1.returncode)
if r1.returncode != 0:
    print((r1.stderr or "")[-600:]); raise SystemExit(1)

# 2. 拼接正片 + 标题卡（stream copy）
listfile = os.path.join(D, "_concat.txt")
with open(listfile, "w", encoding="utf-8") as f:
    f.write(f"file '{FULL.replace(os.sep,'/')}'\n")
    f.write(f"file '{TITLE_SIL.replace(os.sep,'/')}'\n")
cmd2 = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
        "-c", "copy", FINAL_169]
r2 = subprocess.run(cmd2, capture_output=True, text=True)
print("拼接退出码:", r2.returncode)
if r2.returncode != 0:
    print((r2.stderr or "")[-600:]); raise SystemExit(1)

# 3. 2.39:1 遮幅（中心裁剪 1344x768 -> 1344x562）
cmd3 = ["ffmpeg", "-y", "-i", FINAL_169,
        "-vf", "crop=1344:562:0:103",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "copy",
        FINAL_239]
r3 = subprocess.run(cmd3, capture_output=True, text=True)
print("2.39:1 裁剪退出码:", r3.returncode)
if r3.returncode != 0:
    print((r3.stderr or "")[-600:])

os.remove(listfile)
for f in (FINAL_169, FINAL_239):
    print(f"{os.path.basename(f)}: 存在={os.path.exists(f)}, 大小={os.path.getsize(f) if os.path.exists(f) else '-'}")
