#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 三轨智能声画同步混音引擎 (Voice-First / Narration-Centric Sync Engine)

架构规范：
1. 【Track 1 旁白语音轨】：
   - 微软高保真 Edge-TTS（zh-CN-YunjianNeural 沧桑厚重正剧老生音色）。
   - 镜头切入后延后 0.35s 进声（“见画后发声”，符合经典影视剪辑黄金律）。
2. 【Track 2 动效与环境卡点轨】：
   - 在核心动作镜头（Shot 14 两军对撞、Shot 15 神驹衔箭、Shot 17 金刀挑潘、Shot 24 信炮爆闪等）
     在指定绝对毫秒点注入高保真打击音效与物理环境声。
3. 【Track 3 古风民乐 BGM 轨 + 智能侧链闪避 (Audio Ducking)】：
   - 旁白开讲时，BGM 自动平滑压低至 25% (-12dB)；
   - 旁白留白停顿时，BGM 浪涌升起至 85% (-1.5dB)，烘托历史沧桑史诗感。
4. 【画面与文字注解全流合璧】：
   - 华文楷体居中底字幕 + 右上角人物金石注疏名片 + 纯净三轨混流成片输出。
"""

import os
import sys
import json
import asyncio
import subprocess
import edge_tts
import numpy as np
from scipy.io import wavfile

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
OUTPUT_DIR = os.path.join(ROOT, "output", "2026-10-04", "yangjiajiang_ep01")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    import shutil
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

SAMPLE_RATE = 44100

from tools.subtitle_annotator import EP01_SUBTITLES, FONT_KAI, burn_subtitles_and_tags


async def synthesize_sentence(text, voice, out_path, max_retries=4):
    """使用 Edge-TTS 异步合成单句干音（带超时自动重试）"""
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-4%", pitch="-2Hz")
            await communicate.save(out_path)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
                return
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2.0)


def generate_all_narration_track(shots, output_wav_path, voice="zh-CN-YunjianNeural"):
    """为指定分镜序列生成连续对齐的旁白干音轨"""
    total_sec = sum(s["sec"] for s in shots)
    total_samples = int(total_sec * SAMPLE_RATE)
    full_voice = np.zeros(total_samples, dtype=np.float32)

    temp_tts_dir = os.path.join(OUTPUT_DIR, "temp_tts")
    os.makedirs(temp_tts_dir, exist_ok=True)

    cur_time = 0.0
    print(f"\n=== 1. 正在生成 Edge-TTS 评书历史正剧旁白音轨 ({voice}) ===")
    
    for s in shots:
        dur = s["sec"]
        text = s.get("sub", "").strip()
        if not text:
            cur_time += dur
            continue

        tts_mp3 = os.path.join(temp_tts_dir, f"tts_shot_{s['id']:02d}.mp3")
        tts_wav = os.path.join(temp_tts_dir, f"tts_shot_{s['id']:02d}.wav")

        if not os.path.exists(tts_wav):
            asyncio.run(synthesize_sentence(text, voice, tts_mp3))
            # 转为 44100Hz 单声道 wav
            conv_cmd = [FFMPEG, "-y", "-i", tts_mp3, "-ar", str(SAMPLE_RATE), "-ac", "1", tts_wav]
            subprocess.run(conv_cmd, capture_output=True, check=True)

        sr, data = wavfile.read(tts_wav)
        data = data.astype(np.float32)
        if np.max(np.abs(data)) > 0:
            data = data / np.max(np.abs(data)) * 0.95

        # 镜头切入 0.35 秒后进旁白
        start_sec = cur_time + 0.35
        start_idx = int(start_sec * SAMPLE_RATE)
        end_idx = start_idx + len(data)

        # 若旁白过长，在镜头结束前 0.15 秒淡出，避免与下一镜对撞
        max_end_idx = int((cur_time + dur - 0.15) * SAMPLE_RATE)
        if end_idx > max_end_idx:
            data = data[:max_end_idx - start_idx]
            end_idx = max_end_idx

        if end_idx <= total_samples:
            full_voice[start_idx:end_idx] += data[:end_idx - start_idx]
            print(f"  [旁白对齐] 镜 {s['id']:02d} ({s['sec']}s): \"{text[:18]}...\" -> {start_sec:.2f}s~{end_idx/SAMPLE_RATE:.2f}s")

        cur_time += dur

    # 保存整轨旁白 WAV
    voice_int16 = (full_voice * 32767).astype(np.int16)
    wavfile.write(output_wav_path, SAMPLE_RATE, voice_int16)
    print(f"  -> 旁白整轨已生成: {output_wav_path}")
    return output_wav_path, full_voice


def generate_foley_sfx_track(shots, output_wav_path):
    """针对关键动作瞬间注入打击音效与环境音（Track 2）"""
    total_sec = sum(s["sec"] for s in shots)
    total_samples = int(total_sec * SAMPLE_RATE)
    foley = np.zeros(total_samples, dtype=np.float32)

    cur_time = 0.0
    for s in shots:
        dur = s["sec"]
        s_id = s["id"]

        # Shot 14: 两军铁骑对撞冲击音效 (大低频撞击 + 金属刀枪震鸣)
        if s_id == 14:
            hit_t = cur_time + 1.2
            idx = int(hit_t * SAMPLE_RATE)
            l = int(1.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.5, l, endpoint=False)
                impact = (np.sin(2 * np.pi * 48 * t) * 0.8 + np.sin(2 * np.pi * 96 * t) * 0.3) * np.exp(-t * 3.5)
                clang = (np.sin(2 * np.pi * 880 * t) * 0.3 + np.sin(2 * np.pi * 1760 * t) * 0.15) * np.exp(-t * 7.0)
                foley[idx:idx + l] += (impact + clang).astype(np.float32) * 0.85

        # Shot 15: 神驹衔箭 (利箭破空呼啸 + 沉闷咬合声)
        elif s_id == 15:
            arrow_t = cur_time + 1.8
            idx = int(arrow_t * SAMPLE_RATE)
            l = int(1.2 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.2, l, endpoint=False)
                # 调频哨鸣破空声 (800Hz 快速滑向 1800Hz)
                freq_chirp = np.linspace(800, 1800, l)
                whistle = np.sin(2 * np.pi * freq_chirp * t) * np.exp(-t * 2.2) * 0.4
                # 咬合打击脉冲
                bite = (np.sin(2 * np.pi * 75 * t) * 0.7) * np.exp(-t * 12.0)
                foley[idx:idx + l] += (whistle + bite).astype(np.float32) * 0.75

        # Shot 17: 金刀挑落潘仁美 (厚重金戈击甲 + 沉重落马闷响)
        elif s_id == 17:
            strike_t = cur_time + 1.0
            idx = int(strike_t * SAMPLE_RATE)
            l = int(1.4 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.4, l, endpoint=False)
                blade = (np.sin(2 * np.pi * 659 * t) * 0.5 + np.sin(2 * np.pi * 1318 * t) * 0.25) * np.exp(-t * 6.0)
                thud = (np.sin(2 * np.pi * 50 * t) * 0.7) * np.exp(-t * 4.0)
                foley[idx:idx + l] += (blade + thud).astype(np.float32) * 0.8

        # Shot 24: 暗夜信炮白光爆闪 (剧烈爆炸低频轰鸣)
        elif s_id == 24:
            cannon_t = cur_time + 0.5
            idx = int(cannon_t * SAMPLE_RATE)
            l = int(2.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 2.5, l, endpoint=False)
                boom = (np.sin(2 * np.pi * 42 * t) * 0.9 + np.sin(2 * np.pi * 84 * t) * 0.4) * np.exp(-t * 1.8)
                foley[idx:idx + l] += boom.astype(np.float32) * 0.9

        # Shot 33: 红信炮冲天炸裂
        elif s_id == 33:
            burst_t = cur_time + 0.8
            idx = int(burst_t * SAMPLE_RATE)
            l = int(2.0 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 2.0, l, endpoint=False)
                burst = (np.sin(2 * np.pi * 52 * t) * 0.85) * np.exp(-t * 2.2)
                foley[idx:idx + l] += burst.astype(np.float32) * 0.85

        cur_time += dur

    max_v = np.max(np.abs(foley))
    if max_v > 0:
        foley = (foley / max_v) * 0.75

    foley_int16 = (foley * 32767).astype(np.int16)
    wavfile.write(output_wav_path, SAMPLE_RATE, foley_int16)
    print(f"  -> 关键帧音效打击轨已生成: {output_wav_path}")
    return output_wav_path, foley


def generate_ducked_bgm_track(total_sec, voice_array, output_wav_path):
    """生成具有历史厚重感的古风民乐 BGM，并根据旁白包络执行智能侧链闪避"""
    total_samples = int(total_sec * SAMPLE_RATE)
    t = np.linspace(0, total_sec, total_samples, endpoint=False)
    raw_bgm = np.zeros(total_samples, dtype=np.float32)

    # 1. 战阵律动大鼓 (每 1.2 秒一击深沉大皮鼓)
    for bt in np.arange(0.3, total_sec, 1.2):
        idx = int(bt * SAMPLE_RATE)
        l = int(0.7 * SAMPLE_RATE)
        if idx + l <= total_samples:
            dt = t[idx:idx + l] - bt
            decay = np.exp(-dt * 6.5)
            drum = (np.sin(2 * np.pi * 55.0 * dt) * 0.7 + np.sin(2 * np.pi * 110.0 * dt) * 0.25) * decay
            raw_bgm[idx:idx + l] += drum.astype(np.float32) * 0.65

    # 2. 沧桑古风管乐主旋律 (低音埙/箫 五音阶 D-E-G-A)
    notes = [146.8, 164.8, 196.0, 220.0, 293.6]
    for i, freq in enumerate(notes):
        envelope = (np.sin(2 * np.pi * (0.08 + i * 0.03) * t) ** 2) * 0.2
        tone = np.sin(2 * np.pi * freq * t) * 0.5 + np.sin(2 * np.pi * freq * 2.0 * t) * 0.2
        raw_bgm += (tone * envelope).astype(np.float32)

    # 3. 铜磬远鸣 (每 7 秒一声冷清大磬)
    for ct in np.arange(0.0, total_sec, 7.0):
        idx_c = int(ct * SAMPLE_RATE)
        l_c = int(3.5 * SAMPLE_RATE)
        if idx_c + l_c <= total_samples:
            dt_c = t[idx_c:idx_c + l_c] - ct
            decay_c = np.exp(-dt_c * 0.9)
            chime = (np.sin(2 * np.pi * 440.0 * dt_c) * 0.3 + np.sin(2 * np.pi * 880.0 * dt_c) * 0.15) * decay_c
            raw_bgm[idx_c:idx_c + l_c] += chime.astype(np.float32) * 0.5

    # 4. 侧链闪避计算 (Sidechain Ducking)
    # 当 voice_array 有声时，平滑计算增益曲线 (gain: 0.25 降至 -12dB；无声时恢复至 0.85)
    win_len = int(0.25 * SAMPLE_RATE)
    voice_power = np.abs(voice_array)
    # 简单移动均值获取包络
    from scipy.ndimage import uniform_filter1d
    smooth_env = uniform_filter1d(voice_power, size=win_len)
    # 增益映射：env > 0.08 时降至 0.28，env 小时为 0.85
    duck_gain = 0.85 - (smooth_env / (smooth_env + 0.1)) * 0.57
    ducked_bgm = raw_bgm * duck_gain

    max_v = np.max(np.abs(ducked_bgm))
    if max_v > 0:
        ducked_bgm = (ducked_bgm / max_v) * 0.82

    bgm_int16 = (ducked_bgm * 32767).astype(np.int16)
    wavfile.write(output_wav_path, SAMPLE_RATE, bgm_int16)
    print(f"  -> 智能侧链闪避 BGM 轨已生成: {output_wav_path}")
    return output_wav_path, ducked_bgm


def mix_three_tracks(voice_wav, foley_wav, bgm_wav, final_ost_path):
    """三轨母带级无损融合 (Voice 0.95 + Foley 0.75 + Ducked BGM 0.80)"""
    mix_cmd = [
        FFMPEG, "-y",
        "-i", voice_wav,
        "-i", foley_wav,
        "-i", bgm_wav,
        "-filter_complex",
        "[0:a]volume=1.0[v];"
        "[1:a]volume=0.9[f];"
        "[2:a]volume=0.85[b];"
        "[v][f][b]amix=inputs=3:duration=longest:dropout_transition=2[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        final_ost_path
    ]
    subprocess.run(mix_cmd, capture_output=True, check=True)
    print(f"\n[混音交付] 三轨母带级全景音轨已合成: {final_ost_path}")
    return final_ost_path


def render_perfect_synced_video(input_video, shots, output_final_mp4):
    """全自动三轨声画同步渲染总控"""
    temp_dir = os.path.join(OUTPUT_DIR, "synced_audio_temp")
    os.makedirs(temp_dir, exist_ok=True)

    voice_wav = os.path.join(temp_dir, "track1_narration.wav")
    foley_wav = os.path.join(temp_dir, "track2_foley_impact.wav")
    bgm_wav = os.path.join(temp_dir, "track3_ducked_bgm.wav")
    master_ost = os.path.join(temp_dir, "master_three_track_ost.wav")

    # 1. 生成旁白轨
    _, voice_arr = generate_all_narration_track(shots, voice_wav)

    # 2. 生成关键帧音效打击轨
    generate_foley_sfx_track(shots, foley_wav)

    # 3. 生成智能侧链闪避 BGM 轨
    total_sec = sum(s["sec"] for s in shots)
    generate_ducked_bgm_track(total_sec, voice_arr, bgm_wav)

    # 4. 融合三轨
    mix_three_tracks(voice_wav, foley_wav, bgm_wav, master_ost)

    # 5. 视频流剥离旧音频，混入全新三轨 OST
    temp_mux = os.path.join(temp_dir, "temp_video_with_master_ost.mp4")
    mux_cmd = [
        FFMPEG, "-y",
        "-i", input_video,
        "-i", master_ost,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        temp_mux
    ]
    print(f"\n=== 正在混流纯净三轨音轨至画面 ===")
    subprocess.run(mux_cmd, capture_output=True, check=True)

    # 6. 烧录华文楷体字幕与右上角金石注解卡
    print(f"\n=== 正在烧录影视级楷体字幕与注疏名片 ===")
    burn_subtitles_and_tags(temp_mux, output_final_mp4, shots)

    print(f"\n=======================================================")
    print(f"  【全链路交付】三轨声画完全同步成片已生成！")
    print(f"  文件位置: {output_final_mp4}")
    print(f"=======================================================\n")
    return output_final_mp4


if __name__ == "__main__":
    # 默认跑已完成的 Act 1~4 全集
    shots_1_to_4 = [s for s in EP01_SUBTITLES if s["id"] <= 33]
    in_video = os.path.join(FINAL_DIR, "北宋杨家将_第01集_Act1至Act4全连贯大片_annotated.mp4")
    out_video = os.path.join(FINAL_DIR, "北宋杨家将_第01集_Act1至Act4_三轨声画完全同步版.mp4")

    if os.path.exists(in_video):
        render_perfect_synced_video(in_video, shots_1_to_4, out_video)
    else:
        print(f"未找到输入视频: {in_video}")
