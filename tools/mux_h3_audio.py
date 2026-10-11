#!/usr/bin/env python3
"""合并 7 段 H3 原生音频，并混入成片视频（视频 copy + 音频转 AAC）"""
import subprocess, shutil, tempfile, os, glob

SRC_AUDIO = r"D:\ai_projects\ComfyUI\output\fenghuo_audio"
VIDEO = r"D:\ai_projects\ComfyUI\output\fenghuo\fenghuo_full.mp4"
OUT = r"D:\ai_projects\ComfyUI\output\fenghuo\fenghuo_full_audio.mp4"

if not os.path.exists(VIDEO):
    print("错误: 视频不存在", VIDEO)
    raise SystemExit(1)

flacs = sorted(glob.glob(os.path.join(SRC_AUDIO, "seg0*.flac")))
print(f"待合并音频: {len(flacs)} 个")

tmp = tempfile.mkdtemp(prefix="ffaudio_")
try:
    new = []
    for i, f in enumerate(flacs, 1):
        dst = os.path.join(tmp, f"seg{i:02d}.flac")
        shutil.copy2(f, dst)
        new.append(dst)
    listfile = os.path.join(tmp, "audio_list.txt")
    with open(listfile, "w", encoding="utf-8") as fp:
        for p in new:
            fp.write(f"file '{p.replace(os.sep, '/')}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-i", VIDEO,
        "-f", "concat", "-safe", "0", "-i", listfile,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", OUT,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("--- ffmpeg stderr 末尾 ---")
    print((r.stderr or "")[-1200:])
    print("退出码:", r.returncode)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n完成:", OUT)
print("文件存在:", os.path.exists(OUT), "| 大小:", os.path.getsize(OUT) if os.path.exists(OUT) else "-")
