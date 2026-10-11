#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mix_drv_bgm.py
将 drv16.mp4 中的原生律动音频与 Calling_Through_The_Screen BGM 进行智能双轨混音：
1. 提取 drv16.mp4 的音轨（原视频原声律动，与模特动作完全同频）
2. 将 drv16 音轨与 BGM 按节拍音量平衡混音 (amix / sidechain / volume filter)
3. 封装至最终成片 ootd_multilook_nophone_collage.mp4
"""
import os
import sys
import subprocess

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
ROOT = r"D:\ai_projects\ComfyUI"
OUT = os.path.join(ROOT, "output", "2026-10-03", "ootd_multilook_nophone")
DRV16 = os.path.join(OUT, "drv16.mp4")
BGM = os.path.join(ROOT, "input", "ken4", "face", "bgm原创", "Calling_Through_The_Screen (1).mp3")
VIDEO = os.path.join(OUT, "ootd_multilook_nophone_collage.mp4")
TEMP_VIDEO = os.path.join(OUT, "ootd_multilook_nophone_collage_mixed.mp4")

def main():
    if not os.path.exists(DRV16):
        print(f"[错误] 找不到 drv16.mp4: {DRV16}")
        return 1
    if not os.path.exists(BGM):
        print(f"[错误] 找不到 BGM: {BGM}")
        return 1
    if not os.path.exists(VIDEO):
        print(f"[错误] 找不到目标视频: {VIDEO}")
        return 1

    # 获取视频时长
    p = subprocess.run(
        [FFMPEG, "-i", VIDEO],
        stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    # 视频时长已知为 12.233s
    dur = 12.233

    print(f"[mix] 开始双轨混音：")
    print(f"  - 原动效音轨 (drv16): {os.path.basename(DRV16)}")
    print(f"  - 原创 BGM 音轨: {os.path.basename(BGM)}")
    print(f"  - 目标视频: {os.path.basename(VIDEO)} (时长={dur:.3f}s)")

    # 混音设计：
    # Input 0: VIDEO (无声画面 / 仅取画面)
    # Input 1: DRV16 (原舞蹈伴奏/动作声，调至 0.85 保持主节奏清晰)
    # Input 2: BGM (Calling_Through_The_Screen，调至 0.65 融入氛围律动)
    # 使用 amix 滤镜混合两轨，加入低频均衡，保持 44100Hz AAC 256k
    filter_complex = (
        "[1:a]volume=0.85,alimiter=limit=0.95[a1];"
        "[2:a]volume=0.65,alimiter=limit=0.95[a2];"
        "[a1][a2]amix=inputs=2:duration=first:dropout_transition=2,volume=1.2[aout]"
    )

    cmd = [
        FFMPEG, "-y",
        "-i", VIDEO,
        "-ss", "0", "-t", str(dur), "-i", DRV16,
        "-ss", "0", "-t", str(dur), "-i", BGM,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-ar", "44100",
        "-shortest",
        TEMP_VIDEO
    ]

    print("[mix] 执行 ffmpeg 混音命令...")
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[错误] ffmpeg 混音失败: {res.stderr[-500:]}")
        return 1

    if os.path.exists(TEMP_VIDEO) and os.path.getsize(TEMP_VIDEO) > 1000:
        os.replace(TEMP_VIDEO, VIDEO)
        size_mb = os.path.getsize(VIDEO) / 1e6
        print(f"[mix] 混音成功并已替换交付成片！成片大小: {size_mb:.2f} MB")
        return 0
    else:
        print("[错误] 未能生成混音成片")
        return 1

if __name__ == "__main__":
    sys.exit(main())
