#!/usr/bin/env python3
"""
add_text_overlay.py - 视频后处理：AI生成水印 + 底部语录 + 语录重命名
用法:
  python add_text_overlay.py <input_dir> [output_dir]
  python add_text_overlay.py <input_dir> [output_dir] [--category 国学]

输出文件以语录文字命名，如: 路漫漫其修远兮.mp4
"""

import json
import os
import random
import subprocess
import sys
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
QUOTES_FILE = SCRIPT_DIR / "quotes.json"
FONT_FILE = r"C:\Windows\Fonts\msyh.ttc"

AI_TEXT = "AI生成"
AI_DURATION = 5
VIDEO_CRF = "18"
VIDEO_PRESET = "fast"


def load_quotes():
    with open(QUOTES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def escape_ffmpeg(text):
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def sanitize_filename(text, max_len=40):
    """清理文件名非法字符"""
    illegal = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']
    for c in illegal:
        text = text.replace(c, '_')
    return text[:max_len].strip()


def build_cmd(input_path, output_path, quote):
    q_text = escape_ffmpeg(quote["text"])
    q_source = escape_ffmpeg(f"— {quote['source']}")
    fp = FONT_FILE.replace("\\", "/").replace(":", "\\:")

    vf = (
        f"drawtext=fontfile='{fp}'"
        f":text='{AI_TEXT}'"
        f":fontsize=22:fontcolor=white:borderw=2:bordercolor=black"
        f":x=20:y=(h-th-20)"
        f":enable='between(t\\,0\\,{AI_DURATION})'"
        ","
        f"drawtext=fontfile='{fp}'"
        f":text='{q_text}'"
        f":fontsize=24:fontcolor=white:borderw=2:bordercolor=black"
        f":x=(w-text_w)/2:y=h-text_h-30"
        f":box=1:boxcolor=black@0.5:boxborderw=15"
        ","
        f"drawtext=fontfile='{fp}'"
        f":text='{q_source}'"
        f":fontsize=18:fontcolor=white@0.8:borderw=1:bordercolor=black"
        f":x=(w-text_w)/2+100:y=h-30+8"
    )

    return [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", vf,
        "-c:v", "libx264", "-crf", VIDEO_CRF, "-preset", VIDEO_PRESET,
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output_path)
    ]


def main():
    parser = argparse.ArgumentParser(description="视频后处理：AI生成水印 + 底部语录 + 语录重命名")
    parser.add_argument("input_dir", help="输入视频目录")
    parser.add_argument("output_dir", nargs="?", help="输出目录")
    parser.add_argument("--category", help="语录分类: 国学/鸡汤/热梗")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else input_dir / "with_quotes"
    output_dir.mkdir(parents=True, exist_ok=True)

    quotes = load_quotes()
    if args.category:
        filtered = [q for q in quotes if q.get("category") == args.category]
        if filtered:
            quotes = filtered

    # 扫描视频
    video_files = []
    for ext in ["*.mp4", "*.avi", "*.mov", "*.mkv"]:
        video_files.extend(input_dir.glob(ext))
    video_files = [f for f in video_files if "-audio" not in f.name and "temp_" not in f.name]
    video_files.sort()

    if not video_files:
        print(f"❌ 未找到视频文件")
        sys.exit(1)

    print(f"📹 {len(video_files)} 个视频 | 📚 {len(quotes)} 条语录")
    print(f"📁 输出: {output_dir}")
    print("=" * 60)

    # 随机分配语录，尽量不重复
    available = list(quotes)
    if len(video_files) > len(available):
        available = (available * ((len(video_files) // len(available)) + 1))
    random.shuffle(available)

    used_names = set()
    success = fail = 0

    for i, vf in enumerate(video_files, 1):
        quote = available[i - 1]
        base_name = sanitize_filename(quote["text"])
        out_name = f"{base_name}.mp4"
        counter = 1
        while out_name in used_names:
            out_name = f"{base_name}_{counter}.mp4"
            counter += 1
        used_names.add(out_name)

        out_path = output_dir / out_name
        print(f"\n[{i}/{len(video_files)}] {vf.name}")
        print(f"  → {out_name}")
        print(f"  📝 {quote['text']} — {quote['source']} [{quote['category']}]")

        cmd = build_cmd(vf, out_path, quote)
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")

        if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 10000:
            size_mb = out_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ {size_mb:.1f}MB")
            success += 1
        else:
            print(f"  ❌ 失败")
            fail += 1

    print(f"\n{'='*60}")
    print(f"🏁 完成: 成功 {success}, 失败 {fail}")
    print(f"📁 输出: {output_dir}")


if __name__ == "__main__":
    main()
