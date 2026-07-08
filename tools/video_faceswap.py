#!/usr/bin/env python3
"""
视频换脸工具 - 使用 ReActor + ffmpeg
流程: 提取视频帧 → ReActor 逐帧换脸 → 合成视频
"""
import os
import sys
import json
import subprocess
import requests
import time
import argparse
from pathlib import Path

# 配置
COMFYUI_URL = "http://127.0.0.1:8188"
INPUT_VIDEO = "ltxv_gguf_test_00001_.mp4"  # 输入视频
SOURCE_FACE = "test_source_face.png"  # 源人脸图片
OUTPUT_VIDEO = "faceswap_output.mp4"  # 输出视频
FPS = 25

def extract_frames(video_path, output_dir):
    """使用 ffmpeg 提取视频帧"""
    os.makedirs(output_dir, exist_ok=True)
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'fps={FPS}',
        os.path.join(output_dir, 'frame_%04d.png'),
        '-y'
    ]
    subprocess.run(cmd, check=True)
    frames = sorted(Path(output_dir).glob('frame_*.png'))
    print(f"提取了 {len(frames)} 帧")
    return frames

def create_video_from_frames(frames_dir, output_path, fps=25):
    """使用 ffmpeg 将帧合成视频"""
    cmd = [
        'ffmpeg', '-framerate', str(fps),
        '-i', os.path.join(frames_dir, 'frame_%04d.png'),
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        output_path,
        '-y'
    ]
    subprocess.run(cmd, check=True)
    print(f"视频已保存: {output_path}")

def submit_faceswap(frame_path, source_path):
    """提交单帧换脸任务到 ComfyUI"""
    # 上传图片
    with open(frame_path, 'rb') as f:
        resp = requests.post(f"{COMFYUI_URL}/upload/image", files={'image': f})
        frame_name = resp.json()['name']
    
    with open(source_path, 'rb') as f:
        resp = requests.post(f"{COMFYUI_URL}/upload/image", files={'image': f})
        source_name = resp.json()['name']
    
    # 构建工作流
    workflow = {
        "prompt": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": frame_name}
            },
            "2": {
                "class_type": "LoadImage", 
                "inputs": {"image": source_name}
            },
            "3": {
                "class_type": "ReActorFaceSwap",
                "inputs": {
                    "enabled": True,
                    "input_image": ["1", 0],
                    "swap_model": "inswapper_128.onnx",
                    "facedetection": "retinaface_resnet50",
                    "face_restore_model": "none",
                    "face_restore_visibility": 1.0,
                    "codeformer_weight": 0.5,
                    "detect_gender_input": "no",
                    "detect_gender_source": "no",
                    "input_faces_index": "0",
                    "source_faces_index": "0",
                    "console_log_level": 1,
                    "source_image": ["2", 0]
                }
            },
            "4": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["3", 0],
                    "filename_prefix": "faceswap_frame"
                }
            }
        }
    }
    
    # 提交任务
    resp = requests.post(f"{COMFYUI_URL}/api/prompt", json=workflow)
    prompt_id = resp.json()['prompt_id']
    return prompt_id

def wait_for_completion(prompt_id, timeout=300):
    """等待任务完成"""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
        if resp.status_code == 200:
            data = resp.json()
            if prompt_id in data:
                return data[prompt_id]
        time.sleep(1)
    raise TimeoutError("任务超时")

def get_output_image(prompt_id):
    """获取输出图片"""
    history = wait_for_completion(prompt_id)
    outputs = history.get('outputs', {})
    for node_id, node_output in outputs.items():
        if 'images' in node_output:
            for img in node_output['images']:
                return img['filename']
    return None

def main():
    parser = argparse.ArgumentParser(description='视频换脸工具')
    parser.add_argument('--input', '-i', default=INPUT_VIDEO, help='输入视频')
    parser.add_argument('--source', '-s', default=SOURCE_FACE, help='源人脸图片')
    parser.add_argument('--output', '-o', default=OUTPUT_VIDEO, help='输出视频')
    parser.add_argument('--fps', type=int, default=FPS, help='帧率')
    args = parser.parse_args()
    
    frames_dir = 'temp_frames'
    output_frames_dir = 'temp_faceswap_frames'
    
    print("=== 视频换脸工具 ===")
    print(f"输入: {args.input}")
    print(f"源人脸: {args.source}")
    print(f"输出: {args.output}")
    
    # 1. 提取视频帧
    print("\n[1/3] 提取视频帧...")
    frames = extract_frames(args.input, frames_dir)
    
    # 2. 逐帧换脸
    print("\n[2/3] 逐帧换脸...")
    os.makedirs(output_frames_dir, exist_ok=True)
    
    for i, frame_path in enumerate(frames):
        print(f"  处理帧 {i+1}/{len(frames)}: {frame_path.name}")
        
        # 提交换脸任务
        prompt_id = submit_faceswap(frame_path, args.source)
        
        # 等待完成
        output_img = get_output_image(prompt_id)
        if output_img:
            # 下载输出图片
            resp = requests.get(f"{COMFYUI_URL}/view?filename={output_img}")
            output_path = os.path.join(output_frames_dir, f'frame_{i:04d}.png')
            with open(output_path, 'wb') as f:
                f.write(resp.content)
            print(f"    完成: {output_path}")
        else:
            print(f"    失败: 帧 {i+1}")
    
    # 3. 合成视频
    print("\n[3/3] 合成视频...")
    create_video_from_frames(output_frames_dir, args.output, args.fps)
    
    print("\n=== 完成 ===")
    print(f"输出视频: {args.output}")

if __name__ == '__main__':
    main()
