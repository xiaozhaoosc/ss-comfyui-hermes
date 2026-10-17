import cv2
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

def main():
    video_in = os.path.abspath(r"output/2026-10-13/v6_white_model/jia_dance_whitemodel_00001.mp4")
    audio_src = os.path.abspath(r"input/runcha_dance.mp4")
    video_out = os.path.abspath(r"output/2026-10-13/v6_white_model/jia_dance_final_with_audio.mp4")

    print(f"正在封装原视频音频: {audio_src} -> {video_out}")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_in,
        "-i", audio_src,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-shortest",
        video_out
    ]
    ret = subprocess.run(cmd, capture_output=True, text=True)
    if ret.returncode == 0:
        print(f"✅ 音频封装完成！带音频最终成品: {video_out} (大小: {os.path.getsize(video_out)} 字节)")
    else:
        print(f"⚠️ FFmpeg 警告: {ret.stderr[:200]}")

    out_dir = r"output/2026-10-13/v6_white_model/frames"
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_in)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"成片规格: 分辨率 {w}x{h}, 帧数 {total}, 帧率 {fps} fps, 时长 {total/fps:.2f}s")

    for i in [0, 70, 140, 210, 270]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        r, f = cap.read()
        if r and f is not None:
            cv2.imwrite(os.path.join(out_dir, f"frame_{i}.jpg"), f)
    cap.release()
    print(f"✅ 抽帧核验图片保存至: {out_dir}")

if __name__ == "__main__":
    main()
