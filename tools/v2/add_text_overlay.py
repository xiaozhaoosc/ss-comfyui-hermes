#!/usr/bin/env python3
"""
add_text_overlay.py - 视频后处理：AI生成水印 + 底部语录 + 语录重命名 (v2 优化并发版)
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
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = Path(__file__).parent
QUOTES_FILE = SCRIPT_DIR / "quotes.json"

AI_TEXT = "AI生成"
AI_DURATION = 5
VIDEO_CRF = "18"
VIDEO_PRESET = "fast"


# ===== 辅助工具 =====

def check_nvenc_support():
    """检测 ffmpeg 是否支持 NVIDIA NVENC 硬件加速编码"""
    try:
        res = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        if 'h264_nvenc' in res.stdout:
            return True
    except Exception:
        pass
    return False


def get_available_font():
    """智能查找系统中可用的中文字体路径"""
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",   # 微软雅黑
        r"C:\Windows\Fonts\simsun.ttc",  # 宋体
        r"C:\Windows\Fonts\simhei.ttf",  # 黑体
        r"C:\Windows\Fonts\arial.ttf"    # 英文Arial (最后fallback)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    font_dir = r"C:\Windows\Fonts"
    if os.path.exists(font_dir):
        try:
            files = os.listdir(font_dir)
            for f in files:
                if f.lower().endswith(('.ttc', '.ttf')):
                    return os.path.join(font_dir, f)
        except Exception:
            pass
    return "msyh.ttc"


def safe_ffmpeg_prepare(path, tmp_dir, prefix="in"):
    """将含中文的文件复制到ASCII临时路径，供FFmpeg使用。返回(安全路径, 是否需要清理)"""
    if not path:
        return None, False
    path = Path(path)
    try:
        str(path).encode('ascii')
        return str(path), False
    except UnicodeEncodeError:
        pass
    ext = path.suffix or ".mp4"
    safe = Path(tmp_dir) / f"{prefix}_{abs(hash(str(path))) & 0xFFFFFFFF:08x}{ext}"
    shutil.copy2(path, safe)
    return str(safe), True


def load_quotes():
    target_q = QUOTES_FILE
    if not target_q.exists():
        alt_paths = [
            SCRIPT_DIR.parent / "quotes.json",
            SCRIPT_DIR.parent.parent / "quotes.json"
        ]
        for p in alt_paths:
            if p.exists():
                target_q = p
                break
    with open(target_q, "r", encoding="utf-8") as f:
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


def build_cmd(input_path, output_path, quote, use_nvenc=False):
    q_text = escape_ffmpeg(quote["text"])
    q_source = escape_ffmpeg(f"— {quote['source']}")
    
    font_path = get_available_font()
    fp = font_path.replace("\\", "/").replace(":", "\\:")

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

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", vf
    ]

    if use_nvenc:
        cmd.extend([
            "-c:v", "h264_nvenc", "-cq", "20", "-preset", "fast",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path)
        ])
    else:
        cmd.extend([
            "-c:v", "libx264", "-crf", VIDEO_CRF, "-preset", VIDEO_PRESET,
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path)
        ])
    return cmd


def process_single_video(item):
    """单视频处理 worker"""
    i, vf, quote, tmp_dir, output_dir, use_nvenc = item
    base_name = sanitize_filename(quote["text"])
    out_name = f"{base_name}.mp4"
    out_path = output_dir / out_name
    
    # ASCII 中文路径安全转换
    vf_safe, vf_tmp = safe_ffmpeg_prepare(vf, tmp_dir, f"v_{i}")
    out_safe = str(Path(tmp_dir) / f"out_{i:08x}.mp4")
    
    print(f"🎬 [并发任务 {i}] 提交处理: {vf.name} -> {out_name}")
    cmd = build_cmd(vf_safe, out_safe, quote, use_nvenc)
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    
    success = False
    if result.returncode == 0 and Path(out_safe).exists() and Path(out_safe).stat().st_size > 10000:
        try:
            shutil.move(out_safe, str(out_path))
            size_mb = out_path.stat().st_size / (1024 * 1024)
            print(f"✅ [并发任务 {i} 成功] {out_name} ({size_mb:.1f}MB)")
            success = True
        except Exception as e:
            print(f"❌ [并发任务 {i} 失败] {vf.name} -> 文件保存失败: {e}")
    else:
        err = result.stderr[-200:] if result.stderr else "unknown error"
        print(f"❌ [并发任务 {i} 失败] {vf.name} -> {err.strip()[:100]}")
        
    # 清理本次的临时文件
    if vf_tmp and vf_safe:
        try: Path(vf_safe).unlink(missing_ok=True)
        except Exception: pass
        
    return success


def main():
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
            
    parser = argparse.ArgumentParser(description="视频后处理：AI生成水印 + 底部语录 + 语录重命名 (v2 并发版)")
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
    print(f"📁 最终输出目录: {output_dir}")
    print("=" * 60)

    # 随机分配语录，尽量不重复
    available = list(quotes)
    if len(video_files) > len(available):
        available = (available * ((len(video_files) // len(available)) + 1))
    random.shuffle(available)

    # 预检 NVENC 硬件加速
    use_nvenc = check_nvenc_support()
    print(f"⚡ 编解码硬件加速检测: {'[启用 NVIDIA NVENC 硬件加速转码]' if use_nvenc else '[使用 CPU 软解软编]'}")

    tmp_dir = tempfile.mkdtemp(prefix="fftmp_")
    
    tasks = []
    used_names = set()
    for i, vf in enumerate(video_files, 1):
        quote = available[i - 1]
        base_name = sanitize_filename(quote["text"])
        out_name = f"{base_name}.mp4"
        counter = 1
        while out_name in used_names:
            out_name = f"{base_name}_{counter}.mp4"
            counter += 1
        used_names.add(out_name)
        
        tasks.append((i, vf, quote, tmp_dir, output_dir, use_nvenc))

    success = fail = 0
    max_workers = min(4, os.cpu_count() or 4)
    print(f"🚀 开始并发多线程 FFmpeg 叠加，线程数: {max_workers}...")
    print("=" * 60)

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_video, task): task for task in tasks}
            for future in as_completed(futures):
                try:
                    res = future.result()
                    if res:
                        success += 1
                    else:
                        fail += 1
                except Exception as e:
                    print(f"⚠️ 线程抛出未捕获异常: {e}")
                    fail += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"🏁 批量 FFmpeg 叠加完毕: 成功 {success}, 失败 {fail}")
    print(f"📁 输出目录: {output_dir}")


if __name__ == "__main__":
    main()
