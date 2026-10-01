#!/usr/bin/env python3
"""
ComfyUI API 批量视频换脸
提交 ReActor 换脸工作流到 ComfyUI，处理多个视频
"""
import json
import time
import urllib.request
import urllib.error
import sys
import uuid

COMFYUI_URL = "http://127.0.0.1:8188"

# 视频列表：(文件名, 输出前缀)
VIDEOS = [
    ("qdb_video1_爱你没商量不许偷偷看呦.mp4", "qdb_faceswap1_爱你没商量不许偷偷看呦"),
    ("qdb_video2_爱你没商量.mp4", "qdb_faceswap2_爱你没商量"),
    ("qdb_video3_等风等雨只为等你.mp4", "qdb_faceswap3_等风等雨只为等你"),
]

FACE_SOURCE = "face_swap_source.png"


def build_workflow(video_file, output_prefix):
    """构建 ReActor 换脸工作流"""
    return {
        "1": {
            "class_type": "LoadVideo",
            "inputs": {
                "file": video_file
            }
        },
        "2": {
            "class_type": "GetVideoComponents",
            "inputs": {
                "video": ["1", 0]
            }
        },
        "3": {
            "class_type": "LoadImage",
            "inputs": {
                "image": FACE_SOURCE
            }
        },
        "4": {
            "class_type": "ReActorFaceSwap",
            "inputs": {
                "enabled": True,
                "input_image": ["2", 0],
                "source_image": ["3", 0],
                "swap_model": "inswapper_128.onnx",
                "facedetection": "retinaface_resnet50",
                "face_restore_model": "GFPGANv1.4.pth",
                "face_restore_visibility": 1.0,
                "codeformer_weight": 0.5,
                "detect_gender_input": "no",
                "detect_gender_source": "no",
                "input_faces_index": "0",
                "source_faces_index": "0",
                "console_log_level": 1
            }
        },
        "5": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["4", 0],
                "audio": ["2", 1],
                "fps": 30.0
            }
        },
        "6": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["5", 0],
                "filename_prefix": output_prefix,
                "format": "mp4",
                "codec": "h264"
            }
        }
    }


def queue_prompt(workflow):
    """提交工作流到 ComfyUI"""
    client_id = str(uuid.uuid4())
    payload = json.dumps({
        "prompt": workflow,
        "client_id": client_id
    }).encode('utf-8')

    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        return result.get('prompt_id'), client_id
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"  ❌ 提交失败: HTTP {e.code} - {body[:500]}")
        return None, None


def check_progress(prompt_id):
    """检查任务进度"""
    try:
        resp = urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}")
        data = json.loads(resp.read())
        if prompt_id in data:
            status = data[prompt_id].get('status', {})
            if status.get('completed', False):
                return 'completed'
            if status.get('status_str') == 'error':
                return 'error'
        return 'running'
    except:
        return 'unknown'


def main():
    print("=" * 60)
    print("ComfyUI 批量视频换脸")
    print("=" * 60)
    print(f"人脸源: {FACE_SOURCE}")
    print(f"视频数: {len(VIDEOS)}")
    print()

    results = []

    for idx, (video_file, output_prefix) in enumerate(VIDEOS):
        print(f"\n{'='*60}")
        print(f"[{idx+1}/{len(VIDEOS)}] 提交: {video_file}")
        print(f"  输出前缀: {output_prefix}")
        print(f"{'='*60}")

        workflow = build_workflow(video_file, output_prefix)
        prompt_id, client_id = queue_prompt(workflow)

        if not prompt_id:
            print(f"  ❌ 提交失败，跳过")
            results.append((video_file, 'failed'))
            continue

        print(f"  ✅ 已提交: prompt_id={prompt_id}")
        results.append((video_file, prompt_id, 'queued'))

    # 等待所有任务完成
    print(f"\n{'='*60}")
    print("等待所有任务完成...")
    print(f"{'='*60}")

    pending = [(v, p) for v, p, s in results if s == 'queued']
    completed = []
    max_wait = 1800  # 30 minutes max
    start = time.time()

    while pending and (time.time() - start) < max_wait:
        time.sleep(10)
        still_pending = []
        for video_file, prompt_id in pending:
            status = check_progress(prompt_id)
            if status == 'completed':
                print(f"  ✅ 完成: {video_file}")
                completed.append(video_file)
            elif status == 'error':
                print(f"  ❌ 错误: {video_file}")
            else:
                still_pending.append((video_file, prompt_id))
        pending = still_pending
        if pending:
            elapsed = int(time.time() - start)
            print(f"  ⏳ 等待中... {len(pending)} 个任务进行中 ({elapsed}s)")

    if pending:
        print(f"\n⚠️ 超时，{len(pending)} 个任务未完成")

    print(f"\n{'='*60}")
    print(f"完成: {len(completed)}/{len(VIDEOS)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
