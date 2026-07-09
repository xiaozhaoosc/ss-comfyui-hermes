"""媒体工具函数：ffmpeg/ffprobe 封装、中文路径安全的图像 IO"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import cv2
import numpy as np


def imread_unicode(path) -> np.ndarray | None:
    """中文路径安全的图像读取（cv2.imread 不支持中文路径）"""
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path, img: np.ndarray) -> bool:
    """中文路径安全的图像写入"""
    ext = os.path.splitext(str(path))[1]
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(str(path))
        return True
    return False


def get_video_duration(video_path) -> float:
    """获取视频时长(秒)"""
    cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
           '-of', 'csv=p=0', str(video_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def get_video_fps(video_path) -> float:
    """获取视频原始帧率"""
    cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
           '-show_entries', 'stream=r_frame_rate',
           '-of', 'csv=p=0', str(video_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        fps_str = result.stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            return float(num) / float(den)
        return float(fps_str)
    except Exception:
        return 25.0


def get_video_resolution(video_path) -> tuple[int, int]:
    """获取视频分辨率 (width, height)"""
    cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
           '-show_entries', 'stream=width,height',
           '-of', 'csv=p=0', str(video_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        w, h = result.stdout.strip().split(',')
        return int(w), int(h)
    except Exception:
        return 0, 0


def split_video(video_path, output_dir, segment_sec: float = 15.0):
    """将长视频分割为多个片段，返回 (片段列表, 总时长)"""
    os.makedirs(output_dir, exist_ok=True)
    duration = get_video_duration(video_path)

    if duration <= 0:
        duration = 0.0

    if duration <= segment_sec:
        out_path = os.path.join(output_dir, "segment_000.mp4")
        if not os.path.exists(out_path):
            import shutil
            shutil.copy2(video_path, out_path)
        return [out_path], duration

    n_segments = int(np.ceil(duration / segment_sec))
    segments = []
    for i in range(n_segments):
        start = i * segment_sec
        out_path = os.path.join(output_dir, f"segment_{i:03d}.mp4")
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-ss', str(start), '-t', str(segment_sec),
            '-c:v', 'libx264', '-c:a', 'aac',
            out_path, '-y'
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        segments.append(out_path)
    return segments, duration


def merge_videos(segment_paths, output_path):
    """将多个视频片段合并为一个"""
    list_path = str(output_path) + ".concat.txt"
    with open(list_path, 'w', encoding='utf-8') as f:
        for seg in segment_paths:
            f.write(f"file '{os.path.abspath(seg)}'\n")

    cmd = [
        'ffmpeg', '-f', 'concat', '-safe', '0',
        '-i', list_path,
        '-c:v', 'libx264', '-c:a', 'aac',
        '-pix_fmt', 'yuv420p',
        str(output_path), '-y'
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    os.remove(list_path)


def list_videos(directory) -> list[Path]:
    """列出目录下所有视频文件"""
    d = Path(directory)
    exts = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm'}
    return sorted([p for p in d.iterdir() if p.suffix.lower() in exts])


def list_images(directory) -> list[Path]:
    """列出目录下所有图片文件"""
    d = Path(directory)
    exts = {'.png', '.jpg', '.jpeg', '.bmp', '.webp'}
    return sorted([p for p in d.iterdir() if p.suffix.lower() in exts])


def list_audios(directory) -> list[Path]:
    """列出目录下所有音频文件"""
    d = Path(directory)
    exts = {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg'}
    return sorted([p for p in d.iterdir() if p.suffix.lower() in exts])
