#!/usr/bin/env python3
"""H3 MV 7 段串联工具：把 7 段视频无缝衔接

策略（fl2va 首尾帧锚定的补充）:
1. 每段生成后用 ffmpeg 抽最后一帧 → 作为下一段的 first_frame 输入
2. 全段跑完后用 ffmpeg concat 无缝拼接（同分辨率同编码）
3. 生成分段清单供后续混音

用法:
  python tools/stitch_h3_mv7.py --extract-first   # 抽每段尾帧 → input/ 目录
  python tools/stitch_h3_mv7.py --concat          # 拼接 7 段 → output/h3_mv7/full.mp4
"""
import os, subprocess, sys, json

OUT_DIR = r"D:\ai_projects\ComfyUI\output\h3_mv7"
INPUT_DIR = r"D:\ai_projects\ComfyUI\input"
SEG_IDS = [f"seg{i:02d}" for i in range(1, 8)]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"❌ {' '.join(cmd[:4])}...: {r.stderr[-300:]}")
    return r.returncode == 0


def extract_last_frames():
    """每段抽最后一帧 → input/mv7_segXX_last.png"""
    for sid in SEG_IDS:
        # 找该段最新 mp4
        import glob
        matches = sorted(glob.glob(os.path.join(OUT_DIR, f"{sid}*.mp4")))
        if not matches:
            print(f"  ⚠️ {sid} 无 mp4，跳过")
            continue
        src = matches[-1]
        dst = os.path.join(INPUT_DIR, f"mv7_{sid}_last.png")
        if run(["ffmpeg", "-y", "-sseof", "-0.1", "-i", src, "-frames:v", "1", dst]):
            print(f"  ✅ {sid} 尾帧 → mv7_{sid}_last.png")


def concat():
    """拼接 7 段（先确认都存在）"""
    parts = []
    for sid in SEG_IDS:
        import glob
        matches = sorted(glob.glob(os.path.join(OUT_DIR, f"{sid}*.mp4")))
        if not matches:
            print(f"  ❌ {sid} 缺失，无法拼接")
            return
        parts.append(matches[-1])

    list_file = os.path.join(OUT_DIR, "concat_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for p in parts:
            f.write(f"file '{p.replace(os.sep, '/')}'\n")

    out = os.path.join(OUT_DIR, "h3_mv_full.mp4")
    if run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out]):
        print(f"✅ 拼接完成: {out}")
        # 验证
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=nw=1", out],
                           capture_output=True, text=True)
        print(f"   总时长: {r.stdout.strip()}")


if __name__ == "__main__":
    if "--extract-first" in sys.argv:
        extract_last_frames()
    if "--concat" in sys.argv:
        concat()
