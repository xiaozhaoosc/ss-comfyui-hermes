#!/usr/bin/env python3
"""「赤壁夜袭」合并 6 段视频+音频 → 完整成片（视频 stream copy + 音频 AAC）"""
import subprocess, shutil, tempfile, os, glob

SRC_VID = r"D:\ai_projects\ComfyUI\output\chibi"
SRC_AUD = r"D:\ai_projects\ComfyUI\output\chibi_audio"
OUT = r"D:\ai_projects\ComfyUI\output\chibi\chibi_full.mp4"

vids = sorted(glob.glob(os.path.join(SRC_VID, "chibi_0*.mp4")))
auds = sorted(glob.glob(os.path.join(SRC_AUD, "chibi_0*.flac")))
print(f"视频 {len(vids)} 段, 音频 {len(auds)} 段")

tmp = tempfile.mkdtemp(prefix="ffchibi_")
try:
    vpaths, apaths = [], []
    for i, f in enumerate(vids, 1):
        dst = os.path.join(tmp, f"v{i:02d}.mp4"); shutil.copy2(f, dst); vpaths.append(dst)
    for i, f in enumerate(auds, 1):
        dst = os.path.join(tmp, f"a{i:02d}.flac"); shutil.copy2(f, dst); apaths.append(dst)

    vlist = os.path.join(tmp, "vlist.txt")
    alist = os.path.join(tmp, "alist.txt")
    with open(vlist, "w", encoding="utf-8") as fp:
        for p in vpaths: fp.write(f"file '{p.replace(os.sep, '/')}'\n")
    with open(alist, "w", encoding="utf-8") as fp:
        for p in apaths: fp.write(f"file '{p.replace(os.sep, '/')}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", vlist,
        "-f", "concat", "-safe", "0", "-i", alist,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", OUT,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("--- ffmpeg 末尾 ---")
    print((r.stderr or "")[-900:])
    print("退出码:", r.returncode)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n完成:", OUT)
print("存在:", os.path.exists(OUT), "| 大小:", os.path.getsize(OUT) if os.path.exists(OUT) else "-")
