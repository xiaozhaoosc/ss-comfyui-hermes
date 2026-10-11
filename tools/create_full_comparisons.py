import sys
import os
import subprocess
import cv2

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
BGM = r"D:\ai_projects\ComfyUI\input\ken4\face\bgm原创\Calling_Through_The_Screen (1).mp3"
OUT_DIR = r"D:\ai_projects\ComfyUI\output\2026-10-08\motion_transfer_full"

comparisons = [
    {
        "name": "ig14",
        "src": r"C:\Users\kenzhao\Downloads\Instagram14_video.mp4",
        "gen": os.path.join(OUT_DIR, "ig14_1to1_full_duration.mp4"),
        "out": os.path.join(OUT_DIR, "ig14_full_side_by_side.mp4"),
        "dur": "6.07"
    },
    {
        "name": "ig18",
        "src": r"C:\Users\kenzhao\Downloads\Instagram18_video.mp4",
        "gen": os.path.join(OUT_DIR, "ig18_1to1_full_duration.mp4"),
        "out": os.path.join(OUT_DIR, "ig18_full_side_by_side.mp4"),
        "dur": "7.07"
    }
]

for c in comparisons:
    print(f"Generating full side-by-side for {c['name']}...")
    filter_complex = (
        "[0:v]scale=480:832:force_original_aspect_ratio=decrease,pad=480:832:(ow-iw)/2:(oh-ih)/2[v0];"
        "[1:v]scale=480:832[v1];"
        "[v0][v1]hstack=inputs=2[outv]"
    )
    cmd = [
        FFMPEG, "-y",
        "-i", c["src"],
        "-i", c["gen"]
    ]
    if os.path.exists(BGM):
        cmd.extend(["-stream_loop", "-1", "-i", BGM])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-t", c["dur"],
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p"
    ])
    if os.path.exists(BGM):
        cmd.extend(["-map", "2:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"])
    cmd.append(c["out"])
    
    subprocess.run(cmd, capture_output=True)
    if os.path.exists(c["out"]):
        cap = cv2.VideoCapture(c["out"])
        cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        dur = cnt / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0
        cap.release()
        sz = os.path.getsize(c["out"]) / 1024 / 1024
        print(f"[OK] Created {c['out']}: {w}x{h}, {cnt} frames, {dur:.2f}s, {sz:.2f}MB")
    else:
        print(f"Failed {c['name']}")
