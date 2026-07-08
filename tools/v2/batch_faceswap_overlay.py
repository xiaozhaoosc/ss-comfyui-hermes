#!/usr/bin/env python3
"""
batch_faceswap_overlay.py - 一键启动：ComfyUI批量换脸 + AI水印 + 底部语录 + 语录重命名 (v2 优化并发版)

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
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 配置 =====
COMFYUI_URL = "http://127.0.0.1:8188"
SCRIPT_DIR = Path(__file__).parent
QUOTES_FILE = SCRIPT_DIR / "quotes.json"
# 自动定位上一级 workflows
WORKFLOW_FILE = SCRIPT_DIR.parent / "workflows" / "v1" / "batch_faceswap_video_api.json"

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


# ===== 辅助工具：硬件与路径检测 =====

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
    """智能查找系统中可用的中文字体"""
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",   # 微软雅黑
        r"C:\Windows\Fonts\simsun.ttc",  # 宋体
        r"C:\Windows\Fonts\simhei.ttf",  # 黑体
        r"C:\Windows\Fonts\arial.ttf"    # 英文Arial (最后fallback)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # 如果候选列表均无，搜索 Windows Fonts 文件夹中任何 ttf/ttc
    font_dir = r"C:\Windows\Fonts"
    if os.path.exists(font_dir):
        try:
            files = os.listdir(font_dir)
            for f in files:
                if f.lower().endswith(('.ttc', '.ttf')):
                    return os.path.join(font_dir, f)
        except Exception:
            pass
    return "msyh.ttc"  # 退化到硬编码，交由 FFmpeg 自己根据默认环境定位


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
    # 如果 v1 目录不存在，尝试上一级或同级
    target_wf = WORKFLOW_FILE
    if not target_wf.exists():
        # 自适应寻找
        alt_paths = [
            SCRIPT_DIR.parent / "workflows" / "v1" / "batch_faceswap_video_api.json",
            SCRIPT_DIR / "batch_faceswap_video_api.json",
            SCRIPT_DIR.parent / "batch_faceswap_video_api.json"
        ]
        for p in alt_paths:
            if p.exists():
                target_wf = p
                break

    with open(target_wf, "r", encoding="utf-8") as f:
        wf = json.load(f)
    wf["prompt"]["1"]["inputs"]["video"] = video_relpath
    wf["prompt"]["2"]["inputs"]["image"] = face_relpath
    wf["prompt"]["4"]["inputs"]["filename_prefix"] = output_prefix
    return wf


def submit_to_comfyui(workflow, comfyui_url=COMFYUI_URL):
    """提交工作流到 ComfyUI"""
    data = json.dumps({
        "prompt": workflow["prompt"],
        "client_id": str(uuid.uuid4())
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{comfyui_url}/prompt",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


def check_queue(comfyui_url=COMFYUI_URL):
    """检查队列状态"""
    resp = urllib.request.urlopen(f"{comfyui_url}/queue", timeout=10)
    q = json.loads(resp.read())
    running = len(q.get("queue_running", []))
    pending = len(q.get("queue_pending", []))
    return running, pending


def get_finished_history(comfyui_url=COMFYUI_URL):
    """从 ComfyUI 获取已完成的历史 Prompt ID"""
    try:
        resp = urllib.request.urlopen(f"{comfyui_url}/history", timeout=10)
        hist = json.loads(resp.read())
        return set(hist.keys())
    except Exception as e:
        print(f"\n⚠️ 获取 ComfyUI 历史记录失败: {e}")
        return set()


def queue_faceswap_jobs(input_dir, face_path, output_subdir, comfyui_url=COMFYUI_URL):
    """提交所有换脸任务到 ComfyUI"""
    videos = get_video_list(input_dir)
    if not videos:
        print("❌ 未找到视频文件")
        sys.exit(1)

    input_dir = Path(input_dir)
    face_path = Path(face_path)

    # 用实际的 ComfyUI input 目录（从脚本位置向上推导）
    comfyui_input_dir = SCRIPT_DIR.parent.parent / "input"
    if not comfyui_input_dir.exists():
        comfyui_input_dir = SCRIPT_DIR.parent / "input"

    # 人脸图片相对于 input 目录的路径
    try:
        face_rel = str(face_path.relative_to(comfyui_input_dir)).replace("\\", "/")
    except ValueError:
        # 如果人脸图不在 ComfyUI input 目录中，直接拷贝过去
        print(f"⚠️ 人脸图片不在 ComfyUI 输入目录下，正在自动拷贝...")
        target_face_dir = comfyui_input_dir / "todo" / "face"
        target_face_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(face_path, target_face_dir / face_path.name)
        face_rel = f"todo/face/{face_path.name}"

    # 视频目录相对于 input 目录的路径
    try:
        video_dir_rel = str(input_dir.relative_to(comfyui_input_dir)).replace("\\", "/")
    except ValueError:
        # 如果输入视频目录不在 ComfyUI input 下，需要报错或自动复制
        print(f"❌ 错误: 输入视频目录 {input_dir} 必须位于 ComfyUI input 文件夹中")
        sys.exit(1)

    print(f"📹 发现 {len(videos)} 个视频")
    print(f"👤 人脸相对路径: {face_rel}")
    print(f"🔄 提交到 ComfyUI 服务: {comfyui_url}...")

    queued = []
    for i, video in enumerate(videos, 1):
        video_rel = f"{video_dir_rel}/{video.name}"
        output_prefix = f"{output_subdir}/{video.stem}"

        wf = load_workflow(video_rel, face_rel, output_prefix)
        try:
            result = submit_to_comfyui(wf, comfyui_url)
            pid = result.get("prompt_id", "?")
            queued.append({"file": video.name, "prompt_id": pid})
            print(f"  [{i}/{len(videos)}] ✅ {video.name[:50]} → {pid[:8]}")
        except Exception as e:
            print(f"  [{i}/{len(videos)}] ❌ {video.name[:50]} → {e}")

        time.sleep(0.3)

    print(f"\n📊 已成功提交 {len(queued)}/{len(videos)} 个任务")
    return queued


def wait_for_completion(queued, total, comfyui_url=COMFYUI_URL):
    """精准等待提交的特定任务全部完成"""
    print(f"\n⏳ 等待所提交的 {total} 个换脸任务完成（精准 ID 监控，每 {POLL_INTERVAL} 秒检查一次）...")
    start = time.time()
    
    target_ids = {job["prompt_id"] for job in queued if job["prompt_id"] != "?"}
    if not target_ids:
        print("⚠️ 没有有效的 prompt_id 需要监控")
        return True

    while time.time() - start < MAX_WAIT:
        finished_ids = get_finished_history(comfyui_url)
        done_targets = target_ids.intersection(finished_ids)
        done = len(done_targets)
        
        try:
            running, pending = check_queue(comfyui_url)
        except Exception:
            running, pending = 0, 0
            
        elapsed = int(time.time() - start)
        mins, secs = divmod(elapsed, 60)

        print(f"\r  🎯 进度: {done}/{total} 已落盘 | 🖥️ 队列处理中: {running} | ⏱️ 耗时: {mins}m{secs}s", end="", flush=True)

        if len(done_targets) == len(target_ids):
            print(f"\n🎉 提交的 {total} 个换脸任务已全部确认在 ComfyUI 中完成！总耗时 {mins}m{secs}s")
            return True

        time.sleep(POLL_INTERVAL)

    print(f"\n⏰ 轮询超时（{MAX_WAIT}s），部分任务可能仍在队列中或已异常终止。")
    return False


# ===== FFmpeg 中文路径兼容 =====

def safe_ffmpeg_prepare(path, tmp_dir, prefix="in"):
    """将含中文的文件复制到ASCII临时路径，供FFmpeg使用。返回(安全路径, 是否需要清理)"""
    if not path:
        return None, False
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
    # 如果 quotes.json 丢失，自动自适应寻找
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
    """清理文件名中的非法字符"""
    illegal = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']
    for c in illegal:
        text = text.replace(c, '_')
    if len(text) > max_len:
        text = text[:max_len]
    return text.strip()


def build_overlay_cmd(faceswap_path, original_path, output_path, quote, bg_music=None, bg_volume=0.75, orig_volume=0.10, use_nvenc=False):
    """构建 FFmpeg 命令：水印 + 语录 + 音频混合（支持硬件加速检测）"""
    q_text = escape_ffmpeg(quote["text"])
    q_source = escape_ffmpeg(f"— {quote['source']}")
    
    font_path = get_available_font()
    fp = font_path.replace("\\", "/").replace(":", "\\:")

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

    # 优先使用 NVENC NVIDIA GPU 硬件转码加速
    if use_nvenc:
        cmd.extend([
            "-c:v", "h264_nvenc", "-cq", "20", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(output_path)
        ])
    else:
        cmd.extend([
            "-c:v", "libx264", "-crf", VIDEO_CRF, "-preset", VIDEO_PRESET,
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(output_path)
        ])
    return cmd


def process_single_video(item):
    """并发处理单视频的水印+语录+音频混写逻辑"""
    i, vf, quote, original_file, bgm_safe, bg_volume, orig_volume, tmp_dir, output_dir, use_nvenc = item
    base_name = sanitize_filename(quote["text"])
    out_name = f"{base_name}.mp4"
    out_path = output_dir / out_name
    
    # 准备安全路径（中文→ASCII临时文件）
    vf_safe, vf_tmp = safe_ffmpeg_prepare(vf, tmp_dir, f"v_{i}")
    orig_safe, orig_tmp = safe_ffmpeg_prepare(original_file or vf, tmp_dir, f"o_{i}")
    out_safe = str(Path(tmp_dir) / f"out_{i:08x}.mp4")  # 独立文件名避免并发读写冲突
    
    print(f"🎬 [并发任务 {i}] 提交处理: {vf.name} -> {out_name}")
    
    if original_file:
        cmd = build_overlay_cmd(vf_safe, orig_safe, out_safe, quote, bgm_safe, bg_volume, orig_volume, use_nvenc)
    else:
        cmd = build_overlay_cmd(vf_safe, vf_safe, out_safe, quote, bgm_safe, bg_volume, orig_volume, use_nvenc)
        
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    
    success = False
    # 将临时输出复制到最终位置
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
        
    # 清理单次临时文件
    for tmp_path in [vf_safe if vf_tmp else None, orig_safe if orig_tmp else None]:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
    return success


def process_and_rename(input_dir, output_dir, quotes, category=None,
                        original_dir=None, bg_music=None, bg_volume=0.75, orig_volume=0.10):
    """使用多线程并发对换脸后的视频添加水印+语录+音频混合，并以语录命名"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 扫描换脸后的视频
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
        if orig_dir.exists():
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
    print(f"📁 最终输出目录: {output_dir}")
    print("=" * 60)

    # 随机打乱语录，确保不重复
    available = list(filtered_quotes)
    if len(video_files) > len(available):
        available = (available * ((len(video_files) // len(available)) + 1))
    random.shuffle(available)

    orig_list = sorted(original_videos.values()) if original_videos else []

    # 创建临时目录用于中文路径兼容
    tmp_dir = tempfile.mkdtemp(prefix="fftmp_")
    bgm_safe, _ = safe_ffmpeg_prepare(bg_music, tmp_dir, "bgm") if bg_music else (None, False)

    # 预检显卡加速
    use_nvenc = check_nvenc_support()
    print(f"⚡ 编解码硬件加速检测: {'[启用 NVIDIA NVENC 硬件加速转码]' if use_nvenc else '[使用 CPU 软解软编]'}")

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
        
        original_file = None
        if original_videos:
            if vf.stem in original_videos:
                original_file = original_videos[vf.stem]
            elif i - 1 < len(orig_list):
                original_file = orig_list[i - 1]

        tasks.append((i, vf, quote, original_file, bgm_safe, bg_volume, orig_volume, tmp_dir, output_dir, use_nvenc))

    success = fail = 0
    # 并发转码，默认为 4 线程，防止过高线程导致显存或 CPU 过载
    max_workers = min(4, os.cpu_count() or 4)
    print(f"🚀 开始并发多线程 FFmpeg 处理，线程数: {max_workers}...")
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
                    print(f"⚠️ 线程处理抛出未捕获异常: {e}")
                    fail += 1
    finally:
        # 清理总临时目录
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"🏁 批量 FFmpeg 处理完毕: 成功 {success}, 失败 {fail}")
    return success, fail


# ===== 主程序 =====

def main():
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
            
    parser = argparse.ArgumentParser(
        description="一键启动：ComfyUI批量换脸 + AI水印 + 底部语录 + 语录重命名",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认参数
  python batch_faceswap_overlay.py
        """
    )
    parser.add_argument("--input", default=r"D:\ai_projects\ComfyUI\input\十绫Shiling",
                        help="输入视频目录")
    
    FACE_DIR = Path(r"D:\ai_projects\ComfyUI\input\ken4\face")
    FACE_POOL = ["ken-14岁.png", "ken-16岁.png"]
    # 智能检查 FACE_DIR
    if not FACE_DIR.exists():
        FACE_DIR = SCRIPT_DIR.parent / "input" / "ken4" / "face"
        if not FACE_DIR.exists():
            FACE_DIR = SCRIPT_DIR.parent.parent / "input" / "ken4" / "face"
            
    if FACE_DIR.exists():
        try:
            available_faces = [f for f in os.listdir(FACE_DIR) if f.lower().endswith(('.png', '.jpg'))]
            if available_faces:
                default_face = str(FACE_DIR / random.choice(available_faces))
            else:
                default_face = str(FACE_DIR / FACE_POOL[0])
        except Exception:
            default_face = str(FACE_DIR / FACE_POOL[0])
    else:
        default_face = r"D:\ai_projects\ComfyUI\input\ken4\face\ken-14岁.png"

    parser.add_argument("--face", default=default_face,
                        help="人脸图片路径")
    parser.add_argument("--output", default=r"D:\ai_projects\ComfyUI\output\aken4\十绫Shiling",
                        help="最终输出目录")
    parser.add_argument("--skip-faceswap", action="store_true", help="跳过换脸步骤")
    parser.add_argument("--category", help="语录分类过滤: 国学/鸡汤/热梗")
    parser.add_argument("--original-dir", help="原始视频目录（有音频的源文件，用于音频恢复）")
    parser.add_argument("--bg-music", help="背景音乐文件路径")
    parser.add_argument("--bg-volume", type=float, default=0.75, help="背景音乐音量 (默认: 0.75)")
    parser.add_argument("--orig-volume", type=float, default=0.10, help="原声音量 (默认: 0.10)")
    parser.add_argument("--no-music", action="store_true", help="不添加背景音乐，只恢复原声")
    parser.add_argument("--comfyui-url", default=COMFYUI_URL, help="ComfyUI API 地址")
    parser.add_argument("--dry-run", action="store_true", help="只检查参数和连接，不提交任务")
    args = parser.parse_args()

    comfyui_url = args.comfyui_url

    input_dir = Path(args.input)
    face_path = Path(args.face)
    output_dir = Path(args.output)
    
    # 动态确定 ComfyUI 根下的 output 目录，保证映射前缀相对路径
    comfyui_output_dir = SCRIPT_DIR.parent.parent / "output"
    if not comfyui_output_dir.exists():
        comfyui_output_dir = SCRIPT_DIR.parent / "output"
        
    try:
        output_subdir = str(output_dir.relative_to(comfyui_output_dir)).replace("\\", "/")
    except ValueError:
        output_subdir = output_dir.name

    # 中间产物目录（换脸结果，带原始文件名）
    temp_dir = output_dir.parent / f"{output_dir.name}_faceswap_temp"

    print("=" * 60)
    print("🎬 一键批量换脸 + AI水印 + 语录叠加工具 (v2 并发版)")
    print("=" * 60)
    print(f"📂 输入视频目录: {input_dir}")
    print(f"👤 换脸图片目标: {face_path}")
    print(f"📁 最终输出目录: {output_dir}")
    print(f"🏷️ 语录分类过滤: {args.category or '全部'}")
    print(f"⏭️ 是否跳过换脸: {args.skip_faceswap}")
    print("=" * 60)

    # 检查依赖
    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        sys.exit(1)
    if not args.skip_faceswap and not face_path.exists():
        print(f"❌ 人脸图片不存在: {face_path}")
        sys.exit(1)
    
    # 智能定位 quotes.json
    quotes_exist = QUOTES_FILE.exists()
    if not quotes_exist:
        for p in [SCRIPT_DIR.parent / "quotes.json", SCRIPT_DIR.parent.parent / "quotes.json"]:
            if p.exists():
                quotes_exist = True
                break
    if not quotes_exist:
        print(f"❌ 语录库 quotes.json 不存在")
        sys.exit(1)

    # dry-run 模式
    if args.dry_run:
        videos = get_video_list(input_dir)
        print(f"\n🔍 DRY-RUN 模式检测中...")
        print(f"  📂 输入视频: {input_dir} ({len(videos)} 个视频)")
        print(f"  👤 换脸人脸: {face_path}")
        print(f"  📁 目标输出: {output_dir}")
        print(f"  ⏭️ 是否跳过: {args.skip_faceswap}")
        if not args.skip_faceswap:
            try:
                urllib.request.urlopen(f"{comfyui_url}/system_stats", timeout=5)
                print(f"  ✅ ComfyUI 加速服务连接成功: {comfyui_url}")
            except Exception:
                print(f"  ❌ ComfyUI 服务未运行或不可访问: {comfyui_url}")
                sys.exit(1)
        print(f"  📋 前 5 个视频清单:")
        for v in videos[:5]:
            print(f"    - {v.name}")
        if len(videos) > 5:
            print(f"    ... 共 {len(videos)} 个视频")
        print(f"\n✅ dry-run 检测完毕，所有配置合法。")
        sys.exit(0)

    # Step 1: 换脸
    if not args.skip_faceswap:
        # 检查 ComfyUI
        try:
            urllib.request.urlopen(f"{comfyui_url}/system_stats", timeout=5)
        except Exception:
            print(f"❌ ComfyUI 服务连接失败: {comfyui_url}，请先运行 start_comfyui.bat 重启服务")
            sys.exit(1)

        videos = get_video_list(input_dir)
        print(f"\n🔄 Step 1/2: 提交换脸任务到 ComfyUI ({len(videos)} 个视频)")
        queued = queue_faceswap_jobs(input_dir, face_path, output_subdir, comfyui_url)

        if queued:
            wait_for_completion(queued, len(videos), comfyui_url)
        else:
            print("❌ 没有任务提交成功")
            sys.exit(1)

        # 换脸结果输出在 output_dir
        faceswap_output = output_dir
    else:
        print(f"\n⏭️ 跳过换脸，直接对已有结果后处理: {input_dir}")
        faceswap_output = input_dir

    # Step 2: 水印 + 语录 + 音频混合 + 重命名
    print(f"\n🏷️ Step 2/2: 进行并发水印 + 语录 + 音频混合并以语录重命名")
    quotes = load_quotes()

    # 背景音乐选择与 Fallback
    bg_music = None
    if not args.no_music:
        if args.bg_music:
            bg_music = args.bg_music
        else:
            # 智能检测三个可能的背景音乐目录
            music_dirs = [
                Path(r"D:\ai_projects\wx_channel\downloads\背景音乐\bgm"),
                Path(r"D:\ai_projects\ComfyUI\input\music"),
                SCRIPT_DIR.parent.parent / "input" / "music",
                SCRIPT_DIR.parent / "input" / "music"
            ]
            for m_dir in music_dirs:
                if m_dir.exists():
                    for ext in ["*.mp3", "*.wav", "*.flac", "*.m4a"]:
                        files = sorted(m_dir.glob(ext))
                        if files:
                            bg_music = str(random.choice(files))
                            break
                if bg_music:
                    break
        if bg_music:
            print(f"🎵 背景音乐选用: {Path(bg_music).name} (音量: {args.bg_volume})")
        else:
            print("⚠️ 未发现可用的背景音乐文件，将只恢复原声音频")

    # 原始视频目录
    original_dir = args.original_dir or str(input_dir)

    # 最终输出位置
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
    print(f"🎉 批量工作流处理完毕！")
    print(f"📁 最终成品目录: {final_dir}")
    print(f"📊 成功: {success} | 失败: {fail}")


if __name__ == "__main__":
    main()
