#!/usr/bin/env python3
"""
高效视频换脸工具 - 直接使用 ReActor (insightface)
流程: 提取视频帧 → insightface 逐帧换脸 → 合成视频
"""
import os
import sys
import subprocess
import cv2
import numpy as np
import argparse
from pathlib import Path
from insightface.app import FaceAnalysis
from insightface.model_zoo import get_model

# 默认配置
DEFAULT_INPUT = "input/testfaceswap.mp4"
DEFAULT_SOURCE = "input/face_source.png"
DEFAULT_OUTPUT = "output/testfaceswap_result.mp4"
FPS = 25
MODEL_PATH = "models/insightface/inswapper_128.onnx"

def extract_frames(video_path, output_dir, fps=FPS):
    """使用 ffmpeg 提取视频帧"""
    os.makedirs(output_dir, exist_ok=True)
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'fps={fps}',
        os.path.join(output_dir, 'frame_%04d.png'),
        '-y'
    ]
    subprocess.run(cmd, check=True)
    frames = sorted(Path(output_dir).glob('frame_*.png'))
    print(f"提取了 {len(frames)} 帧")
    return frames

def create_video_from_frames(frames_dir, output_path, fps=FPS):
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

def init_face_swap():
    """初始化换脸模型"""
    # 初始化人脸分析
    app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))
    
    # 加载换脸模型
    swapper = get_model(MODEL_PATH)
    
    return app, swapper

def swap_face(app, swapper, source_img, target_img):
    """执行换脸"""
    # 检测源人脸
    source_faces = app.get(source_img)
    if len(source_faces) == 0:
        print("警告: 源图片未检测到人脸")
        return target_img
    
    source_face = source_faces[0]
    
    # 检测目标人脸
    target_faces = app.get(target_img)
    if len(target_faces) == 0:
        print("警告: 目标图片未检测到人脸")
        return target_img
    
    # 对每个目标人脸进行换脸
    result = target_img.copy()
    for target_face in target_faces:
        result = swapper.get(result, target_face, source_face, paste_back=True)
    
    return result

def main():
    parser = argparse.ArgumentParser(description='高效视频换脸工具')
    parser.add_argument('--input', '-i', default=DEFAULT_INPUT, help='输入视频路径')
    parser.add_argument('--source', '-s', default=DEFAULT_SOURCE, help='源人脸图片路径')
    parser.add_argument('--output', '-o', default=DEFAULT_OUTPUT, help='输出视频路径')
    parser.add_argument('--fps', type=int, default=FPS, help='帧率')
    args = parser.parse_args()
    
    print("=== 高效视频换脸工具 ===")
    print(f"输入: {args.input}")
    print(f"源人脸: {args.source}")
    print(f"输出: {args.output}")
    
    frames_dir = 'temp_frames'
    output_frames_dir = 'temp_faceswap_frames'
    
    # 1. 提取视频帧
    print("\n[1/4] 提取视频帧...")
    frames = extract_frames(args.input, frames_dir, args.fps)
    
    # 2. 初始化换脸模型
    print("\n[2/4] 初始化换脸模型...")
    app, swapper = init_face_swap()
    
    # 3. 读取源人脸
    print("\n[3/4] 读取源人脸...")
    source_img = cv2.imread(args.source)
    if source_img is None:
        print(f"错误: 无法读取源图片 {args.source}")
        return
    
    # 4. 逐帧换脸
    print("\n[4/4] 逐帧换脸...")
    os.makedirs(output_frames_dir, exist_ok=True)
    
    for i, frame_path in enumerate(frames):
        print(f"  处理帧 {i+1}/{len(frames)}: {frame_path.name}")
        
        # 读取目标帧
        target_img = cv2.imread(str(frame_path))
        if target_img is None:
            print(f"    跳过: 无法读取 {frame_path}")
            continue
        
        # 执行换脸
        result = swap_face(app, swapper, source_img, target_img)
        
        # 保存结果
        output_path = os.path.join(output_frames_dir, f'frame_{i:04d}.png')
        cv2.imwrite(output_path, result)
        print(f"    完成: {output_path}")
    
    # 5. 合成视频
    print("\n[5/5] 合成视频...")
    create_video_from_frames(output_frames_dir, args.output, args.fps)
    
    print("\n=== 完成 ===")
    print(f"输出视频: {args.output}")
    print(f"处理帧数: {len(frames)}")

if __name__ == '__main__':
    main()
