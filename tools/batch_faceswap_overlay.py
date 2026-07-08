#!/usr/bin/env python3
"""
batch_faceswap_overlay.py - 一键启动：ComfyUI批量换脸 + AI水印 + 底部语录 + 语录重命名

默认参数（可不传，自动使用）：
  --input  D:\\ai_projects\\ComfyUI\\input\\十绫Shiling
  --face   D:\\ai_projects\\ComfyUI\\input\\todo\\face\\ken4.png
  --output D:\\ai_projects\\ComfyUI\\output\\aken4\\十绫Shiling

用法:
  # 使用默认参数（零参数运行）
  python batch_faceswap_overlay.py

  # 自定义参数
  python batch_faceswap_overlay.py --input <视频目录> --face <人脸图片> --output <输出目录>

  # 跳过换脸，只做水印+语录
  python batch_faceswap_overlay.py --skip-faceswap

  # 只用国学类语录
  python batch_faceswap_overlay.py --category 国学

  # dry-run：只检查参数和连接，不提交任务
  python batch_faceswap_overlay.py --dry-run
"""

import json
import os
import random
import subprocess
import sys
import time
import uuid
import argparse
import shutil
import urllib.request
import tempfile
from pathlib import Path

# ===== 配置 =====
COMFYUI_URL = "http://127.0.0.1:8188"
SCRIPT_DIR = Path(__file__).parent
QUOTES_FILE = SCRIPT_DIR / "quotes.json"
WORKFLOW_FILE = SCRIPT_DIR.parent / "workflows" / "v1" / "batch_faceswap_video_api.json"
FONT_FILE = r"C:\Windows\Fonts\msyh.ttc"

# 换脸配置
SWAP_MODEL = "inswapper_128.onnx"
FACE_DETECT = "retinaface_resnet50"

# 水印配置
AI_TEXT = "AI生成"
AI_DURATION = 5
VIDEO_CRF = "18"
VIDEO_PRESET = "fast"

# 监控配置
POLL_INTERVAL = 10  # 秒
MAX_WAIT = 7200     # 最大等待2小时


# ===== Step 1: ComfyUI 换脸 =====

def get_video_list(input_dir):
    """获取输入目录中的视频文件"""
    videos = []
    for ext in ["*.mp4", "*.avi", "*.mov", "*.mkv"]:
        videos.extend(Path(input_dir).glob(ext))
    videos.sort()
    return videos


def load_workflow(video_relpath, face_relpath, output_prefix):
    """加载并修改工作流"""
    with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
        wf = json.load(f)
    wf["prompt"]["1"]["inputs"]["video"] = video_relpath
    wf["prompt"]["2"]["inputs"]["image"] = face_relpath
    wf["prompt"]["4"]["inputs"]["filename_prefix"] = output_prefix
    return wf


def submit_to_comfyui(workflow):
    """提交工作流到 ComfyUI"""
    data = json.dumps({
        "prompt": workflow["prompt"],
        "client_id": str(uuid.uuid4())
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


def check_queue():
    """检查队列状态"""
    resp = urllib.request.urlopen(f"{COMFYUI_URL}/queue", timeout=10)
    q = json.loads(resp.read())
    running = len(q.get("queue_running", []))
    pending = len(q.get("queue_pending", []))
    return running, pending


def queue_faceswap_jobs(input_dir, face_path, output_subdir):
    """提交所有换脸任务到 ComfyUI"""
    videos = get_video_list(input_dir)
    if not videos:
        print("❌ 未找到视频文件")
        sys.exit(1)

    input_dir = Path(input_dir)
    face_path = Path(face_path)

    # 计算 ComfyUI input 相对路径
    comfyui_input = Path(COMFYUI_URL.split("//")[1].split(":")[0])  # 这里不对
    # 用实际的 ComfyUI input 目录（从脚本位置推导）
    comfyui_input_dir = SCRIPT_DIR.parent / "input"

    # 人脸图片相对于 input 目录的路径
    face_rel = str(face_path.relative_to(comfyui_input_dir)).replace("\\", "/")
    # 视频目录相对于 input 目录的路径
    video_dir_rel = str(input_dir.relative_to(comfyui_input_dir)).replace("\\", "/")

    print(f"📹 发现 {len(videos)} 个视频")
    print(f"👤 人脸: {face_rel}")
    print(f"🔄 提交到 ComfyUI...")

    queued = []
    for i, video in enumerate(videos, 1):
        video_rel = f"{video_dir_rel}/{video.name}"
        output_prefix = f"{output_subdir}/{video.stem}"

        wf = load_workflow(video_rel, face_rel, output_prefix)
        try:
            result = submit_to_comfyui(wf)
            pid = result.get("prompt_id", "?")
            queued.append({"file": video.name, "prompt_id": pid})
            print(f"  [{i}/{len(videos)}] ✅ {video.name[:50]} → {pid[:8]}")
        except Exception as e:
            print(f"  [{i}/{len(videos)}] ❌ {video.name[:50]} → {e}")

        time.sleep(0.3)

    print(f"\n📊 已提交 {len(queued)}/{len(videos)}")
    return queued


def wait_for_completion(queued, total):
    """等待所有任务完成"""
    print(f"\n⏳ 等待换脸完成（每{POLL_INTERVAL}秒检查一次）...")
    start = time.time()

    while time.time() - start < MAX_WAIT:
        running, pending = check_queue()
        done = total - running - pending
        elapsed = int(time.time() - start)
        mins, secs = divmod(elapsed, 60)

        print(f"\r  ✅ {done}/{total} 完成 | 🔄 {running} 处理中 | ⏳ {pending} 等待 | ⏱ {mins}m{secs}s", end="", flush=True)

        if running == 0 and pending == 0:
            print(f"\n🎉 全部换脸完成！耗时 {mins}m{secs}s")
            return True

        time.sleep(POLL_INTERVAL)

    print(f"\n⏰ 超时（{MAX_WAIT}s），还有任务未完成")
    return False


# ===== FFmpeg 中文路径兼容 =====

def safe_ffmpeg_prepare(path, tmp_dir, prefix="in"):
    """将含中文的文件复制到ASCII临时路径，供FFmpeg使用。返回(安全路径, 是否需要清理)"""
    path = Path(path)
    try:
        str(path).encode('ascii')
        return str(path), False  # 已经是纯ASCII
    except UnicodeEncodeError:
        pass
    ext = path.suffix or ".mp4"
    safe = Path(tmp_dir) / f"{prefix}_{abs(hash(str(path))) & 0xFFFFFFFF:08x}{ext}"
    shutil.copy2(path, safe)
    return str(safe), True


# ===== Step 2: 水印 + 语录 + 重命名 =====

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
    """清理文件名中的非法字符"""
    illegal = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']
    for c in illegal:
        text = text.replace(c, '_')
    if len(text) > max_len:
        text = text[:max_len]
    return text.strip()


def build_overlay_cmd(faceswap_path, original_path, output_path, quote, bg_music=None, bg_volume=0.75, orig_volume=0.10):
    """构建 FFmpeg 命令：水印 + 语录 + 音频混合"""
    q_text = escape_ffmpeg(quote["text"])
    q_source = escape_ffmpeg(f"— {quote['source']}")
    fp = FONT_FILE.replace("\\", "/").replace(":", "\\:")

    # 用 f-string 拼接 enable 表达式，避免嵌套转义问题
    enable_expr = "between(t\\,0\\," + str(AI_DURATION) + ")"

    vf = (
        f"drawtext=fontfile='{fp}'"
        f":text='{AI_TEXT}'"
        f":fontsize=22:fontcolor=white:borderw=2:bordercolor=black"
        f":x=20:y=(h-th-20)"
        f":enable='{enable_expr}'"
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

    cmd = ["ffmpeg", "-y"]
    cmd.extend(["-i", str(faceswap_path)])  # 输入0: 换脸后视频
    cmd.extend(["-i", str(original_path)])  # 输入1: 原始视频（有音频）

    if bg_music and Path(bg_music).exists():
        cmd.extend(["-stream_loop", "-1", "-i", str(bg_music)])  # 输入2: 背景音乐（循环）
        # amix normalize=0 禁止自动归一化，保持原声和BGM各自音量
        filter_complex = (
            f"[0:v]{vf}[vout];"
            f"[1:a]volume={orig_volume}[orig];"
            f"[2:a]volume={bg_volume}[bg];"
            f"[orig][bg]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
        )
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
    else:
        cmd.extend(["-vf", vf])
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    cmd.extend([
        "-c:v", "libx264", "-crf", VIDEO_CRF, "-preset", VIDEO_PRESET,
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(output_path)
    ])
    return cmd


def process_and_rename(input_dir, output_dir, quotes, category=None,
                       original_dir=None, bg_music=None, bg_volume=0.75, orig_volume=0.10):
    """对换脸后的视频添加水印+语录+音频混合，并以语录命名"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 扫描换脸后的视频（排除 -audio、temp_ 等）
    video_files = []
    for ext in ["*.mp4", "*.avi", "*.mov", "*.mkv"]:
        video_files.extend(input_dir.glob(ext))
    video_files = [
        f for f in video_files
        if "-audio" not in f.name and "temp_" not in f.name
        and "with_quotes" not in f.name and "_final" not in str(f)
    ]
    video_files.sort()

    if not video_files:
        print(f"❌ 未找到视频文件: {input_dir}")
        return 0, 0

    # 构建原始视频索引（用于音频恢复）
    original_videos = {}
    if original_dir:
        orig_dir = Path(original_dir)
        for f in orig_dir.glob("*.mp4"):
            if "-audio" not in f.name and "faceswap" not in f.name:
                original_videos[f.stem] = f

    # 过滤分类
    if category:
        filtered_quotes = [q for q in quotes if q.get("category") == category]
        if not filtered_quotes:
            print(f"⚠️ 分类 '{category}' 无语录，使用全部")
            filtered_quotes = quotes
    else:
        filtered_quotes = quotes

    print(f"📹 {len(video_files)} 个视频 | 📚 {len(filtered_quotes)} 条语录")
    print(f"📁 输出: {output_dir}")
    print("=" * 60)

    # 随机打乱语录，确保不重复（如果视频数<=语录数）
    available = list(filtered_quotes)
    if len(video_files) > len(available):
        # 视频比语录多，重复填充
        available = (available * ((len(video_files) // len(available)) + 1))
    random.shuffle(available)

    success = fail = 0
    used_names = set()
    orig_list = sorted(original_videos.values()) if original_videos else []

    # 创建临时目录用于中文路径兼容
    tmp_dir = tempfile.mkdtemp(prefix="fftmp_")
    bgm_safe, _ = safe_ffmpeg_prepare(bg_music, tmp_dir, "bgm") if bg_music else (None, False)

    try:
        for i, vf in enumerate(video_files, 1):
            quote = available[i - 1]

            # 生成语录文件名，去重
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

            # 查找对应的原始视频（用于音频恢复）
            original_file = None
            if original_videos:
                if vf.stem in original_videos:
                    original_file = original_videos[vf.stem]
                elif i - 1 < len(orig_list):
                    original_file = orig_list[i - 1]

            # 准备安全路径（中文→ASCII临时文件）
            vf_safe, vf_tmp = safe_ffmpeg_prepare(vf, tmp_dir, f"v{i}")
            orig_safe, orig_tmp = safe_ffmpeg_prepare(original_file or vf, tmp_dir, f"o{i}")
            out_safe = str(Path(tmp_dir) / f"out_{i:03d}.mp4")

            if original_file:
                cmd = build_overlay_cmd(vf_safe, orig_safe, out_safe, quote, bgm_safe, bg_volume, orig_volume)
            else:
                print(f"  ⚠️ 无原始视频，跳过音频恢复")
                cmd = build_overlay_cmd(vf_safe, vf_safe, out_safe, quote, bgm_safe, bg_volume, orig_volume)

            result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")

            # 将临时输出复制到最终位置
            if result.returncode == 0 and Path(out_safe).exists() and Path(out_safe).stat().st_size > 10000:
                shutil.move(out_safe, str(out_path))
                size_mb = out_path.stat().st_size / (1024 * 1024)
                print(f"  ✅ {size_mb:.1f}MB")
                success += 1
            else:
                err = result.stderr[-200:] if result.stderr else "unknown"
                print(f"  ❌ 失败: {err[:100]}")
                fail += 1

            # 清理单次临时文件
            for tmp_path in [vf_safe if vf_tmp else None, orig_safe if orig_tmp else None]:
                if tmp_path:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
    finally:
        # 清理临时目录
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"🏁 完成: 成功 {success}, 失败 {fail}")
    return success, fail


# ===== 主程序 =====

def main():
    parser = argparse.ArgumentParser(
        description="一键启动：ComfyUI批量换脸 + AI水印 + 底部语录 + 语录重命名",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认参数
  python batch_faceswap_overlay.py

  # 自定义输入输出
  python batch_faceswap_overlay.py --input "D:\\input\\videos" --face "D:\\face.png" --output "D:\\output"

  # 跳过换脸，只做水印+语录
  python batch_faceswap_overlay.py --skip-faceswap

  # dry-run 检查
  python batch_faceswap_overlay.py --dry-run
        """
    )
    parser.add_argument("--input", default=r"D:\ai_projects\ComfyUI\input\十绫Shiling",
                        help="输入视频目录 (默认: 十绫Shiling)")
    FACE_DIR = Path(r"D:\ai_projects\ComfyUI\input\ken4\face")
    FACE_POOL = ["ken-14岁.png", "ken-16岁.png"]
    default_face = str(FACE_DIR / random.choice(FACE_POOL))
    parser.add_argument("--face", default=default_face,
                        help="人脸图片路径 (默认: ken4/face 中随机14/16岁)")
    parser.add_argument("--output", default=r"D:\ai_projects\ComfyUI\output\aken4\十绫Shiling",
                        help="最终输出目录 (默认: aken4/十绫Shiling)")
    parser.add_argument("--skip-faceswap", action="store_true", help="跳过换脸步骤（已有换脸结果时）")
    parser.add_argument("--category", help="语录分类过滤: 国学/鸡汤/热梗")
    parser.add_argument("--original-dir", help="原始视频目录（有音频的源文件，用于音频恢复）")
    parser.add_argument("--bg-music", help="背景音乐文件路径（不指定则自动从 music 目录选取）")
    parser.add_argument("--bg-volume", type=float, default=0.75, help="背景音乐音量 0.0-1.0 (默认: 0.75)")
    parser.add_argument("--orig-volume", type=float, default=0.10, help="原声音量 0.0-1.0 (默认: 0.10)")
    parser.add_argument("--no-music", action="store_true", help="不添加背景音乐，只恢复原声")
    parser.add_argument("--comfyui-url", default=COMFYUI_URL, help="ComfyUI API 地址")
    parser.add_argument("--dry-run", action="store_true", help="只检查参数和连接，不提交任务")
    args = parser.parse_args()

    comfyui_url = args.comfyui_url

    input_dir = Path(args.input)
    face_path = Path(args.face)
    output_dir = Path(args.output)
    # 计算相对于 ComfyUI output 目录的路径，作为 ComfyUI filename_prefix
    comfyui_output_dir = SCRIPT_DIR.parent / "output"
    try:
        output_subdir = str(output_dir.relative_to(comfyui_output_dir)).replace("\\", "/")
    except ValueError:
        # output_dir 不在 ComfyUI output 下，用目录名
        output_subdir = output_dir.name

    # 中间产物目录（换脸结果，带原始文件名）
    temp_dir = output_dir.parent / f"{output_dir.name}_faceswap_temp"

    print("=" * 60)
    print("🎬 一键批量换脸 + AI水印 + 语录叠加工具")
    print("=" * 60)
    print(f"📂 输入: {input_dir}")
    print(f"👤 人脸: {face_path}")
    print(f"📁 输出: {output_dir}")
    print(f"🏷️ 分类: {args.category or '全部'}")
    print(f"⏭️ 跳过换脸: {args.skip_faceswap}")
    print("=" * 60)

    # 检查依赖
    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        sys.exit(1)
    if not face_path.exists():
        print(f"❌ 人脸图片不存在: {face_path}")
        sys.exit(1)
    if not QUOTES_FILE.exists():
        print(f"❌ 语录库不存在: {QUOTES_FILE}")
        sys.exit(1)

    # dry-run 模式：只检查不执行
    if args.dry_run:
        videos = get_video_list(input_dir)
        print(f"\n🔍 DRY-RUN 模式")
        print(f"  📂 输入目录: {input_dir} ({len(videos)} 个视频)")
        print(f"  👤 人脸图片: {face_path}")
        print(f"  📁 输出目录: {output_dir}")
        print(f"  ⏭️ 跳过换脸: {args.skip_faceswap}")
        if not args.skip_faceswap:
            try:
                urllib.request.urlopen(f"{comfyui_url}/system_stats", timeout=5)
                print(f"  ✅ ComfyUI 连接正常: {comfyui_url}")
            except Exception:
                print(f"  ❌ ComfyUI 无法连接: {comfyui_url}")
                sys.exit(1)
        print(f"  📋 前5个视频:")
        for v in videos[:5]:
            print(f"    - {v.name}")
        if len(videos) > 5:
            print(f"    ... 还有 {len(videos)-5} 个")
        print(f"\n✅ dry-run 完成，所有参数有效")
        sys.exit(0)

    # Step 1: 换脸
    if not args.skip_faceswap:
        # 检查 ComfyUI
        comfyui_url_use = comfyui_url or COMFYUI_URL
        try:
            urllib.request.urlopen(f"{comfyui_url_use}/system_stats", timeout=5)
        except Exception:
            print(f"❌ ComfyUI 无法连接: {COMFYUI_URL}")
            sys.exit(1)

        videos = get_video_list(input_dir)
        print(f"\n🔄 Step 1/2: 提交换脸任务（{len(videos)} 个视频）")
        queued = queue_faceswap_jobs(input_dir, face_path, output_subdir)

        if queued:
            wait_for_completion(queued, len(videos))
        else:
            print("❌ 没有任务被提交")
            sys.exit(1)

        # 换脸结果在 output_dir（ComfyUI 直接输出到这里）
        faceswap_output = output_dir
    else:
        print(f"\n⏭️ 跳过换脸，使用已有结果: {input_dir}")
        faceswap_output = input_dir

    # Step 2: 水印 + 语录 + 音频混合 + 重命名
    print(f"\n🏷️ Step 2/2: 添加水印 + 语录 + 音频混合 + 重命名")
    quotes = load_quotes()

    # 背景音乐
    bg_music = None
    if not args.no_music:
        if args.bg_music:
            bg_music = args.bg_music
        else:
            music_dir = Path(r"D:\ai_projects\wx_channel\downloads\背景音乐\bgm")
            for ext in ["*.mp3", "*.wav", "*.flac", "*.m4a"]:
                files = sorted(music_dir.glob(ext))
                if files:
                    bg_music = str(random.choice(files))
                    break
        if bg_music:
            print(f"🎵 背景音乐: {Path(bg_music).name} (音量{args.bg_volume})")

    # 原始视频目录
    original_dir = args.original_dir or str(input_dir)

    # 最终输出到 output_dir（如果跳过换脸，输出到新目录）
    final_dir = output_dir if args.skip_faceswap else output_dir.parent / f"{output_dir.name}_final"
    if args.skip_faceswap:
        final_dir = output_dir

    success, fail = process_and_rename(
        faceswap_output, final_dir, quotes, args.category,
        original_dir=original_dir, bg_music=bg_music,
        bg_volume=args.bg_volume, orig_volume=args.orig_volume
    )

    # 清理临时目录
    if not args.skip_faceswap and temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"🎉 全部完成！")
    print(f"📁 最终输出: {final_dir}")
    print(f"📊 成功: {success} | 失败: {fail}")


if __name__ == "__main__":
    main()
