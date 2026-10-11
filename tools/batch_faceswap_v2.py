"""
批量 ReActor 换脸：对指定目录下的视频逐个执行 V2-verify 工作流。
- 复用已验证的 API prompt 模板（VHS_VideoInfo 自动帧率）
- 串行提交，避免 GPU 资源竞争
- 输出到 output/大小姐/ 目录
- 每个视频生成独立前缀，便于区分
"""
import json
import time
import sys
import urllib.request
import urllib.error
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
SOURCE_DIR = Path(r"d:\ai_projects\ComfyUI\input\ken4\西门大小姐日常")
OUTPUT_DIR = Path(r"d:\ai_projects\ComfyUI\output\大小姐")
FIRST_N = 5  # 先处理前 5 个

# API prompt 模板（基于已验证的 v2_autofps_api_prompt.json）
PROMPT_TEMPLATE = {
    "1": {  # VHS_LoadVideo
        "class_type": "VHS_LoadVideo",
        "inputs": {
            "video": "",  # 待填充
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
    "6": {
        "class_type": "ImageBatch",
        "inputs": {"image1": ["2", 0], "image2": ["3", 0]},
    },
    "7": {
        "class_type": "ImageBatch",
        "inputs": {"image1": ["6", 0], "image2": ["4", 0]},
    },
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
    "10": {
        "class_type": "ReActorFaceSwap",
        "inputs": {
            "input_image": ["1", 0],
            "face_model": ["9", 0],
            "enabled": True,
            "swap_model": "inswapper_128.onnx",
            "facedetection": "retinaface_resnet50",
            "face_restore_model": "GFPGANv1.4.pth",
            "face_restore_visibility": 0.5,
            "codeformer_weight": 0.5,
            "detect_gender_input": "no",
            "detect_gender_source": "no",
            "input_faces_index": "0",
            "source_faces_index": "0",
            "console_log_level": 1,
        },
    },
    "14": {
        "class_type": "VHS_VideoInfo",
        "inputs": {"video_info": ["1", 3]},
    },
    "11": {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["10", 0],
            "audio": ["1", 2],
            "frame_rate": ["14", 5],  # 自动从 video_info 提取 loaded_fps
            "loop_count": 0,
            "filename_prefix": "",  # 待填充
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 19,
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        },
    },
}


def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_prompt(video_rel_path, filename_prefix):
    """基于模板构造单个视频的 API prompt。"""
    prompt = json.loads(json.dumps(PROMPT_TEMPLATE))  # 深拷贝
    prompt["1"]["inputs"]["video"] = video_rel_path
    prompt["11"]["inputs"]["filename_prefix"] = filename_prefix
    return prompt


def submit_and_wait(prompt, label, timeout_sec=600):
    """提交 prompt 并等待执行完成。"""
    submission = {"prompt": prompt, "client_id": "batch_agent"}
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


def main():
    # 1. 收集前 N 个视频
    videos = sorted([f for f in SOURCE_DIR.glob("*.mp4") if f.name != "test.mp4"])
    targets = videos[:FIRST_N]
    print(f"源目录: {SOURCE_DIR}")
    print(f"总视频数: {len(videos)}, 本次处理: {len(targets)}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    # 2. 检查 ComfyUI 是否在运行
    try:
        http_get_json(COMFY + "/system_stats")
    except Exception:
        print("[错误] ComfyUI 未运行，请先启动")
        sys.exit(1)

    # 3. 批量处理
    results = []
    total_start = time.time()
    for i, video in enumerate(targets, 1):
        # 相对路径（ComfyUI 从 input/ 下找）
        rel_path = str(video.relative_to(Path(r"d:\ai_projects\ComfyUI\input"))).replace("/", "\\")
        # 输出前缀：用视频文件名（去扩展名）+ 序号
        video_stem = video.stem
        prefix = f"大小姐\\{video_stem}"

        print(f"\n[{i}/{len(targets)}] {video.name}")
        print(f"  相对路径: {rel_path}")
        print(f"  输出前缀: {prefix}")

        prompt = build_prompt(rel_path, prefix)
        t0 = time.time()
        ok, outputs, errors = submit_and_wait(prompt, video.name, timeout_sec=600)
        elapsed = time.time() - t0

        if ok:
            # 提取输出文件信息
            out_files = []
            if outputs and "11" in outputs:
                gifs = outputs["11"].get("gifs", [])
                for g in gifs:
                    out_files.append(g.get("filename", ""))
            print(f"  ✓ 完成 ({elapsed:.1f}s) 输出: {', '.join(out_files)}")
            results.append((video.name, True, elapsed, out_files))
        else:
            print(f"  ✗ 失败 ({elapsed:.1f}s) 原因: {outputs}")
            if errors:
                print(f"    节点错误: {errors}")
            results.append((video.name, False, elapsed, str(outputs)))

    # 4. 汇总
    total_elapsed = time.time() - total_start
    success = sum(1 for _, ok, _, _ in results if ok)
    print("\n" + "=" * 60)
    print(f"批量处理完成: {success}/{len(targets)} 成功, 总耗时 {total_elapsed:.1f}s")
    print("\n详细:")
    for name, ok, elapsed, info in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {name} ({elapsed:.1f}s) {info if not ok else ''}")


if __name__ == "__main__":
    main()
