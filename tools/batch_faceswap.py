#!/usr/bin/env python3
"""
批量视频换脸工具 - 支持长视频自动分割/合并
流程: 检测时长 → 分割 → 逐段换脸 → 合并 → 输出

修复版 v2:
- 每段开始前清理旧临时目录（防止残留帧编号冲突）
- 帧写入后验证完整性
- ffmpeg 合成前检查帧连续性
- 源人脸用 det_size=320 检测（大特写图需要）
- 目标人脸用 det_size=640 检测
"""
import os
import sys
import subprocess
import shutil
import json
import cv2
import numpy as np
import argparse
from pathlib import Path
from insightface.app import FaceAnalysis
from insightface.model_zoo import get_model

# 默认配置
MODEL_PATH = "models/insightface/inswapper_128.onnx"
GFPGAN_PATH = "models/facerestore_models/GFPGANv1.4.pth"
MAX_SEGMENT_SEC = 15  # 最大片段时长(秒)


def get_video_duration(video_path):
    """获取视频时长(秒)"""
    cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
           '-of', 'csv=p=0', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def get_video_fps(video_path):
    """获取视频原始帧率"""
    cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
           '-show_entries', 'stream=r_frame_rate',
           '-of', 'csv=p=0', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        fps_str = result.stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            return float(num) / float(den)
        return float(fps_str)
    except:
        return 25.0


def split_video(video_path, output_dir, segment_sec=MAX_SEGMENT_SEC):
    """将长视频分割为多个片段"""
    os.makedirs(output_dir, exist_ok=True)
    duration = get_video_duration(video_path)

    if duration <= segment_sec:
        out_path = os.path.join(output_dir, "segment_000.mp4")
        shutil.copy2(video_path, out_path)
        return [out_path], duration

    n_segments = int(np.ceil(duration / segment_sec))
    segments = []

    for i in range(n_segments):
        start = i * segment_sec
        out_path = os.path.join(output_dir, f"segment_{i:03d}.mp4")
        cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', str(start), '-t', str(segment_sec),
            '-c:v', 'libx264', '-c:a', 'aac',
            out_path, '-y'
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        segments.append(out_path)
        print(f"  分段 {i+1}/{n_segments}: {start:.1f}s - {min(start+segment_sec, duration):.1f}s")

    return segments, duration


def merge_videos(segment_paths, output_path):
    """将多个视频片段合并为一个"""
    list_path = output_path + ".concat.txt"
    with open(list_path, 'w') as f:
        for seg in segment_paths:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    cmd = [
        'ffmpeg', '-f', 'concat', '-safe', '0',
        '-i', list_path,
        '-c:v', 'libx264', '-c:a', 'aac',
        '-pix_fmt', 'yuv420p',
        output_path, '-y'
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    os.remove(list_path)
    print(f"  合并完成: {output_path}")


def init_face_swap(det_size=(640, 640)):
    """初始化换脸模型"""
    app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=det_size)
    swapper = get_model(MODEL_PATH)
    return app, swapper


def init_gfpgan():
    """初始化 GFPGAN"""
    try:
        from gfpgan import GFPGANer
        if not os.path.exists(GFPGAN_PATH):
            return None
        return GFPGANer(
            model_path=GFPGAN_PATH,
            upscale=1, arch='clean', channel_multiplier=2, bg_upsampler=None
        )
    except Exception as e:
        print(f"GFPGAN 初始化失败: {e}")
        return None


def process_video_segment(app, swapper, restorer, source_img,
                          input_video, output_video, fps=25,
                          source_faces_cache=None):
    """处理单个视频片段"""
    frames_dir = input_video + "_frames"
    output_frames_dir = input_video + "_swapped"

    # ★ 关键修复: 每段开始前清理旧临时目录，防止残留帧冲突
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir, ignore_errors=True)
    if os.path.exists(output_frames_dir):
        shutil.rmtree(output_frames_dir, ignore_errors=True)

    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(output_frames_dir, exist_ok=True)

    # 提取帧（用视频原始帧率）
    extract_result = subprocess.run([
        'ffmpeg', '-i', input_video,
        '-vf', f'fps={fps}',
        os.path.join(frames_dir, 'frame_%04d.png'), '-y'
    ], capture_output=True, text=True)
    if extract_result.returncode != 0:
        print(f"    ⚠️ 帧提取失败: {extract_result.stderr[-300:]}", flush=True)

    frames = sorted(Path(frames_dir).glob('frame_*.png'))
    if not frames:
        print(f"    ⚠️ 未提取到任何帧，跳过此片段", flush=True)
        subprocess.run([
            'ffmpeg', '-f', 'lavfi', '-i', f'color=c=black:s=640x480:d=1',
            '-i', input_video,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-map', '0:v:0', '-map', '1:a:0?',
            '-shortest', '-pix_fmt', 'yuv420p',
            output_video, '-y'
        ], capture_output=True)
        return 0

    print(f"    提取到 {len(frames)} 帧", flush=True)

    # 预检测源人脸（只需检测一次，大图需缩小以适配检测器）
    if source_faces_cache:
        source_faces = source_faces_cache
    else:
        sh, sw = source_img.shape[:2]
        if max(sh, sw) > 800:
            source_small = cv2.resize(source_img, (320, int(320 * sh / sw)))
        else:
            source_small = source_img
        source_faces = app.get(source_small)
    if not source_faces:
        print(f"    ⚠️ 源人脸检测失败，跳过此片段", flush=True)
        shutil.copy2(input_video, output_video)
        return 0

    # 读取第一帧获取尺寸（用于黑帧占位）
    first_frame = cv2.imread(str(frames[0]))
    frame_shape = first_frame.shape if first_frame is not None else (480, 640, 3)

    # 逐帧换脸
    written_count = 0
    for i, frame_path in enumerate(frames):
        target_img = cv2.imread(str(frame_path))
        if target_img is None:
            # 读取失败，用黑帧占位
            print(f"    警告: 无法读取帧 {frame_path.name}，使用黑帧占位", flush=True)
            placeholder = np.zeros(frame_shape, dtype=np.uint8)
            out_path = os.path.join(output_frames_dir, frame_path.name)
            ok = cv2.imwrite(out_path, placeholder)
            if not ok:
                print(f"    ❌ 写入失败: {frame_path.name}", flush=True)
            else:
                written_count += 1
            continue

        # 检测目标人脸
        target_faces = app.get(target_img)

        if not source_faces or not target_faces:
            # 无脸帧：写原帧（保证帧连续性）
            out_path = os.path.join(output_frames_dir, frame_path.name)
            ok = cv2.imwrite(out_path, target_img)
            if not ok:
                print(f"    ❌ 写入失败: {frame_path.name}", flush=True)
            else:
                written_count += 1
            continue

        # 选最大人脸
        best_face = max(target_faces, key=lambda f: (f.bbox[2]-f.bbox[0]) * (f.bbox[3]-f.bbox[1]))

        # 换脸
        result = swapper.get(target_img.copy(), best_face, source_faces[0], paste_back=True)

        # GFPGAN修复
        if restorer:
            try:
                _, _, restored = restorer.enhance(
                    result, has_aligned=False, only_center_face=False,
                    paste_back=True, weight=0.5
                )
                if restored is not None:
                    result = restored
            except:
                pass

        out_path = os.path.join(output_frames_dir, frame_path.name)
        ok = cv2.imwrite(out_path, result)
        if not ok:
            print(f"    ❌ 写入失败: {frame_path.name}", flush=True)
        else:
            written_count += 1

    # 验证帧完整性
    swapped_frames = sorted(Path(output_frames_dir).glob('frame_*.png'))
    if len(swapped_frames) != len(frames):
        print(f"    ⚠️ 帧数不匹配: 期望 {len(frames)}，实际 {len(swapped_frames)}", flush=True)

    if len(swapped_frames) == 0:
        print(f"    ❌ 没有输出帧，跳过合成", flush=True)
        shutil.copy2(input_video, output_video)
        return 0

    # 合成视频（含音频）
    # 注意: -start_number 1 必须在 -i 之前，作用于 image2 demuxer
    ffmpeg_cmd = [
        'ffmpeg',
        '-start_number', '1',
        '-framerate', str(fps),
        '-i', os.path.join(output_frames_dir, 'frame_%04d.png'),
        '-i', input_video,
        '-c:v', 'libx264', '-c:a', 'aac',
        '-map', '0:v:0', '-map', '1:a:0?',
        '-pix_fmt', 'yuv420p',
        output_video, '-y'
    ]
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ffmpeg 编码失败: {result.stderr[-500:]}", flush=True)
        raise subprocess.CalledProcessError(result.returncode, ffmpeg_cmd)

    # 清理临时文件
    shutil.rmtree(frames_dir, ignore_errors=True)
    shutil.rmtree(output_frames_dir, ignore_errors=True)

    return written_count


def batch_face_swap(video_dir, face_dir, output_dir, fps=25):
    """批量处理目录下所有视频"""
    os.makedirs(output_dir, exist_ok=True)

    # 初始化模型
    print("初始化模型...")
    app, swapper = init_face_swap()
    restorer = init_gfpgan()
    # 源人脸检测用小尺寸（大特写图需要 det_size=320）
    app_src = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    app_src.prepare(ctx_id=0, det_size=(320, 320))

    # 优先使用能检测到人脸的图片
    face_img_path = None
    candidates = sorted(Path(face_dir).glob("*.png")) + sorted(Path(face_dir).glob("*.jpg"))
    for f in candidates:
        if 'face' in f.stem.lower():
            test_img = cv2.imread(str(f))
            if test_img is not None:
                h, w = test_img.shape[:2]
                test_small = cv2.resize(test_img, (640, int(640 * h / w))) if max(h, w) > 1000 else test_img
                test_faces = app_src.get(test_small)
                if test_faces:
                    face_img_path = f
                    print(f"  人脸源(带face): {f.name} ({len(test_faces)} 人脸)")
                    break
    if face_img_path is None:
        for f in candidates:
            test_img = cv2.imread(str(f))
            if test_img is not None:
                h, w = test_img.shape[:2]
                test_small = cv2.resize(test_img, (640, int(640 * h / w))) if max(h, w) > 1000 else test_img
                test_faces = app_src.get(test_small)
                if test_faces:
                    face_img_path = f
                    print(f"  人脸源(自动): {f.name} ({len(test_faces)} 人脸)")
                    break

    if face_img_path is None:
        print(f"错误: {face_dir} 中未找到可检测到人脸的图片")
        return

    print(f"人脸源: {face_img_path}")
    source_img = cv2.imread(str(face_img_path))
    # 缓存源人脸检测结果
    source_faces_cached = app_src.get(source_img) if max(source_img.shape[:2]) <= 800 else app_src.get(cv2.resize(source_img, (320, int(320 * source_img.shape[0] / source_img.shape[1]))))
    print(f"  源人脸检测: {len(source_faces_cached)} 个 (缓存)")

    # 找到所有视频
    videos = sorted(Path(video_dir).glob("*.mp4")) + sorted(Path(video_dir).glob("*.avi"))
    if not videos:
        print(f"错误: {video_dir} 中未找到视频文件")
        return

    print(f"找到 {len(videos)} 个视频")

    for vid_idx, video_path in enumerate(videos):
        print(f"\n{'='*60}")
        print(f"[{vid_idx+1}/{len(videos)}] 处理: {video_path.name}")
        print(f"{'='*60}")

        # 获取原始帧率
        orig_fps = get_video_fps(str(video_path))
        use_fps = max(orig_fps, fps)  # 用较高帧率，避免丢帧
        print(f"  原始帧率: {orig_fps:.2f}, 使用帧率: {use_fps}")

        # 分割视频
        temp_dir = os.path.join(output_dir, f"_temp_{video_path.stem}")
        segments, duration = split_video(str(video_path), temp_dir, MAX_SEGMENT_SEC)
        print(f"  时长: {duration:.1f}s, 分为 {len(segments)} 段")

        # 逐段换脸
        swapped_segments = []
        for seg_idx, seg_path in enumerate(segments):
            seg_output = seg_path.replace(".mp4", "_swapped.mp4")
            # 断点续传：跳过已完成的片段
            if os.path.exists(seg_output) and os.path.getsize(seg_output) > 1000:
                swapped_segments.append(seg_output)
                print(f"\n  跳过片段 {seg_idx+1}/{len(segments)}: 已存在 {Path(seg_output).name}")
                continue
            print(f"\n  处理片段 {seg_idx+1}/{len(segments)}: {Path(seg_path).name}")
            n_frames = process_video_segment(
                app, swapper, restorer, source_img,
                seg_path, seg_output, use_fps,
                source_faces_cache=source_faces_cached
            )
            swapped_segments.append(seg_output)
            print(f"    完成: {n_frames} 帧")

        # 合并片段
        final_output = os.path.join(output_dir, f"{video_path.stem}_faceswap.mp4")
        if len(swapped_segments) == 1:
            shutil.move(swapped_segments[0], final_output)
        else:
            merge_videos(swapped_segments, final_output)

        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)

        # 验证输出
        if os.path.exists(final_output):
            size_mb = os.path.getsize(final_output) / 1e6
            print(f"\n✅ 完成: {final_output} ({size_mb:.1f}MB)")
        else:
            print(f"\n❌ 失败: {final_output}")


def main():
    parser = argparse.ArgumentParser(description='批量视频换脸工具')
    parser.add_argument('--video-dir', default='input/todo/swap_face',
                        help='视频目录')
    parser.add_argument('--face-dir', default='input/todo/face/model1',
                        help='人脸源目录')
    parser.add_argument('--output-dir', default='output/batch_faceswap',
                        help='输出目录')
    parser.add_argument('--fps', type=int, default=25, help='帧率')
    parser.add_argument('--max-segment', type=int, default=15,
                        help='最大片段时长(秒)')
    args = parser.parse_args()

    global MAX_SEGMENT_SEC
    MAX_SEGMENT_SEC = args.max_segment

    print("=== 批量视频换脸工具 v2 ===")
    print(f"视频目录: {args.video_dir}")
    print(f"人脸目录: {args.face_dir}")
    print(f"输出目录: {args.output_dir}")
    print(f"最大片段: {args.max_segment}s")

    batch_face_swap(args.video_dir, args.face_dir, args.output_dir, args.fps)

    print("\n=== 全部完成 ===")


if __name__ == '__main__':
    main()
