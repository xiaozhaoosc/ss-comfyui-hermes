#!/usr/bin/env python3
"""ffmpeg 合并 7 个分段为完整视频（stream copy，无重编码）"""
import subprocess, shutil, tempfile, os, glob

SRC_DIR = r"D:\ai_projects\ComfyUI\output\fenghuo"
OUT = r"D:\ai_projects\ComfyUI\output\fenghuo\fenghuo_full.mp4"

# 按文件名顺序列出分段（seg01..seg07）
files = sorted(glob.glob(os.path.join(SRC_DIR, "seg0*.mp4")))
print(f"待合并分段: {len(files)} 个")
for f in files:
    print("  ", os.path.basename(f))

tmp = tempfile.mkdtemp(prefix="ffmerge_")
try:
    # 复制为 ASCII 名，避免中文路径导致 ffmpeg 编码问题
    new_paths = []
    for i, f in enumerate(files, 1):
        dst = os.path.join(tmp, f"seg{i:02d}.mp4")
        shutil.copy2(f, dst)
        new_paths.append(dst)

    listfile = os.path.join(tmp, "list.txt")
    with open(listfile, "w", encoding="utf-8") as fp:
        for p in new_paths:
            fp.write(f"file '{p.replace(os.sep, '/')}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", OUT]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("\n--- ffmpeg stderr 末尾 ---")
    print((r.stderr or "")[-1500:])
    print("退出码:", r.returncode)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n完成:", OUT)
print("文件存在:", os.path.exists(OUT), "| 大小:", os.path.getsize(OUT) if os.path.exists(OUT) else "-")
