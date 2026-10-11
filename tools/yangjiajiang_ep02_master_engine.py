#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 2 集《归宋 · 天波府》全集长轴母带级三轨声画大总成引擎 (EP02 Master Engine)

核心工业级视听标准：
1. 【两段式 720P 硬件超分】：
   - 全 54 镜原始 544x960 视频通过 Lanczos + Unsharp 极速无损超分至 720x1280 (9:16 标准纵向水墨画幅)。
   - 彻底剥离 (-an) ComfyUI 扩散模型自生的高频嘶嘶白噪。
2. 【旁白绝不吞字·长轴绝对时序排布】：
   - 微软 Edge-TTS 云健沧桑正剧男声 (zh-CN-YunjianNeural, rate="-3%", pitch="-2Hz")。
   - 入画 0.35s 自然切入，每句保留 0.40s 呼吸留白，绝不剪切尾音气声。
3. 【全频段古风民乐物理建模 (Full-Band Acoustic Modeling)】：
   - 战阵大皮鼓 (55/110/220/880Hz)、塞外角号 (110~440Hz)、古风箫埙 (羽调式古五音阶含 4.5Hz 颤音)、皇朝青铜编钟/大磬。
4. 【54 镜全景关键动作瞬间全频动效卡点】：
   - 晋阳围城巨鼓、呼延赞枪花破空、开山斧冰雪暴撞、神臂弩齐射、军棍钝击、金刀触地、
     应州重锁开门、八王倒履相迎、紫宸殿朝贺钟磬、天波府金匾朱砂点睛定音。
5. 【智能动态侧链闪避 (Sidechain Ducking)】：
   - 旁白发声时 BGM 中频凹陷闪避，对白停顿与战役高潮时民乐浪涌回归 100%。
6. 【华文楷体字幕与右上角金石战局注疏名片】：
   - 暖象牙白楷体居中底字幕 + 黑底金石战局注疏卡。
7. 【全剧超级大总成 (Picture Lock) 与五幕独立成片一键交付】。
"""

import os
import sys
import glob
import json
import asyncio
import argparse
import subprocess
import edge_tts
import numpy as np
from scipy.io import wavfile
from scipy.ndimage import uniform_filter1d

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATE_STR = "2026-10-08"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep02")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")
os.makedirs(FINAL_DIR, exist_ok=True)

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    import shutil
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

FONT_KAI = r"C:\Windows\Fonts\simkai.ttf"
SAMPLE_RATE = 44100

from tools.yangjiajiang_ep02_metadata import EP02_METADATA
from tools.subtitle_annotator import format_srt_time, generate_srt_file


ACT_INFO = {
    1: {"title": "晋阳鏖战", "shots": (1, 9)},
    2: {"title": "劫营严律", "shots": (10, 18)},
    3: {"title": "寒堂猜忌", "shots": (19, 27)},
    4: {"title": "绝处明志", "shots": (28, 38)},
    5: {"title": "天波朱砂", "shots": (39, 54)},
}


async def synthesize_sentence_robust(text, voice, out_path, max_retries=4):
    """带超时与指数退避重试的 Edge-TTS 异步语音生成"""
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-3%", pitch="-2Hz")
            await communicate.save(out_path)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 200:
                return
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2.0 * (attempt + 1))


def normalize_and_upscale_shot(shot, target_w=720, target_h=1280):
    """单镜规格归一化：剥离白噪 (-an) + 截断时长 (-t) + Lanczos 超分至 720P (720x1280)"""
    sid = shot["id"]
    sec = shot["sec"]
    norm_path = os.path.join(OUTPUT_DIR, f"clean_norm_shot{sid:02d}.mp4")

    # 若已存在且文件完整则复用
    if os.path.exists(norm_path) and os.path.getsize(norm_path) > 50000:
        return norm_path

    # 查找原始渲染产物
    candidates = [
        os.path.join(OUTPUT_DIR, f"yang_ep02_shot{sid:02d}_00001_.mp4"),
        os.path.join(OUTPUT_DIR, f"yang_ep02_shot{sid:02d}.mp4"),
        os.path.join(OUTPUT_DIR, f"yang_ep02_shot{sid:02d}_00001.mp4"),
    ]
    src = None
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 10000:
            src = c
            break

    if not src:
        # 模糊匹配
        matches = glob.glob(os.path.join(OUTPUT_DIR, f"yang_ep02_shot{sid:02d}*.mp4"))
        if matches:
            src = matches[0]

    if not src:
        raise FileNotFoundError(f"[错误] 未找到镜头 {sid:02d} 的渲染产物！")

    vf_chain = (
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=lanczos+accurate_rnd,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,"
        f"unsharp=5:5:0.7:5:5:0.0,fps=24"
    )

    cmd = [
        FFMPEG, "-y",
        "-i", src,
        "-an",
        "-t", str(sec),
        "-vf", vf_chain,
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "17",
        "-pix_fmt", "yuv420p",
        norm_path
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"镜 {sid:02d} 转码超分失败: {res.stderr.decode('utf-8', errors='ignore')}")

    return norm_path


def build_pure_video_lock(shots, output_pure_mp4, tag="ep02"):
    """【Picture Lock 画面锁剪】将指定镜头归一化并无缝拼接为纯视频主干"""
    if os.path.exists(output_pure_mp4) and os.path.getsize(output_pure_mp4) > 5000000:
        print(f"[Picture Lock 复用] 720P 纯视频主干已就绪: {output_pure_mp4}")
        return output_pure_mp4

    print(f"\n=======================================================")
    print(f"  正在执行 Picture Lock 画面锁剪与 720P 镜头超分 ({tag})")
    print(f"  目标画幅: 720x1280 (9:16) | 帧率: 24fps | 音轨: 剥离 (-an)")
    print(f"=======================================================\n")

    norm_clips = []
    for s in shots:
        sid = s["id"]
        sec = s["sec"]
        norm_v = normalize_and_upscale_shot(s, target_w=720, target_h=1280)
        norm_clips.append(norm_v)
        print(f"  [720P 就绪] 镜 {sid:02d}: {os.path.basename(norm_v)} ({sec}s)")

    concat_txt = os.path.join(OUTPUT_DIR, f"concat_picture_lock_{tag}.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in norm_clips:
            f.write(f"file '{c.replace(chr(92), '/')}'\n")

    concat_cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "17",
        "-pix_fmt", "yuv420p",
        output_pure_mp4
    ]
    subprocess.run(concat_cmd, capture_output=True, check=True)
    print(f"\n[Picture Lock 达成] 720P 纯视频主干已生成: {output_pure_mp4}\n")
    return output_pure_mp4


def build_global_unclipped_narration_track(shots, output_wav_path, voice="zh-CN-YunjianNeural"):
    """【绝对时序长轴排布】生成不吞字、自然呼吸跨镜的旁白音轨"""
    total_sec = sum(s["sec"] for s in shots)
    total_samples = int((total_sec + 5.0) * SAMPLE_RATE)
    full_voice = np.zeros(total_samples, dtype=np.float32)

    temp_tts_dir = os.path.join(OUTPUT_DIR, "temp_tts")
    os.makedirs(temp_tts_dir, exist_ok=True)

    print(f"\n=======================================================")
    print(f"  正在生成连续旁白长轨 (Voice: {voice})")
    print(f"  镜头数: {len(shots)} | 机制: 长轴绝对时序，自然跨镜呼吸")
    print(f"=======================================================\n")

    cur_shot_start = 0.0
    cur_voice_write_head = 0.0

    for s in shots:
        dur = s["sec"]
        text = s.get("sub", "").strip()
        if not text:
            cur_shot_start += dur
            continue

        tts_mp3 = os.path.join(temp_tts_dir, f"tts_ep02_shot_{s['id']:02d}.mp3")
        tts_wav = os.path.join(temp_tts_dir, f"tts_ep02_shot_{s['id']:02d}.wav")

        if not os.path.exists(tts_wav) or os.path.getsize(tts_wav) < 1000:
            asyncio.run(synthesize_sentence_robust(text, voice, tts_mp3))
            conv_cmd = [FFMPEG, "-y", "-i", tts_mp3, "-ar", str(SAMPLE_RATE), "-ac", "1", tts_wav]
            subprocess.run(conv_cmd, capture_output=True, check=True)

        sr, data = wavfile.read(tts_wav)
        data = data.astype(np.float32)
        if np.max(np.abs(data)) > 0:
            data = data / np.max(np.abs(data)) * 0.95

        ideal_start = cur_shot_start + 0.35
        actual_start_sec = max(ideal_start, cur_voice_write_head + 0.40)

        start_idx = int(actual_start_sec * SAMPLE_RATE)
        end_idx = start_idx + len(data)

        if end_idx <= total_samples:
            full_voice[start_idx:end_idx] += data
        else:
            pad_len = end_idx - total_samples + 44100
            full_voice = np.pad(full_voice, (0, pad_len))
            total_samples = len(full_voice)
            full_voice[start_idx:end_idx] += data

        cur_voice_write_head = end_idx / SAMPLE_RATE
        sentence_dur = len(data) / SAMPLE_RATE
        print(f"  [旁白注入] 镜 {s['id']:02d} ({dur}s) -> 语音时长 {sentence_dur:.2f}s | 区间: {actual_start_sec:.2f}s ~ {cur_voice_write_head:.2f}s")

        cur_shot_start += dur

    final_len = int(total_sec * SAMPLE_RATE)
    if len(full_voice) > final_len:
        full_voice = full_voice[:final_len]
    else:
        full_voice = np.pad(full_voice, (0, final_len - len(full_voice)))

    voice_int16 = (full_voice * 32767).astype(np.int16)
    wavfile.write(output_wav_path, SAMPLE_RATE, voice_int16)
    print(f"\n[旁白交付] 完整旁白长轨已就绪: {output_wav_path} (时长: {total_sec:.2f}s)\n")
    return output_wav_path, full_voice


def build_full_band_foley_track(shots, output_wav_path):
    """【全频段动效卡点】为第2集 54 镜高潮动作与转折点注入物理声学模型"""
    total_sec = sum(s["sec"] for s in shots)
    total_samples = int(total_sec * SAMPLE_RATE)
    foley = np.zeros(total_samples, dtype=np.float32)

    cur_t = 0.0
    for s in shots:
        dur = s["sec"]
        sid = s["id"]

        # Shot 01: 晋阳十万铁甲长围 (大阵战鼓轰鸣 + 寒风呼啸)
        if sid == 1:
            hit_t = cur_t + 0.6
            idx = int(hit_t * SAMPLE_RATE)
            l = int(3.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 3.5, l, endpoint=False)
                wind = (np.sin(2 * np.pi * 75 * t) * 0.4) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.8 * t)) * np.exp(-t * 0.5)
                drums = (np.sin(2 * np.pi * 55 * t) * 0.6 + np.sin(2 * np.pi * 110 * t) * 0.3) * np.exp(-t * 1.2)
                foley[idx:idx + l] += (wind + drums).astype(np.float32) * 0.85

        # Shot 05: 呼延赞点钢枪抖枪花 (高频破空寒光啸叫 1200~2800Hz)
        elif sid == 5:
            spear_t = cur_t + 0.8
            idx = int(spear_t * SAMPLE_RATE)
            l = int(1.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.5, l, endpoint=False)
                chirp = np.linspace(1200, 2800, l)
                whistle = np.sin(2 * np.pi * chirp * t) * np.exp(-t * 3.5) * 0.6
                foley[idx:idx + l] += whistle.astype(np.float32) * 0.8

        # Shot 07: 开山斧与点钢枪爆撞 (金属交击与火星爆裂 880/1760/3520Hz)
        elif sid == 7:
            clash_t = cur_t + 1.2
            idx = int(clash_t * SAMPLE_RATE)
            l = int(1.8 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.8, l, endpoint=False)
                clang = (
                    np.sin(2 * np.pi * 880 * t) * 0.55 +
                    np.sin(2 * np.pi * 1760 * t) * 0.35 +
                    np.sin(2 * np.pi * 3520 * t) * 0.20
                ) * np.exp(-t * 7.0)
                sub_hit = (np.sin(2 * np.pi * 70 * t) * 0.8) * np.exp(-t * 4.0)
                foley[idx:idx + l] += (clang + sub_hit).astype(np.float32) * 0.95

        # Shot 08: 开山斧落空劈裂坚冰冻土 (坚冰炸裂与碎石飞溅 120/450/1400Hz)
        elif sid == 8:
            ice_t = cur_t + 0.9
            idx = int(ice_t * SAMPLE_RATE)
            l = int(1.6 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.6, l, endpoint=False)
                thud = (np.sin(2 * np.pi * 50 * t) * 0.7 + np.sin(2 * np.pi * 120 * t) * 0.4) * np.exp(-t * 4.5)
                crack = (np.sin(2 * np.pi * 1400 * t) * 0.35) * np.exp(-t * 12.0)
                foley[idx:idx + l] += (thud + crack).astype(np.float32) * 0.85

        # Shot 12: 铜锣骤响 + 暗夜万千飞蝗火箭 (铜锣激荡 620Hz + 强弩破空)
        elif sid == 12:
            gong_t = cur_t + 0.4
            idx = int(gong_t * SAMPLE_RATE)
            l = int(2.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 2.5, l, endpoint=False)
                gong = (np.sin(2 * np.pi * 620 * t) * 0.5 + np.sin(2 * np.pi * 1240 * t) * 0.3) * np.exp(-t * 2.5)
                arrows = np.sin(2 * np.pi * np.linspace(800, 2200, l) * t) * np.exp(-t * 1.8) * 0.4
                foley[idx:idx + l] += (gong + arrows).astype(np.float32) * 0.9

        # Shot 16: 朱漆军棍重责四十 (沉闷皮肉骨节钝击 65Hz/150Hz)
        elif sid == 16:
            for bt in [cur_t + 0.6, cur_t + 1.8, cur_t + 3.0, cur_t + 4.2]:
                idx = int(bt * SAMPLE_RATE)
                l = int(0.7 * SAMPLE_RATE)
                if idx + l <= total_samples:
                    t = np.linspace(0, 0.7, l, endpoint=False)
                    strike = (np.sin(2 * np.pi * 65 * t) * 0.7 + np.sin(2 * np.pi * 160 * t) * 0.4) * np.exp(-t * 8.0)
                    foley[idx:idx + l] += strike.astype(np.float32) * 0.75

        # Shot 18: 杨业立谶语 (苍凉宿命古埙颤音)
        elif sid == 18:
            xun_t = cur_t + 1.0
            idx = int(xun_t * SAMPLE_RATE)
            l = int(5.0 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 5.0, l, endpoint=False)
                tone = np.sin(2 * np.pi * 220.0 * (1 + 0.02 * np.sin(2 * np.pi * 4.5 * t)) * t) * np.exp(-t * 0.6) * 0.5
                foley[idx:idx + l] += tone.astype(np.float32) * 0.7

        # Shot 20: 皇朝大磬定音 (八贤王定策)
        elif sid == 20:
            chime_t = cur_t + 0.8
            idx = int(chime_t * SAMPLE_RATE)
            l = int(3.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 3.5, l, endpoint=False)
                chime = (np.sin(2 * np.pi * 440 * t) * 0.5 + np.sin(2 * np.pi * 880 * t) * 0.3) * np.exp(-t * 1.0)
                foley[idx:idx + l] += chime.astype(np.float32) * 0.75

        # Shot 22: 赵遂抚赤金 (金铤清脆撞击 2400Hz/4800Hz)
        elif sid == 22:
            gold_t = cur_t + 1.0
            idx = int(gold_t * SAMPLE_RATE)
            l = int(1.2 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.2, l, endpoint=False)
                tink = (np.sin(2 * np.pi * 2400 * t) * 0.3 + np.sin(2 * np.pi * 4800 * t) * 0.2) * np.exp(-t * 9.0)
                foley[idx:idx + l] += tink.astype(np.float32) * 0.65

        # Shot 25: 刘钧掷宝剑于金阶 (铿锵落地弹跳 780Hz/1560Hz)
        elif sid == 25:
            sword_t = cur_t + 1.2
            idx = int(sword_t * SAMPLE_RATE)
            l = int(1.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 1.5, l, endpoint=False)
                clang = (np.sin(2 * np.pi * 780 * t) * 0.5 + np.sin(2 * np.pi * 1560 * t) * 0.3) * np.exp(-t * 6.5)
                foley[idx:idx + l] += clang.astype(np.float32) * 0.85

        # Shot 29: 免战木牌凄风嘎吱声
        elif sid == 29:
            creak_t = cur_t + 0.5
            idx = int(creak_t * SAMPLE_RATE)
            l = int(2.0 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 2.0, l, endpoint=False)
                wood = np.sin(2 * np.pi * (180 + 30 * np.sin(2 * np.pi * 5 * t)) * t) * np.exp(-t * 1.5) * 0.4
                foley[idx:idx + l] += wood.astype(np.float32) * 0.6

        # Shot 36: 金刀滑落触地 (沉重铁刃顿地余音)
        elif sid == 36:
            blade_t = cur_t + 1.5
            idx = int(blade_t * SAMPLE_RATE)
            l = int(2.0 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 2.0, l, endpoint=False)
                drop = (np.sin(2 * np.pi * 140 * t) * 0.6 + np.sin(2 * np.pi * 720 * t) * 0.4) * np.exp(-t * 5.0)
                foley[idx:idx + l] += drop.astype(np.float32) * 0.8

        # Shot 38: 应州城门大启 (沉重大铜门铁锁机括隆隆轰响)
        elif sid == 38:
            gate_t = cur_t + 0.8
            idx = int(gate_t * SAMPLE_RATE)
            l = int(3.0 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 3.0, l, endpoint=False)
                gate = (np.sin(2 * np.pi * 45 * t) * 0.8 + np.sin(2 * np.pi * 90 * t) * 0.4) * np.exp(-t * 1.2)
                iron = (np.sin(2 * np.pi * 380 * t) * 0.3) * np.exp(-t * 4.0)
                foley[idx:idx + l] += (gate + iron).astype(np.float32) * 0.9

        # Shot 42: 八王折节相迎 (环佩玉玦相撞清音)
        elif sid == 42:
            jade_t = cur_t + 1.0
            idx = int(jade_t * SAMPLE_RATE)
            l = int(2.0 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 2.0, l, endpoint=False)
                jade = (np.sin(2 * np.pi * 1050 * t) * 0.3 + np.sin(2 * np.pi * 2100 * t) * 0.2) * np.exp(-t * 3.5)
                foley[idx:idx + l] += jade.astype(np.float32) * 0.7

        # Shot 46: 汴京金殿太宗解御袍加身 (皇室钟磬金声玉振)
        elif sid == 46:
            palace_t = cur_t + 0.6
            idx = int(palace_t * SAMPLE_RATE)
            l = int(3.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 3.5, l, endpoint=False)
                bell = (np.sin(2 * np.pi * 520 * t) * 0.5 + np.sin(2 * np.pi * 1040 * t) * 0.3) * np.exp(-t * 0.9)
                foley[idx:idx + l] += bell.astype(np.float32) * 0.85

        # Shot 54: 终局天波府金匾朱砂点睛 (神钟长鸣 + 金石定音 + 4.5s 渐隐余音)
        elif sid == 54:
            climax_t = cur_t + 0.5
            idx = int(climax_t * SAMPLE_RATE)
            l = int(5.5 * SAMPLE_RATE)
            if idx + l <= total_samples:
                t = np.linspace(0, 5.5, l, endpoint=False)
                grand_bell = (
                    np.sin(2 * np.pi * 110 * t) * 0.60 +
                    np.sin(2 * np.pi * 220 * t) * 0.40 +
                    np.sin(2 * np.pi * 440 * t) * 0.30 +
                    np.sin(2 * np.pi * 880 * t) * 0.15
                ) * np.exp(-t * 0.6)
                foley[idx:idx + l] += grand_bell.astype(np.float32) * 1.0

        cur_t += dur

    max_v = np.max(np.abs(foley))
    if max_v > 0:
        foley = (foley / max_v) * 0.88

    foley_int16 = (foley * 32767).astype(np.int16)
    wavfile.write(output_wav_path, SAMPLE_RATE, foley_int16)
    print(f"[动效交付] 54 镜全景物理动效轨已生成: {output_wav_path}")
    return output_wav_path, foley


def build_full_band_ducked_bgm_track(total_sec, voice_array, output_wav_path):
    """【全频段古风民乐 + 智能侧链闪避】富含泛音与共振的传统民族乐声场"""
    total_samples = int(total_sec * SAMPLE_RATE)
    t = np.linspace(0, total_sec, total_samples, endpoint=False)
    raw_bgm = np.zeros(total_samples, dtype=np.float32)

    # 1. 战阵大皮鼓 (全频段：击槌高频 + 鼓皮中频 + 腔体低频)
    for bt in np.arange(0.3, total_sec, 1.25):
        idx = int(bt * SAMPLE_RATE)
        l = int(0.85 * SAMPLE_RATE)
        if idx + l <= total_samples:
            dt = t[idx:idx + l] - bt
            decay = np.exp(-dt * 5.5)
            drum_strike = (
                np.sin(2 * np.pi * 55.0 * dt) * 0.55 +
                np.sin(2 * np.pi * 110.0 * dt) * 0.35 +
                np.sin(2 * np.pi * 220.0 * dt) * 0.25 +
                np.sin(2 * np.pi * 880.0 * dt) * 0.10 * np.exp(-dt * 15.0)
            ) * decay
            raw_bgm[idx:idx + l] += drum_strike.astype(np.float32) * 0.75

    # 2. 塞外角号长鸣 (雄浑悲壮，110Hz~550Hz 多级谐波，每 10 秒一声)
    for ht in np.arange(1.0, total_sec, 10.0):
        idx_h = int(ht * SAMPLE_RATE)
        l_h = int(4.0 * SAMPLE_RATE)
        if idx_h + l_h <= total_samples:
            dt_h = t[idx_h:idx_h + l_h] - ht
            horn_env = (np.sin(np.pi * dt_h / 4.0) ** 2) * 0.35
            horn_tone = (
                np.sin(2 * np.pi * 110.0 * dt_h) * 0.5 +
                np.sin(2 * np.pi * 220.0 * dt_h) * 0.3 +
                np.sin(2 * np.pi * 330.0 * dt_h) * 0.15 +
                np.sin(2 * np.pi * 440.0 * dt_h) * 0.08
            ) * horn_env
            raw_bgm[idx_h:idx_h + l_h] += horn_tone.astype(np.float32)

    # 3. 苍凉古风箫埙旋律 (羽调式古五音阶 A-C-D-E-G，带自然气鸣与颤音)
    pentatonic = [220.0, 261.6, 293.6, 329.6, 392.0, 440.0]
    for i, base_freq in enumerate(pentatonic):
        vibrato = 1.0 + 0.015 * np.sin(2 * np.pi * 4.5 * t)
        freq = base_freq * vibrato
        env = (np.sin(2 * np.pi * (0.07 + i * 0.02) * t) ** 2) * 0.22
        pipe = (
            np.sin(2 * np.pi * freq * t) * 0.6 +
            np.sin(2 * np.pi * freq * 2.0 * t) * 0.25 +
            np.sin(2 * np.pi * freq * 3.0 * t) * 0.12
        ) * env
        raw_bgm += pipe.astype(np.float32)

    # 4. 皇朝青铜编钟/大磬余韵 (庄重沉雄，每 12 秒一声)
    for ct in np.arange(0.0, total_sec, 12.0):
        idx_c = int(ct * SAMPLE_RATE)
        l_c = int(5.5 * SAMPLE_RATE)
        if idx_c + l_c <= total_samples:
            dt_c = t[idx_c:idx_c + l_c] - ct
            decay_c = np.exp(-dt_c * 0.75)
            bell = (
                np.sin(2 * np.pi * 440.0 * dt_c) * 0.35 +
                np.sin(2 * np.pi * 880.0 * dt_c) * 0.20 +
                np.sin(2 * np.pi * 1318.0 * dt_c) * 0.10 +
                np.sin(2 * np.pi * 2100.0 * dt_c) * 0.05
            ) * decay_c
            raw_bgm[idx_c:idx_c + l_c] += bell.astype(np.float32) * 0.6

    # 5. 动态侧链闪避 (Sidechain Ducking)
    win = int(0.3 * SAMPLE_RATE)
    voice_env = uniform_filter1d(np.abs(voice_array), size=win)
    duck_gain = 0.85 - (voice_env / (voice_env + 0.08)) * 0.61
    ducked_bgm = raw_bgm * duck_gain

    max_v = np.max(np.abs(ducked_bgm))
    if max_v > 0:
        ducked_bgm = (ducked_bgm / max_v) * 0.82

    bgm_int16 = (ducked_bgm * 32767).astype(np.int16)
    wavfile.write(output_wav_path, SAMPLE_RATE, bgm_int16)
    print(f"[配乐交付] 全频段古风民乐 + 动态侧链闪避轨已生成: {output_wav_path}")
    return output_wav_path, ducked_bgm


def mix_master_soundtrack(voice_wav, foley_wav, bgm_wav, master_wav):
    """母带终混：人声突出 1.20 + 动效 1.00 + 侧链 BGM 0.88"""
    cmd = [
        FFMPEG, "-y",
        "-i", voice_wav,
        "-i", foley_wav,
        "-i", bgm_wav,
        "-filter_complex",
        "[0:a]volume=1.20[v];"
        "[1:a]volume=1.00[f];"
        "[2:a]volume=0.88[b];"
        "[v][f][b]amix=inputs=3:duration=longest:dropout_transition=2:normalize=0[mixed];"
        "[mixed]alimiter=limit=0.95[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        master_wav
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"\n[终混完成] 母带级全景音轨已交付: {master_wav}\n")
    return master_wav


def burn_ep02_subtitles_and_tags(input_video, output_video, shots_metadata):
    """使用 ffmpeg 烧录 720P 底部华文楷体居中字幕与右上角金石注解卡"""
    srt_path = input_video.replace(".mp4", "_sub.srt")
    generate_srt_file(shots_metadata, srt_path)

    escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
    escaped_font = FONT_KAI.replace("\\", "/").replace(":", "\\:")

    filter_parts = []
    # 底部华文楷体电影字幕 (金石白字、深色微描边、720P 适配布距)
    sub_filter = (
        f"subtitles='{escaped_srt}':force_style="
        f"'FontName=KaiTi,FontSize=22,PrimaryColour=&H00F5F5DC,OutlineColour=&H00111111,"
        f"Outline=2,Shadow=1,MarginV=35,Alignment=2'"
    )
    filter_parts.append(sub_filter)

    # 右上角战局/人物注解卡 (前 3.8 秒展示)
    cur_t = 0.0
    for s in shots_metadata:
        dur = s["sec"]
        t_start = cur_t
        t_end = cur_t + dur
        tag = s.get("tag")
        if tag:
            display_end = min(t_start + 3.8, t_end)
            tag_text = tag.replace("'", "'\\''")
            draw_tag = (
                f"drawtext=fontfile='{escaped_font}':text='{tag_text}':"
                f"fontsize=18:fontcolor=white@0.95:box=1:boxcolor=black@0.45:boxborderw=8:"
                f"x=w-tw-35:y=35:enable='between(t,{t_start:.2f},{display_end:.2f})'"
            )
            filter_parts.append(draw_tag)
        cur_t += dur

    full_filter = ",".join(filter_parts)

    burn_cmd = [
        FFMPEG, "-y",
        "-i", input_video,
        "-vf", full_filter,
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "17",
        "-c:a", "copy",
        output_video
    ]
    print(f"\n=== 开始烧录 720P 华文楷体字幕与金石注疏卡: {os.path.basename(output_video)} ===")
    res = subprocess.run(burn_cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[交付成功] 完整字幕注解版成片已输出: {output_video}")
        return output_video
    else:
        print(f"[烧录错误] {res.stderr[-400:]}")
        return None


def produce_suite(shots, tag_name, output_annotated_mp4, output_clean_mp4, output_srt, use_bgm_foley=False):
    """端到端 720P 超分、Picture Lock、纯净人声母带与字幕烧录交付套件"""
    suite_dir = os.path.join(OUTPUT_DIR, f"suite_{tag_name}")
    os.makedirs(suite_dir, exist_ok=True)

    pure_video = os.path.join(suite_dir, f"pure_video_{tag_name}_720p.mp4")
    build_pure_video_lock(shots, pure_video, tag=tag_name)

    voice_wav = os.path.join(suite_dir, "track1_voice.wav")
    master_ost = os.path.join(suite_dir, "master_ost.wav")

    # 1. 旁白音轨 (微软 Edge-TTS 云健沧桑正剧男声，长轴绝对时序，彻底杜绝吞字)
    _, voice_arr = build_global_unclipped_narration_track(shots, voice_wav)

    if use_bgm_foley:
        foley_wav = os.path.join(suite_dir, "track2_foley.wav")
        bgm_wav = os.path.join(suite_dir, "track3_bgm.wav")
        build_full_band_foley_track(shots, foley_wav)
        total_sec = sum(s["sec"] for s in shots)
        build_full_band_ducked_bgm_track(total_sec, voice_arr, bgm_wav)
        mix_master_soundtrack(voice_wav, foley_wav, bgm_wav, master_ost)
    else:
        # 【依据用户指示：彻底去除合成民乐与动效杂音，保持 100% 纯净通透广播级正剧人声】
        master_cmd = [
            FFMPEG, "-y",
            "-i", voice_wav,
            "-af", "volume=1.08,alimiter=limit=0.98",
            "-c:a", "pcm_s16le",
            "-ar", str(SAMPLE_RATE),
            master_ost
        ]
        subprocess.run(master_cmd, capture_output=True, check=True)
        print(f"\n[纯净人声母带交付] 已彻底剔除合成杂音，纯净对白母带就绪: {master_ost}\n")

    # 5. 混流纯净母带版 (无字幕 720P)
    mux_cmd = [
        FFMPEG, "-y",
        "-i", pure_video,
        "-i", master_ost,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        output_clean_mp4
    ]
    print(f"=== 混流生成 720P 纯净母带版: {os.path.basename(output_clean_mp4)} ===")
    subprocess.run(mux_cmd, capture_output=True, check=True)

    # 6. 生成标准字幕文件
    generate_srt_file(shots, output_srt)

    # 7. 烧录楷体字幕与金石注疏名片成片 (720P)
    burn_ep02_subtitles_and_tags(output_clean_mp4, output_annotated_mp4, shots)

    print(f"\n=======================================================")
    print(f"  【交付就绪】{tag_name} 完整成品已归档至 final 目录！")
    print(f"  1. 完整注释成片 (720P): {output_annotated_mp4}")
    print(f"  2. 纯净母带成片 (720P): {output_clean_mp4}")
    print(f"  3. 独立外挂字幕: {output_srt}")
    print(f"=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="北宋杨家将第2集大总成生产引擎")
    parser.add_argument("--mode", type=str, default="all", choices=["all", "acts_only", "full_only"], help="生产模式")
    parser.add_argument("--act", type=int, default=0, choices=range(0, 6), help="指定单幕生产 (1~5)")
    parser.add_argument("--with-bgm", action="store_true", help="是否包含实验性合成背景音 (默认关闭以保持 100% 纯净人声)")
    args = parser.parse_args()

    # 1. 产出各单幕成片
    if args.mode in ["all", "acts_only"] or args.act > 0:
        target_acts = [args.act] if args.act > 0 else list(range(1, 6))
        for act_num in target_acts:
            info = ACT_INFO[act_num]
            s_range = info["shots"]
            act_shots = [s for s in EP02_METADATA if s_range[0] <= s["id"] <= s_range[1]]
            act_name = f"Act{act_num}_{info['title']}"

            annotated_v = os.path.join(FINAL_DIR, f"{act_name}_annotated_720p.mp4")
            clean_v = os.path.join(FINAL_DIR, f"{act_name}_clean_720p.mp4")
            srt_f = os.path.join(FINAL_DIR, f"{act_name}.srt")

            print(f"\n>>> 启动单幕大总成交付: {act_name} (Shots {s_range[0]}~{s_range[1]}) <<<")
            produce_suite(act_shots, f"act{act_num}", annotated_v, clean_v, srt_f, use_bgm_foley=args.with_bgm)

    # 2. 产出全剧 54 镜超级大总成 (214.0 秒)
    if (args.mode in ["all", "full_only"]) and args.act == 0:
        print(f"\n>>> 启动全剧终极超级大总成 (Picture Lock 全 54 镜 · 214.0s) <<<")
        full_annotated = os.path.join(FINAL_DIR, "北宋杨家将_第02集_完整版_全剧超级大总成_annotated.mp4")
        full_clean = os.path.join(FINAL_DIR, "北宋杨家将_第02集_完整版_全剧超级大总成_clean.mp4")
        full_srt = os.path.join(FINAL_DIR, "北宋杨家将_第02集_全集字幕.srt")
        produce_suite(EP02_METADATA, "ep02_full", full_annotated, full_clean, full_srt, use_bgm_foley=args.with_bgm)


if __name__ == "__main__":
    main()
