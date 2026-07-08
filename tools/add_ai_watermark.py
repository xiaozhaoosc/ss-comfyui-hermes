#!/usr/bin/env python
"""Add 'AI生成' watermark to the beginning of videos (bottom-left)."""
import subprocess
import sys
import os

FFMPEG = r"C:\Users\kenzhao\anaconda3\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
FONT = r"C\:/Windows/Fonts/msyh.ttc"
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output"

# Videos to process
videos = sys.argv[1:] if len(sys.argv) > 1 else []

if not videos:
    print("Usage: python add_ai_watermark.py video1.mp4 [video2.mp4 ...]")
    sys.exit(1)

for vpath in videos:
    if not os.path.exists(vpath):
        print(f"SKIP (not found): {vpath}")
        continue

    base, ext = os.path.splitext(vpath)
    outpath = f"{base}_watermarked{ext}"

    # drawtext: "AI生成" at bottom-left, first 5 seconds
    # white text with black border for visibility
    vf = (
        f"drawtext=fontfile='{FONT}'"
        f":text='AI生成'"
        f":x=20:y=h-th-20"
        f":fontsize=40"
        f":fontcolor=white"
        f":borderw=2:bordercolor=black"
        f":enable='between(t\\,0\\,5)'"
    )

    cmd = [
        FFMPEG, "-y",
        "-i", vpath,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "19",
        "-c:a", "copy",
        outpath
    ]

    print(f"Processing: {os.path.basename(vpath)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Done -> {os.path.basename(outpath)}")
    else:
        print(f"  ERROR: {result.stderr[-300:]}")
