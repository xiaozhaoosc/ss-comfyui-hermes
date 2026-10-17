#!/usr/bin/env python3
"""
batch_faceswap_watermark.py - 批量换脸 + AI水印 + 保留原BGM（不含语录）

基于 batch_faceswap_overlay.py 复制精简：只保留「换脸 → AI水印 → 原声/原BGM」，
去掉底部语录叠加与语录重命名。输出文件名沿用源视频名（去掉 VHS 的 _00001 尾缀）。

默认参数（可不传，自动使用）：
  --input  D:\\ai_projects\\ComfyUI\\input\\十绫Shiling
  --face   D:\\ai_projects\\ComfyUI\\input\\ken4\\face\\ken
  --output D:\\ai_projects\\ComfyUI\\output\\aken4\\十绫Shiling

用法:
  # 零参数运行
  python batch_faceswap_watermark.py

  # 自定义
  python batch_faceswap_watermark.py --input <视频目录> --face <人脸图片> --output <输出目录>

  # 跳过换脸，只加水印（已有换脸结果）
  python batch_faceswap_watermark.py --skip-faceswap

  # 额外混入背景音乐（默认不加，保持原BGM）
  python batch_faceswap_watermark.py --bg-music <mp3> --bg-volume 0.15

  # 提交与轮询解耦（长任务抗中断）
  python batch_faceswap_watermark.py --submit-only
  python batch_faceswap_watermark.py --poll-only
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid
import argparse
import shutil
import urllib.request
import tempfile
from pathlib import Path

# 本机 8188 会被系统代理劫持（os.environ 里的 http_proxy），本地请求一律绕开
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ===== 配置 =====
COMFYUI_URL = "http://127.0.0.1:8188"
SCRIPT_DIR = Path(__file__).parent
WORKFLOW_FILE = SCRIPT_DIR.parent / "workflows" / "v1" / "batch_faceswap_video_api.json"
FONT_FILE = r"C:\Windows\Fonts\msyh.ttc"

# 水印配置
AI_TEXT = "AI生成"
AI_DURATION = 5
VIDEO_CRF = "18"
VIDEO_PRESET = "fast"

# 监控配置
POLL_INTERVAL = 10
MAX_WAIT = 14400


# ===== Step 1: ComfyUI 换脸（与 batch_faceswap_overlay 一致） =====

def get_video_list(input_dir):
    videos = []
    for ext in ["*.mp4", "*.avi", "*.mov", "*.mkv"]:
        videos.extend(Path(input_dir).glob(ext))
    videos.sort()
    return videos


def probe_fps(video_path):
    """读取视频真实帧率——VHS_VideoCombine 的 frame_rate 必须与源一致,否则成片变速"""
    candidates = ['ffprobe', r'C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe']
    for exe in candidates:
        try:
            r = subprocess.run(
                [exe, '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', str(video_path)],
                capture_output=True, timeout=30)
            raw = r.stdout.decode('utf-8', 'replace').strip()
            if not raw:
                continue
            if '/' in raw:
                num, den = raw.split('/')
                fps = float(num) / float(den) if float(den) else 30.0
            else:
                fps = float(raw)
            return round(fps, 3) if 1 <= fps <= 240 else 30.0
        except Exception:
            continue
    return 30.0


def load_workflow(video_relpath, face_relpath, output_prefix, fps=30):
    with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
        wf = json.load(f)
    wf["prompt"]["1"]["inputs"]["video"] = video_relpath
    wf["prompt"]["2"]["inputs"]["image"] = face_relpath
    wf["prompt"]["4"]["inputs"]["filename_prefix"] = output_prefix
    wf["prompt"]["4"]["inputs"]["frame_rate"] = fps
    return wf


def submit_to_comfyui(workflow):
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
    last_err = None
    for _ in range(3):
        try:
            resp = urllib.request.urlopen(f"{COMFYUI_URL}/queue", timeout=30)
            q = json.loads(resp.read())
            return len(q.get("queue_running", [])), len(q.get("queue_pending", []))
        except Exception as e:
            last_err = e
            time.sleep(5)
    raise last_err


def check_prompt_status(prompt_id):
    try:
        resp = urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}", timeout=30)
        entry = json.loads(resp.read()).get(prompt_id) or {}
        return entry.get("status", {}).get("status_str")
    except Exception:
        return None


def comfyui_output_subdir(output_dir):
    comfyui_output_dir = SCRIPT_DIR.parent / "output"
    try:
        return str(Path(output_dir).relative_to(comfyui_output_dir)).replace("\\", "/")
    except ValueError:
        return Path(output_dir).name


def faceswap_done(faceswap_dir, stem):
    faceswap_dir = Path(faceswap_dir)
    if not faceswap_dir.exists():
        return False
    return any(f.name.startswith(stem + "_00001") and f.suffix == ".mp4"
               and "-audio" not in f.name for f in faceswap_dir.iterdir())


def load_order(order_file, videos):
    if not order_file:
        return videos
    names = [os.path.basename(l.strip())
             for l in Path(order_file).read_text(encoding="utf-8").splitlines() if l.strip()]
    head = sorted((v for v in videos if v.name in names), key=lambda v: names.index(v.name))
    tail = [v for v in videos if v.name not in names]
    return head + tail


def load_manifest(manifest_path):
    p = Path(manifest_path)
    if not p.exists():
        return []
    seen = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        pid = e.get("prompt_id")
        if pid and pid != "?":
            seen[pid] = {"file": e.get("file", "?"), "prompt_id": pid}
    return list(seen.values())


def queue_faceswap_jobs(input_dir, face_path, output_dir, limit=0, order_file=None):
    input_dir = Path(input_dir)
    face_path = Path(face_path)
    output_dir = Path(output_dir)

    output_subdir = comfyui_output_subdir(output_dir)
    faceswap_dir = SCRIPT_DIR.parent / "output" / output_subdir
    manifest = faceswap_dir.parent / "_submit_manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)

    comfyui_input_dir = SCRIPT_DIR.parent / "input"
    face_rel = str(face_path.relative_to(comfyui_input_dir)).replace("\\", "/")
    video_dir_rel = str(input_dir.relative_to(comfyui_input_dir)).replace("\\", "/")

    videos = load_order(order_file, get_video_list(input_dir))
    if not videos:
        print("❌ 未找到视频文件")
        sys.exit(1)

    todo = [v for v in videos if not faceswap_done(faceswap_dir, v.stem)]
    if len(todo) < len(videos):
        print(f"⏭️ 跳过已产出 {len(videos) - len(todo)} 个")
    if limit > 0:
        todo = todo[:limit]
    if not todo:
        print("✅ 无需提交（全部已有产物或超出 limit）")
        return []

    print(f"📹 本批提交 {len(todo)} 个视频（输入共 {len(videos)} 个）")
    print(f"👤 人脸: {face_rel}")
    print(f"🔄 提交到 ComfyUI...")

    queued = []
    for i, video in enumerate(todo, 1):
        video_rel = f"{video_dir_rel}/{video.name}"
        output_prefix = f"{output_subdir}/{video.stem}"

        fps = probe_fps(video)
        wf = load_workflow(video_rel, face_rel, output_prefix, fps=fps)
        print(f"  🎞️ {video.name[:40]} — 源帧率 {fps} fps")
        try:
            result = submit_to_comfyui(wf)
            pid = result.get("prompt_id")
            if not pid:
                print(f"  [{i}/{len(todo)}] ⚠️ 无 prompt_id，跳过")
                continue
            queued.append({"file": video.name, "prompt_id": pid})
            with open(manifest, "a", encoding="utf-8") as fp:
                fp.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                                     "face": face_rel, "file": video.name,
                                     "prompt_id": pid}, ensure_ascii=False) + "\n")
            print(f"  [{i}/{len(todo)}] ✅ {video.name[:50]} → {pid[:8]}")
        except Exception as e:
            print(f"  [{i}/{len(todo)}] ❌ {video.name[:50]} → {e}")

        time.sleep(0.3)

    print(f"\n📊 已提交 {len(queued)}/{len(todo)}")
    return queued


def wait_for_completion(queued, total):
    print(f"\n⏳ 等待换脸完成（每{POLL_INTERVAL}秒查一次 /history）...")
    start = time.time()
    remaining = {q["prompt_id"]: q["file"] for q in queued
                 if q.get("prompt_id") and q["prompt_id"] != "?"}
    done_files, failed = [], []

    while time.time() - start < MAX_WAIT:
        for pid in list(remaining):
            status = check_prompt_status(pid)
            if status == "success":
                done_files.append(remaining.pop(pid))
            elif status == "error":
                failed.append(remaining.pop(pid))
        elapsed = int(time.time() - start)
        mins, secs = divmod(elapsed, 60)
        try:
            running, pending = check_queue()
            queue_info = f" | 🔄 {running} 处理中 | ⏳ {pending} 等待"
        except Exception as e:
            queue_info = f" | ⚠️ 队列查询失败: {e}"
        print(f"\r  ✅ {len(done_files)}/{total} | ❌ {len(failed)}{queue_info} | ⏱ {mins}m{secs}s",
              end="", flush=True)

        if not remaining:
            print(f"\n🏁 本批完成: 成功 {len(done_files)} | 失败 {len(failed)} | 耗时 {mins}m{secs}s")
            for f in failed:
                print(f"  ❌ {f}")
            return not failed
        time.sleep(POLL_INTERVAL)

    print(f"\n⏰ 超时（{MAX_WAIT}s），还剩 {len(remaining)} 个未完成")
    for f in remaining.values():
        print(f"  ⏰ {f}")
    return False


# ===== FFmpeg 中文路径兼容 =====

def safe_ffmpeg_prepare(path, tmp_dir, prefix="in"):
    """将含中文的文件复制到ASCII临时路径，供FFmpeg使用。返回(安全路径, 是否需要清理)"""
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


# ===== Step 2: AI水印 + 保留原BGM =====

def escape_ffmpeg(text):
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "'\\''")
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def build_watermark_cmd(faceswap_path, original_path, output_path,
                        bg_music=None, bg_volume=0.15):
    """构建 FFmpeg 命令：仅 AI水印；原声(原BGM)保持满音量，默认不加背景音乐"""
    fp = FONT_FILE.replace("\\", "/").replace(":", "\\:")
    enable_expr = "between(t\\,0\\," + str(AI_DURATION) + ")"

    vf = (
        f"drawtext=fontfile='{fp}'"
        f":text='{escape_ffmpeg(AI_TEXT)}'"
        f":fontsize=22:fontcolor=white:borderw=2:bordercolor=black"
        f":x=20:y=(h-th-20)"
        f":enable='{enable_expr}'"
    )

    cmd = ["ffmpeg", "-y"]
    cmd.extend(["-i", str(faceswap_path)])   # 输入0: 换脸后视频
    cmd.extend(["-i", str(original_path)])   # 输入1: 原始视频（原BGM）

    if bg_music and Path(bg_music).exists():
        cmd.extend(["-stream_loop", "-1", "-i", str(bg_music)])  # 输入2: 额外BGM（可选）
        filter_complex = (
            f"[0:v]{vf}[vout];"
            f"[1:a]volume=1.0[orig];"          # 原声/BGM 满音量
            f"[2:a]volume={bg_volume}[bg];"
            f"[orig][bg]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
        )
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
    else:
        cmd.extend(["-vf", vf])
        cmd.extend(["-map", "0:v", "-map", "1:a"])  # 原声完整保留

    cmd.extend([
        "-c:v", "libx264", "-crf", VIDEO_CRF, "-preset", VIDEO_PRESET,
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(output_path)
    ])
    return cmd


def process_watermark(input_dir, output_dir, original_dir=None,
                      bg_music=None, bg_volume=0.15):
    """对换脸后的视频仅加 AI 水印（保留原BGM），输出沿用源视频名"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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

    done_map_path = output_dir / "_done_map.json"
    done_stems = set()
    if done_map_path.exists():
        try:
            done_stems = set(json.loads(done_map_path.read_text(encoding="utf-8")))
        except Exception:
            done_stems = set()
    todo_files = [f for f in video_files if f.stem not in done_stems]
    if not todo_files:
        print("✅ 全部已处理后处理，无需处理")
        return 0, 0
    if len(todo_files) < len(video_files):
        print(f"⏭️ 跳过已处理 {len(video_files) - len(todo_files)} 个")
    video_files = todo_files

    original_videos = {}
    if original_dir:
        orig_dir = Path(original_dir)
        for f in orig_dir.glob("*.mp4"):
            if "-audio" not in f.name and "faceswap" not in f.name:
                original_videos[f.stem] = f

    print(f"📹 {len(video_files)} 个视频")
    print(f"📁 输出: {output_dir}")
    print("=" * 60)

    success = fail = 0
    # 预置已有文件，避免同名产物被静默覆盖
    used_names = {f.name for f in output_dir.glob("*.mp4")}
    orig_list = sorted(original_videos.values()) if original_videos else []

    tmp_dir = tempfile.mkdtemp(prefix="fftmp_")
    bgm_safe, _ = safe_ffmpeg_prepare(bg_music, tmp_dir, "bgm") if bg_music else (None, False)

    try:
        for i, vf in enumerate(video_files, 1):
            # 输出名：去掉 VHS 的 _00001 尾缀，沿用源视频名
            clean_stem = re.sub(r"_\d{5}$", "", vf.stem)
            out_name = f"{clean_stem}.mp4"
            counter = 1
            while out_name in used_names:
                out_name = f"{clean_stem}_{counter}.mp4"
                counter += 1
            used_names.add(out_name)

            out_path = output_dir / out_name
            print(f"\n[{i}/{len(video_files)}] {vf.name}")
            print(f"  → {out_name}")

            original_file = None
            if original_videos:
                orig_stem = re.sub(r"_\d{5}$", "", vf.stem)
                if orig_stem in original_videos:
                    original_file = original_videos[orig_stem]
                elif i - 1 < len(orig_list):
                    original_file = orig_list[i - 1]

            vf_safe, vf_tmp = safe_ffmpeg_prepare(vf, tmp_dir, f"v{i}")
            orig_safe, orig_tmp = safe_ffmpeg_prepare(original_file or vf, tmp_dir, f"o{i}")
            out_safe = str(Path(tmp_dir) / f"out_{i:03d}.mp4")

            if original_file:
                cmd = build_watermark_cmd(vf_safe, orig_safe, out_safe, bgm_safe, bg_volume)
            else:
                print(f"  ⚠️ 无原始视频，使用换脸视频自身音轨")
                cmd = build_watermark_cmd(vf_safe, vf_safe, out_safe, bgm_safe, bg_volume)

            result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")

            if result.returncode == 0 and Path(out_safe).exists() and Path(out_safe).stat().st_size > 10000:
                shutil.move(out_safe, str(out_path))
                size_mb = out_path.stat().st_size / (1024 * 1024)
                print(f"  ✅ {size_mb:.1f}MB")
                success += 1
                done_stems.add(vf.stem)
                done_map_path.write_text(
                    json.dumps(sorted(done_stems), ensure_ascii=False), encoding="utf-8")
            else:
                err = result.stderr[-200:] if result.stderr else "unknown"
                print(f"  ❌ 失败: {err[:100]}")
                fail += 1

            for tmp_path in [vf_safe if vf_tmp else None, orig_safe if orig_tmp else None]:
                if tmp_path:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\n{'='*60}")
    print(f"🏁 完成: 成功 {success}, 失败 {fail}")
    return success, fail


# ===== 主程序 =====

def main():
    parser = argparse.ArgumentParser(
        description="一键启动：ComfyUI批量换脸 + AI水印 + 保留原BGM（不含语录）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python batch_faceswap_watermark.py
  python batch_faceswap_watermark.py --input "D:\\input\\videos" --face "D:\\face.png" --output "D:\\output"
  python batch_faceswap_watermark.py --skip-faceswap
  python batch_faceswap_watermark.py --submit-only
  python batch_faceswap_watermark.py --poll-only
        """
    )
    parser.add_argument("--input", default=r"D:\ai_projects\ComfyUI\input\十绫Shiling",
                        help="输入视频目录 (默认: 十绫Shiling)")
    FACE_DIR = Path(r"D:\ai_projects\ComfyUI\input\ken4\face\ken")
    FACE_POOL = ["ken-14岁.png", "ken-16岁.png"]
    default_face = str(FACE_DIR / FACE_POOL[0])
    parser.add_argument("--face", default=default_face,
                        help="人脸图片路径 (默认: ken4/face/ken 第一张)")
    parser.add_argument("--output", default=r"D:\ai_projects\ComfyUI\output\aken4\十绫Shiling",
                        help="最终输出目录 (默认: aken4/十绫Shiling)")
    parser.add_argument("--skip-faceswap", action="store_true", help="跳过换脸步骤（已有换脸结果时）")
    parser.add_argument("--original-dir", help="原始视频目录（有原BGM的源文件）")
    parser.add_argument("--bg-music", help="额外混入的背景音乐（不指定则只保留原BGM）")
    parser.add_argument("--bg-volume", type=float, default=0.15, help="额外BGM音量 0.0-1.0 (默认: 0.15)")
    parser.add_argument("--comfyui-url", default=COMFYUI_URL, help="ComfyUI API 地址")
    parser.add_argument("--dry-run", action="store_true", help="只检查参数和连接，不提交任务")
    parser.add_argument("--limit", type=int, default=0, help="本批最多提交 N 个（0=全部）")
    parser.add_argument("--submit-only", action="store_true",
                        help="只提交不轮询不后处理（提交即走，稍后 --poll-only 续）")
    parser.add_argument("--poll-only", action="store_true",
                        help="只轮询提交清单中的任务并后处理（不新提交）")
    parser.add_argument("--order-file", help="提交顺序清单（txt 一行一片）")
    args = parser.parse_args()

    comfyui_url = args.comfyui_url
    input_dir = Path(args.input)
    face_path = Path(args.face)
    output_dir = Path(args.output)
    output_subdir = comfyui_output_subdir(output_dir)
    manifest = (SCRIPT_DIR.parent / "output" / output_subdir).parent / "_submit_manifest.jsonl"

    print("=" * 60)
    print("🎬 批量换脸 + AI水印 + 保留原BGM（无语录）")
    print("=" * 60)
    print(f"📂 输入: {input_dir}")
    print(f"👤 人脸: {face_path}")
    print(f"📁 输出: {output_dir}")
    print(f"⏭️ 跳过换脸: {args.skip_faceswap}")
    print("=" * 60)

    if not input_dir.exists():
        print(f"❌ 输入目录不存在: {input_dir}")
        sys.exit(1)
    if not face_path.exists() and not args.skip_faceswap:
        print(f"❌ 人脸图片不存在: {face_path}")
        sys.exit(1)

    if args.dry_run:
        videos = get_video_list(input_dir)
        print(f"\n🔍 DRY-RUN 模式")
        print(f"  📂 输入目录: {input_dir} ({len(videos)} 个视频)")
        print(f"  👤 人脸图片: {face_path}")
        print(f"  📁 输出目录: {output_dir}")
        print(f"  ⏭️ 跳过换脸: {args.skip_faceswap}")
        if not args.skip_faceswap:
            try:
                urllib.request.urlopen(f"{comfyui_url}/queue", timeout=5)
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

    faceswap_output = output_dir
    if args.poll_only:
        try:
            urllib.request.urlopen(f"{COMFYUI_URL}/queue", timeout=10)
        except Exception:
            print(f"❌ ComfyUI 无法连接: {COMFYUI_URL}")
            sys.exit(1)
        queued = load_manifest(manifest)
        if not queued:
            print(f"❌ 提交清单为空或不存在: {manifest}")
            sys.exit(1)
        print(f"\n🔄 Step 1/2: 轮询清单中 {len(queued)} 个任务（不提交）")
        wait_for_completion(queued, len(queued))
    elif not args.skip_faceswap:
        try:
            urllib.request.urlopen(f"{comfyui_url}/queue", timeout=5)
        except Exception:
            print(f"❌ ComfyUI 无法连接: {COMFYUI_URL}")
            sys.exit(1)

        queued = queue_faceswap_jobs(input_dir, face_path, output_dir,
                                     limit=args.limit, order_file=args.order_file)

        if args.submit_only:
            print(f"\n📤 仅提交模式：已提交 {len(queued)} 个任务（清单 {manifest}）")
            print("   稍后用 --poll-only 轮询并完成后处理")
            sys.exit(0)

        if queued:
            wait_for_completion(queued, len(queued))
        else:
            print("⚠️ 没有新任务被提交（全部已有产物？），继续后处理")
    else:
        print(f"\n⏭️ 跳过换脸，使用已有结果: {input_dir}")
        faceswap_output = input_dir

    # Step 2: AI水印 + 保留原BGM
    print(f"\n🏷️ Step 2/2: 添加 AI水印 + 保留原BGM")
    original_dir = args.original_dir or str(input_dir)
    final_dir = output_dir if args.skip_faceswap else output_dir.parent / f"{output_dir.name}_final"

    bg_music = args.bg_music
    if bg_music:
        print(f"🎵 额外混入BGM: {Path(bg_music).name} (音量{args.bg_volume})，原BGM保持满音量")
    else:
        print(f"🎵 仅保留原BGM（原声音轨满音量），不额外混音")

    success, fail = process_watermark(
        faceswap_output, final_dir,
        original_dir=original_dir, bg_music=bg_music, bg_volume=args.bg_volume
    )

    print(f"\n{'='*60}")
    print(f"🎉 全部完成！")
    print(f"📁 最终输出: {final_dir}")
    print(f"📊 成功: {success} | 失败: {fail}")


if __name__ == "__main__":
    main()
