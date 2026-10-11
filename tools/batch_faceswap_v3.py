"""
批量 ReActor 换脸 V3-opt：画质优化版。
- YOLOv5l 人脸检测（更精确）
- face_restore_visibility=0.75（修复更充分）
- ReActorFaceBoost（codeformer + Lanczos 二次增强）
- crf=16（接近视觉无损）
- 断点续传：progress.json 记录已完成视频
- 自动重试：单视频失败重试 2 次
- ffprobe 校验：输出时长与源视频对比
- 显存监控：超 14GB 触发 /free
- 输出到 output/大小姐_v3/ 目录
"""
import json
import time
import sys
import os
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
SOURCE_DIR = Path(r"d:\ai_projects\ComfyUI\input\ken4\西门大小姐日常")
OUTPUT_DIR = Path(r"d:\ai_projects\ComfyUI\output\大小姐_v3")
PROGRESS_FILE = OUTPUT_DIR / "progress.json"
FIRST_N = 0  # 0 表示处理全部
MAX_RETRY = 2  # 单视频失败重试次数
VRAM_THRESHOLD_MB = 14000  # 显存超此值触发 ComfyUI 释放缓存

# API prompt 模板（V3-opt：FaceBoost + YOLOv5l + crf=16 + restore=0.75）
PROMPT_TEMPLATE = {
    "1": {  # VHS_LoadVideo
        "class_type": "VHS_LoadVideo",
        "inputs": {
            "video": "",
            "force_rate": 0,
            "custom_width": 0,
            "custom_height": 0,
            "frame_load_cap": 0,
            "skip_first_frames": 0,
            "select_every_nth": 1,
            "format": "AnimateDiff",
        },
    },
    "2": {"class_type": "LoadImage", "inputs": {"image": "ken4\\face\\gpt\\duo.png"}},
    "3": {"class_type": "LoadImage", "inputs": {"image": "ken4\\face\\gpt\\left.png"}},
    "4": {"class_type": "LoadImage", "inputs": {"image": "ken4\\face\\gpt\\right.png"}},
    "6": {"class_type": "ImageBatch", "inputs": {"image1": ["2", 0], "image2": ["3", 0]}},
    "7": {"class_type": "ImageBatch", "inputs": {"image1": ["6", 0], "image2": ["4", 0]}},
    "9": {
        "class_type": "ReActorBuildFaceModel",
        "inputs": {
            "images": ["7", 0],
            "save_mode": False,
            "send_only": False,
            "face_model_name": "Mean",
            "compute_method": "Mean",
        },
    },
    "15": {  # ReActorFaceBoost（V3 新增）
        "class_type": "ReActorFaceBoost",
        "inputs": {
            "enabled": True,
            "boost_model": "codeformer.pth",
            "interpolation": "Lanczos",
            "visibility": 0.5,
            "codeformer_weight": 0.5,
            "restore_with_main_after": True,
        },
    },
    "10": {
        "class_type": "ReActorFaceSwap",
        "inputs": {
            "input_image": ["1", 0],
            "face_model": ["9", 0],
            "face_boost": ["15", 0],  # V3 连接 FaceBoost
            "enabled": True,
            "swap_model": "inswapper_128.onnx",
            "facedetection": "YOLOv5l",  # V3 升级
            "face_restore_model": "GFPGANv1.4.pth",
            "face_restore_visibility": 0.75,  # V3 提升
            "codeformer_weight": 0.5,
            "detect_gender_input": "no",
            "detect_gender_source": "no",
            "input_faces_index": "0",
            "source_faces_index": "0",
            "console_log_level": 1,
        },
    },
    "14": {"class_type": "VHS_VideoInfo", "inputs": {"video_info": ["1", 3]}},
    "11": {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["10", 0],
            "audio": ["1", 2],
            "frame_rate": ["14", 5],
            "loop_count": 0,
            "filename_prefix": "",
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 16,  # V3 接近视觉无损
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        },
    },
}


def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_vram_usage_mb():
    """通过 nvidia-smi 获取当前 GPU 显存占用（MB）。"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        return int(result.stdout.strip())
    except Exception:
        return 0


def free_comfy_cache():
    """调用 ComfyUI /free 释放模型缓存。"""
    try:
        req = urllib.request.Request(COMFY + "/free", data=b'{"unload_models":true}', headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"    [显存] 已触发 ComfyUI 释放缓存: {resp.read().decode()[:100]}")
    except Exception as e:
        print(f"    [显存] 释放缓存失败: {e}")


def ffprobe_duration(video_path):
    """用 ffprobe 获取视频时长（秒）。"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return -1


def validate_output(src_path, out_path):
    """校验输出视频时长是否与源视频匹配。"""
    src_dur = ffprobe_duration(src_path)
    out_dur = ffprobe_duration(out_path)
    if src_dur < 0 or out_dur < 0:
        return False, "无法读取时长"
    diff = abs(src_dur - out_dur)
    if diff > 0.5:  # 时长差异超 0.5s 视为异常
        return False, f"时长差异 {diff:.2f}s (源={src_dur:.2f}, 输出={out_dur:.2f})"
    return True, f"时长匹配 ({out_dur:.2f}s)"


def load_progress():
    """加载进度文件。"""
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": []}


def save_progress(progress):
    """保存进度文件。"""
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def build_prompt(video_rel_path, filename_prefix):
    """基于模板构造单个视频的 API prompt。"""
    prompt = json.loads(json.dumps(PROMPT_TEMPLATE))
    prompt["1"]["inputs"]["video"] = video_rel_path
    prompt["11"]["inputs"]["filename_prefix"] = filename_prefix
    return prompt


def submit_and_wait(prompt, label, timeout_sec=1200):
    """提交 prompt 并等待执行完成。"""
    submission = {"prompt": prompt, "client_id": "batch_v3_agent"}
    try:
        resp = http_post_json(COMFY + "/prompt", submission)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, f"HTTP {e.code}: {body}", None

    if "error" in resp:
        return False, f"提交错误: {resp.get('error')}", resp.get("node_errors")
    if "prompt_id" not in resp:
        return False, f"无 prompt_id: {resp}", None

    pid = resp["prompt_id"]
    node_errors = resp.get("node_errors", {})
    if node_errors:
        return False, f"节点错误: {node_errors}", None

    deadline = time.time() + timeout_sec
    last_status = None
    while time.time() < deadline:
        try:
            h = http_get_json(COMFY + "/history/" + pid)
            if pid in h:
                s = h[pid].get("status", {})
                st = s.get("status_str", "unknown")
                if st != last_status:
                    print(f"    [{label}] 状态: {st}")
                    last_status = st
                if st in ("success", "error"):
                    if st == "error":
                        return False, f"执行错误: {json.dumps(s, ensure_ascii=False)}", None
                    outputs = h[pid].get("outputs", {})
                    return True, outputs, None
            time.sleep(3)
        except Exception as e:
            print(f"    [{label}] 轮询异常: {e}")
            time.sleep(3)
    return False, "超时", None


def process_video(video, index, total, output_dir_rel):
    """处理单个视频，含重试逻辑。"""
    rel_path = str(video.relative_to(Path(r"d:\ai_projects\ComfyUI\input"))).replace("/", "\\")
    video_stem = video.stem
    prefix = f"{output_dir_rel}\\{video_stem}"

    print(f"\n[{index}/{total}] {video.name}")
    print(f"  相对路径: {rel_path}")
    print(f"  输出前缀: {prefix}")

    # 显存检查
    vram = get_vram_usage_mb()
    if vram > VRAM_THRESHOLD_MB:
        print(f"  [显存] 当前 {vram}MB 超阈值 {VRAM_THRESHOLD_MB}MB，释放缓存...")
        free_comfy_cache()
        time.sleep(3)
    else:
        print(f"  [显存] {vram}MB")

    prompt = build_prompt(rel_path, prefix)

    for attempt in range(1, MAX_RETRY + 2):  # 原始 + 重试
        if attempt > 1:
            print(f"  [重试 {attempt - 1}/{MAX_RETRY}]")
        t0 = time.time()
        ok, outputs, errors = submit_and_wait(prompt, video.name, timeout_sec=1200)
        elapsed = time.time() - t0

        if ok:
            # 提取输出文件
            out_files = []
            if outputs and "11" in outputs:
                gifs = outputs["11"].get("gifs", [])
                for g in gifs:
                    out_files.append(g.get("filename", ""))
            # ffprobe 校验
            expected_out = OUTPUT_DIR / f"{video_stem}_00001-audio.mp4"
            if expected_out.exists():
                valid, msg = validate_output(video, expected_out)
                status = "✓" if valid else "⚠"
                print(f"  {status} 完成 ({elapsed:.1f}s) 校验: {msg}")
                if not valid:
                    print(f"    输出文件: {expected_out.name}")
            else:
                print(f"  ⚠ 完成但未找到输出文件: {expected_out.name}")
            return True, elapsed, out_files
        else:
            print(f"  ✗ 失败 ({elapsed:.1f}s) 原因: {outputs}")
            if errors:
                print(f"    节点错误: {errors}")
            if attempt < MAX_RETRY + 1:
                print(f"    等待 5s 后重试...")
                time.sleep(5)

    return False, 0, str(outputs)


def main():
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 收集视频
    videos = sorted([f for f in SOURCE_DIR.glob("*.mp4") if f.name != "test.mp4"])
    targets = videos[:FIRST_N] if FIRST_N > 0 else videos
    print(f"源目录: {SOURCE_DIR}")
    print(f"总视频数: {len(videos)}, 本次处理: {len(targets)}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"重试次数: {MAX_RETRY}, 显存阈值: {VRAM_THRESHOLD_MB}MB")
    print("=" * 60)

    # 检查 ComfyUI
    try:
        http_get_json(COMFY + "/system_stats")
    except Exception:
        print("[错误] ComfyUI 未运行，请先启动")
        sys.exit(1)

    # 加载进度
    progress = load_progress()
    completed_set = set(progress["completed"])
    print(f"已完成: {len(completed_set)} 个, 待处理: {len(targets) - len(completed_set)} 个")

    # 批量处理
    results = []
    total_start = time.time()
    for i, video in enumerate(targets, 1):
        if video.name in completed_set:
            print(f"\n[{i}/{len(targets)}] {video.name} (已完成，跳过)")
            continue

        ok, elapsed, info = process_video(video, i, len(targets), "大小姐_v3")
        results.append((video.name, ok, elapsed, info))

        if ok:
            progress["completed"].append(video.name)
            save_progress(progress)
        else:
            progress["failed"].append({"name": video.name, "reason": str(info)})
            save_progress(progress)

    # 汇总
    total_elapsed = time.time() - total_start
    success = sum(1 for _, ok, _, _ in results if ok)
    print("\n" + "=" * 60)
    print(f"批量处理完成: {success}/{len(results)} 成功, 总耗时 {total_elapsed:.1f}s")
    if progress["failed"]:
        print(f"失败列表 ({len(progress['failed'])} 个):")
        for f in progress["failed"]:
            print(f"  - {f['name']}: {f['reason'][:80]}")
    print("\n详细:")
    for name, ok, elapsed, info in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {name} ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
