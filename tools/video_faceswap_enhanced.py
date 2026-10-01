#!/usr/bin/env python3
"""
增强版视频换脸工具 - insightface + GFPGAN 修复 + 色彩校正
流程: 提取视频帧 → insightface 换脸 → GFPGAN 修复 → 色彩校正 → 合成视频
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
GFPGAN_PATH = "models/facerestore_models/GFPGANv1.4.pth"


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


def create_video_from_frames(frames_dir, output_path, fps=FPS, audio_source=None):
    """使用 ffmpeg 将帧合成视频，可选保留原视频音频"""
    cmd = [
        'ffmpeg', '-framerate', str(fps),
        '-i', os.path.join(frames_dir, 'frame_%04d.png'),
    ]
    if audio_source and os.path.exists(audio_source):
        cmd += ['-i', audio_source, '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0?']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', output_path, '-y']
    subprocess.run(cmd, check=True)
    print(f"视频已保存: {output_path}")


def init_face_swap(det_size=(640, 640)):
    """初始化换脸模型"""
    app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=det_size)
    swapper = get_model(MODEL_PATH)
    return app, swapper


def init_gfpgan():
    """初始化 GFPGAN 人脸修复模型"""
    try:
        from gfpgan import GFPGANer
        if not os.path.exists(GFPGAN_PATH):
            print(f"警告: GFPGAN 模型不存在: {GFPGAN_PATH}")
            return None
        restorer = GFPGANer(
            model_path=GFPGAN_PATH,
            upscale=1,
            arch='clean',
            channel_multiplier=2,
            bg_upsampler=None
        )
        print("GFPGAN 初始化成功")
        return restorer
    except Exception as e:
        print(f"GFPGAN 初始化失败: {e}")
        return None


def color_correct_face(source_img, result_img, face_bbox, margin=30):
    """色彩校正：将换脸区域的色彩匹配到原始图像"""
    x1, y1, x2, y2 = [int(v) for v in face_bbox]
    # 扩展区域
    h, w = result_img.shape[:2]
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(w, x2 + margin)
    y2 = min(h, y2 + margin)

    # 提取原始和结果的脸部区域
    orig_face = source_img[y1:y2, x1:x2].astype(np.float32)
    result_face = result_img[y1:y2, x1:x2].astype(np.float32)

    if orig_face.size == 0 or result_face.size == 0:
        return result_img

    # 统计色彩
    for c in range(3):
        orig_mean = orig_face[:, :, c].mean()
        orig_std = orig_face[:, :, c].std() + 1e-6
        result_mean = result_face[:, :, c].mean()
        result_std = result_face[:, :, c].std() + 1e-6

        # 色彩迁移
        result_face[:, :, c] = (result_face[:, :, c] - result_mean) * (orig_std / result_std) + orig_mean

    result_face = np.clip(result_face, 0, 255).astype(np.uint8)
    result_img[y1:y2, x1:x2] = result_face
    return result_img


def swap_face_enhanced(app, swapper, restorer, source_img, target_img, 
                       use_restoration=True, use_color_correction=True):
    """执行增强版换脸"""
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

    # 过滤：只选最大/最自信的人脸（避免手部误检）
    best_face = max(target_faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))
    if best_face.det_score < 0.5:
        print(f"警告: 人脸检测置信度过低 ({best_face.det_score:.3f})")
        return target_img

    # 执行换脸
    result = swapper.get(target_img.copy(), best_face, source_face, paste_back=True)

    # GFPGAN 人脸修复
    if use_restoration and restorer is not None:
        try:
            _, _, restored = restorer.enhance(
                result, 
                has_aligned=False, 
                only_center_face=False, 
                paste_back=True,
                weight=0.5  # 混合权重，0=原始 1=完全修复
            )
            if restored is not None:
                result = restored
        except Exception as e:
            print(f"GFPGAN 修复失败: {e}")

    # 色彩校正
    if use_color_correction:
        result = color_correct_face(target_img, result, best_face.bbox)

    return result


def main():
    parser = argparse.ArgumentParser(description='增强版视频换脸工具')
    parser.add_argument('--input', '-i', default=DEFAULT_INPUT, help='输入视频路径')
    parser.add_argument('--source', '-s', default=DEFAULT_SOURCE, help='源人脸图片路径')
    parser.add_argument('--output', '-o', default=DEFAULT_OUTPUT, help='输出视频路径')
    parser.add_argument('--fps', type=int, default=FPS, help='帧率')
    parser.add_argument('--det-size', type=int, default=640, help='人脸检测尺寸')
    parser.add_argument('--no-restoration', action='store_true', help='禁用 GFPGAN 修复')
    parser.add_argument('--no-color-correct', action='store_true', help='禁用色彩校正')
    parser.add_argument('--keep-audio', action='store_true', help='保留原视频音频')
    args = parser.parse_args()

    print("=== 增强版视频换脸工具 ===")
    print(f"输入: {args.input}")
    print(f"源人脸: {args.source}")
    print(f"输出: {args.output}")
    print(f"检测尺寸: {args.det_size}")
    print(f"GFPGAN: {'禁用' if args.no_restoration else '启用'}")
    print(f"色彩校正: {'禁用' if args.no_color_correct else '启用'}")

    frames_dir = 'temp_frames'
    output_frames_dir = 'temp_faceswap_frames'

    # 1. 提取视频帧
    print("\n[1/5] 提取视频帧...")
    frames = extract_frames(args.input, frames_dir, args.fps)

    # 2. 初始化模型
    print("\n[2/5] 初始化模型...")
    app, swapper = init_face_swap(det_size=(args.det_size, args.det_size))
    restorer = init_gfpgan() if not args.no_restoration else None

    # 3. 读取源人脸
    print("\n[3/5] 读取源人脸...")
    source_img = cv2.imread(args.source)
    if source_img is None:
        print(f"错误: 无法读取源图片 {args.source}")
        return

    # 4. 逐帧换脸
    print("\n[4/5] 逐帧换脸...")
    os.makedirs(output_frames_dir, exist_ok=True)

    for i, frame_path in enumerate(frames):
        print(f"  处理帧 {i+1}/{len(frames)}: {frame_path.name}")

        target_img = cv2.imread(str(frame_path))
        if target_img is None:
            print(f"    跳过: 无法读取 {frame_path}")
            continue

        result = swap_face_enhanced(
            app, swapper, restorer, source_img, target_img,
            use_restoration=not args.no_restoration,
            use_color_correction=not args.no_color_correct
        )

        output_path = os.path.join(output_frames_dir, f'frame_{i:04d}.png')
        cv2.imwrite(output_path, result)

    # 5. 合成视频
    print("\n[5/5] 合成视频...")
    audio_source = args.input if args.keep_audio else None
    create_video_from_frames(output_frames_dir, args.output, args.fps, audio_source)

    print("\n=== 完成 ===")
    print(f"输出视频: {args.output}")
    print(f"处理帧数: {len(frames)}")


if __name__ == '__main__':
    main()
