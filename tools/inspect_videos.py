import cv2
import os

paths = [
    'C:/Users/kenzhao/Downloads/Instagram18_video.mp4',
    'C:/Users/kenzhao/Downloads/Instagram14_video.mp4',
    'output/2026-10-04/motion_transfer/ig18_user_test_00001_.mp4',
    'output/2026-10-08/motion_transfer/ig14_user_test_00001_.mp4',
    'input/motion_poses/ig18_user_test/ig18_user_test_pose_pure.mp4',
    'input/motion_poses/ig14_user_test/ig14_user_test_pose_pure.mp4'
]

import subprocess

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"

for p in paths:
    if not os.path.exists(p):
        print(f"NOT FOUND: {p}")
        continue
    cap = cv2.VideoCapture(p)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = cnt / fps if fps > 0 else 0
    cap.release()
    
    # ffprobe check audio
    cmd = [FFPROBE, "-v", "error", "-show_streams", p]
    res = subprocess.run(cmd, capture_output=True, text=True)
    has_audio = "codec_type=audio" in res.stdout
    has_video = "codec_type=video" in res.stdout
    sz = os.path.getsize(p) / 1024 / 1024
    print(f"{p}: {w}x{h}, {cnt}f, {fps:.1f}fps, {dur:.2f}s, size={sz:.2f}MB, audio={has_audio}")

