#!/usr/bin/env python3
"""
restore_and_mix_audio.py - 恢复原视频音频 + 混搭背景音乐
用法:
  python restore_and_mix_audio.py --original <原视频目录> --processed <换脸后目录> --output <输出目录>
  python restore_and_mix_audio.py --original ... --processed ... --output ... --bg-music <音乐文件路径> --bg-volume 0.3
  python restore_and_mix_audio.py --original ... --processed ... --output ... --bg-music "D:\music\song.flac" --bg-volume 0.25

功能:
  1. 从原视频提取音频
  2. 与背景音乐混搭（原声为主，背景音乐降低音量）
  3. 合并到换脸后的视频
  4. 输出文件以语录命名（配合 add_text_overlay.py 的命名）

依赖: FFmpeg (scoop install ffmpeg)
"""

import json
import os
import random
import subprocess
import sys
import argparse
from pathlib import Path
import shutil

# 配置
SCRIPT_DIR = Path(__file__).parent
QUOTES_FILE = SCRIPT_DIR / "quotes.json"
BG_MUSIC_DIR = Path(r"D:\ai_projects\ComfyUI\input\music")

# 音频混合参数
ORIGINAL_VOLUME = 1.0      # 原声音量
BG_MUSIC_VOLUME = 0.25     # 背景音乐音量（相对原声）
BG_MUSIC_FADE_IN = 2       # 背景音乐淡入秒数
BG_MUSIC_FADE_OUT = 3      # 背景音乐淡出秒数


def get_audio_duration(video_path):
    """获取视频时长（秒）"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0


def has_audio(video_path):
    """检查视频是否有音频流"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return "audio" in result.stdout


def get_music_files():
    """获取背景音乐目录中的所有音乐文件"""
    music_files = []
    for ext in ["*.mp3", "*.wav", "*.flac", "*.m4a", "*.ogg", "*.aac"]:
        music_files.extend(BG_MUSIC_DIR.glob(ext))
    return sorted(music_files)


def mix_audio_ffmpeg(processed_video, original_video, output_path, bg_music=None, bg_volume=0.25):
    """
    FFmpeg 音频混合：
    - 从原视频提取音频
    - 可选：与背景音乐混搭
    - 合并到换脸后视频
    """
    duration = get_audio_duration(processed_video)
    if duration <= 0:
        print(f"  ❌ 无法获取视频时长")
        return False

    # 构建 FFmpeg 命令
    cmd = ["ffmpeg", "-y"]

    # 输入1: 换脸后视频（无音频）
    cmd.extend(["-i", str(processed_video)])

    # 输入2: 原视频（有音频）
    has_orig_audio = has_audio(original_video)
    if has_orig_audio:
        cmd.extend(["-i", str(original_video)])

    # 输入3: 背景音乐（可选）
    if bg_music and bg_music.exists():
        cmd.extend(["-i", str(bg_music)])
        has_bg = True
    else:
        has_bg = False

    # 构建滤镜
    filter_parts = []

    if has_bg and has_orig_audio:
        # 原声 + 背景音乐混搭
        # 原声: 直接使用
        # 背景音乐: 降低音量 + 循环到视频长度 + 淡入淡出
        filter_complex = (
            f"[1:a]volume={ORIGINAL_VOLUME}[orig];"  # 原声
            f"[2:a]volume={bg_volume},aloop=loop=-1:size=2e+09,atrim=duration={duration},"
            f"afade=t=in:st=0:d={BG_MUSIC_FADE_IN},"
            f"afade=t=out:st={duration - BG_MUSIC_FADE_OUT}:d={BG_MUSIC_FADE_OUT}[bg];"
            f"[orig][bg]amix=inputs=2:duration=shortest:dropout_transition=2[aout]"
        )
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v",  # 换脸后视频画面
            "-map", "[aout]",  # 混合音频
        ])
        print(f"  🎵 混音模式: 原声 + 背景音乐(音量{bg_volume})")

    elif has_orig_audio:
        # 只有原声，直接提取
        cmd.extend([
            "-map", "0:v",
            "-map", "1:a",
        ])
        print(f"  🔊 恢复原声模式")

    elif has_bg:
        # 只有背景音乐
        filter_complex = (
            f"[1:a]volume={bg_volume},aloop=loop=-1:size=2e+09,atrim=duration={duration},"
            f"afade=t=in:st=0:d={BG_MUSIC_FADE_IN},"
            f"afade=t=out:st={duration - BG_MUSIC_FADE_OUT}:d={BG_MUSIC_FADE_OUT}[aout]"
        )
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
        ])
        print(f"  🎵 纯背景音乐模式(音量{bg_volume})")
    else:
        print(f"  ⚠️ 无音频源，跳过")
        return False

    # 输出参数
    cmd.extend([
        "-c:v", "copy",  # 视频直接复制，不重编码
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ])

    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")

    if result.returncode != 0:
        print(f"  ❌ FFmpeg 失败: {result.stderr[-300:]}")
        return False

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  ✅ {os.path.basename(output_path)} ({size_mb:.1f}MB)")
        return True

    print(f"  ❌ 输出文件异常")
    return False


def load_quotes():
    if QUOTES_FILE.exists():
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def get_quote_name(quotes, index):
    """根据索引获取语录名（确定性分配）"""
    if not quotes:
        return f"video_{index:03d}"
    q = quotes[index % len(quotes)]
    name = q["text"]
    # 清理非法字符
    illegal = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t', '[', ']']
    for c in illegal:
        name = name.replace(c, '_')
    return name[:40].strip()


def main():
    parser = argparse.ArgumentParser(description="恢复原视频音频 + 混搭背景音乐")
    parser.add_argument("--original", required=True, help="原始视频目录（有音频的源文件）")
    parser.add_argument("--processed", required=True, help="换脸后视频目录（无音频的文件）")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--bg-music", help="背景音乐文件路径（不指定则从 music 目录自动选取）")
    parser.add_argument("--bg-volume", type=float, default=0.25, help="背景音乐音量 0.0-1.0 (默认: 0.25)")
    parser.add_argument("--no-bg", action="store_true", help="不添加背景音乐，只恢复原声")
    args = parser.parse_args()

    original_dir = Path(args.original)
    processed_dir = Path(args.processed)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 背景音乐
    bg_music = None
    if not args.no_bg:
        if args.bg_music:
            bg_music = Path(args.bg_music)
        else:
            music_files = get_music_files()
            if music_files:
                bg_music = music_files[0]  # 默认用第一首
                print(f"🎵 背景音乐: {bg_music.name}")
            else:
                print(f"⚠️ 未找到背景音乐文件，将只恢复原声")

    if bg_music and not bg_music.exists():
        print(f"❌ 背景音乐文件不存在: {bg_music}")
        sys.exit(1)

    # 扫描原视频和已处理视频
    original_videos = {}
    for f in original_dir.glob("*.mp4"):
        if "-audio" not in f.name and "faceswap" not in f.name:
            # 提取基础名（去掉后缀）
            stem = f.stem
            original_videos[stem] = f

    processed_videos = sorted([
        f for f in processed_dir.glob("*.mp4")
    ])

    if not processed_videos:
        print(f"❌ 未找到已处理的视频文件")
        sys.exit(1)

    # 加载语录
    quotes = load_quotes()

    print(f"📹 原始视频: {len(original_videos)} 个")
    print(f"📹 已处理视频: {len(processed_videos)} 个")
    print(f"📁 输出目录: {output_dir}")
    print("=" * 60)

    success = fail = skip = 0
    for i, processed_file in enumerate(processed_videos, 1):
        # 找到对应的原始视频
        # 已处理文件名可能是语录名或原名
        original_file = None

        # 策略1: 直接匹配文件名
        if processed_file.stem in original_videos:
            original_file = original_videos[processed_file.stem]

        # 策略2: 模糊匹配（语录名 → 原名，通过索引）
        if not original_file:
            # 按排序顺序匹配索引
            orig_list = sorted(original_videos.values())
            idx = i - 1
            if idx < len(orig_list):
                original_file = orig_list[idx]

        if not original_file:
            print(f"[{i}/{len(processed_videos)}] ⚠️ 找不到原始视频: {processed_file.name}")
            skip += 1
            continue

        # 输出文件名（语录命名）
        quote_name = get_quote_name(quotes, i - 1)
        output_file = output_dir / f"{quote_name}.mp4"

        print(f"[{i}/{len(processed_videos)}] {processed_file.name}")
        print(f"  原始: {original_file.name}")

        if mix_audio_ffmpeg(processed_file, original_file, output_file, bg_music, args.bg_volume):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print(f"🏁 完成: 成功 {success}, 失败 {fail}, 跳过 {skip}")
    print(f"📁 输出: {output_dir}")


if __name__ == "__main__":
    main()
