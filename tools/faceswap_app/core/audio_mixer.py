"""BGM 混音模块：原音 + BGM 混合，可调音量比例

使用 ffmpeg amix filter 实现：
- 视频原音轨 + BGM 音轨混合
- BGM 不足自动循环
- 原音/BGM 音量独立可调
- 无原音时仅用 BGM
- 无 BGM 时直接复制
"""
from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path

from .media_utils import list_audios


def _probe_has_audio(video_path: str) -> bool:
    """检测视频是否含音频轨"""
    cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'a',
           '-show_entries', 'stream=codec_type',
           '-of', 'csv=p=0', str(video_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return 'audio' in r.stdout


def _pick_bgm(bgm_source: str, bgm_random: bool) -> str | None:
    """从文件或目录中选取 BGM"""
    p = Path(bgm_source)
    if p.is_file():
        return str(p)
    if p.is_dir():
        audios = list_audios(p)
        if not audios:
            return None
        if bgm_random:
            return str(random.choice(audios))
        return str(audios[0])
    return None


def mix_bgm(input_video: str, output_video: str,
            bgm_source: str,
            bgm_random: bool = False,
            keep_original_audio: bool = True,
            bgm_volume: float = 0.5,
            original_volume: float = 1.0) -> str:
    """将 BGM 混入视频

    Args:
        input_video: 输入视频路径（已换脸，含或不含原音）
        output_video: 输出视频路径
        bgm_source: BGM 文件或目录
        bgm_random: 目录模式下是否随机选
        keep_original_audio: 是否保留原音（True=混合，False=仅 BGM）
        bgm_volume: BGM 音量 0~1
        original_volume: 原音音量 0~1

    Returns:
        输出视频路径
    """
    bgm_path = _pick_bgm(bgm_source, bgm_random)
    if bgm_path is None:
        # 没有 BGM 可用，直接复制
        import shutil
        shutil.copy2(input_video, output_video)
        return output_video

    has_audio = _probe_has_audio(input_video)

    # 情况 1: 无原音 或 不保留原音 -> 仅用 BGM 替换音轨
    if not has_audio or not keep_original_audio:
        cmd = [
            'ffmpeg', '-y',
            '-i', input_video,
            '-stream_loop', '-1', '-i', bgm_path,
            '-map', '0:v:0', '-map', '1:a:0',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            '-filter:a', f'volume={bgm_volume}',
            str(output_video),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg BGM 替换失败: {r.stderr[-300:]}")
        return output_video

    # 情况 2: 原音 + BGM 混合（amix filter）
    # [0:a]volume=原音音量[a0]; [1:a]volume=bgm音量[a1]; [a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]
    filter_complex = (
        f"[0:a]volume={original_volume}[a0];"
        f"[1:a]volume={bgm_volume}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    cmd = [
        'ffmpeg', '-y',
        '-i', input_video,
        '-stream_loop', '-1', '-i', bgm_path,
        '-filter_complex', filter_complex,
        '-map', '0:v:0', '-map', '[aout]',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-shortest',
        str(output_video),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # 混合失败时回退：保留原音复制
        import shutil
        shutil.copy2(input_video, output_video)
        raise RuntimeError(f"ffmpeg 混音失败(已回退保留原音): {r.stderr[-300:]}")
    return output_video
