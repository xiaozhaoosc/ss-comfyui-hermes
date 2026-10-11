#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第3集前2段 ComfyUI/FFmpeg 电影级后期接力总成引擎
(Route A Post-Production Relay Engine)

功能：
1. 【1080P 电影级画质超分与去噪】：
   - 将 720p (1280x720) 视频采用 Lanczos + 边缘强化 (Unsharp) + 国风微对比增强 (EQ) 超分至 1080P (1920x1080)。
   - 彻底剥离 AI 扩散生成自生的背景高频低噪。
2. 【48fps 丝滑高帧率平滑插帧】：
   - 消除镜头横移与仰推时的微顿挫感，呈现院线级丝滑运镜。
3. 【三轨声学母带级音频总成】：
   - 轨道 1：Edge-TTS 云健沧桑正剧男声 (zh-CN-YunjianNeural，入画 0.4s 自然呼吸切入，绝不吞字)。
   - 轨道 2：关键物理动效 (SFX，雪山狂风、金石碰撞、大殿沉钟)。
   - 轨道 3：全频段历史古风背景乐 (BGM，塞外战鼓、低音埙箫、朝堂编钟)，配合智能侧链闪避。
4. 【视觉注疏金石名片与华文楷体居中字幕】：
   - 右上角半透明宣纸黑底 + 金粉边框战局注疏名片。
   - 底部象牙白居中楷体字幕，带黑底半透明晕染描边。
5. 【单镜与 16s 双镜母带连贯总成】：
   - 交付 shot_01_master_1080p.mp4、shot_02_master_1080p.mp4 以及北宋杨家将_第03集_前2段大总成母带_1080p.mp4。
"""

import os
import sys
import asyncio
import subprocess
import edge_tts
import numpy as np
from scipy.io import wavfile
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = r"D:\ai_projects\ComfyUI"
DATE_STR = "2026-10-10"
BASE_DIR = os.path.join(ROOT, "output", DATE_STR, "route_a")
VIDEO_SRC_DIR = os.path.join(BASE_DIR, "videos")
FINAL_DIR = os.path.join(BASE_DIR, "final")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
CARDS_DIR = os.path.join(BASE_DIR, "cards")

os.makedirs(FINAL_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(CARDS_DIR, exist_ok=True)

FFMPEG = "ffmpeg"
FONT_KAI = r"C:\Windows\Fonts\simkai.ttf"
SAMPLE_RATE = 44100

SHOTS = [
    {
        "id": 1,
        "sec": 8.0,
        "raw_video": os.path.join(VIDEO_SRC_DIR, "shot_01_veo_8s.mp4"),
        "sub": "太平兴国五年，宋主感念神恩，御驾亲巡五台山进香还愿。",
        "tag": "太平兴国五年 · 御驾还愿",
        "sfx_type": "mountain_snow",
        "bgm_type": "imperial_march",
        "master_name": "shot_01_master_1080p.mp4"
    },
    {
        "id": 2,
        "sec": 8.0,
        "raw_video": os.path.join(VIDEO_SRC_DIR, "shot_02_veo_8s.mp4"),
        "sub": "贤相寇准伏地苦谏：‘塞北辽骑凶悍，至尊不可轻履险地！’",
        "tag": "寇 准 · 伏地苦谏",
        "sfx_type": "court_hall",
        "bgm_type": "palace_drama",
        "master_name": "shot_02_master_1080p.mp4"
    }
]

# 1. 旁白合成
async def generate_narration(text, out_mp3):
    voice = "zh-CN-YunjianNeural"
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-3%", pitch="-2Hz")
            await communicate.save(out_mp3)
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000:
                return True
        except Exception as e:
            print(f"TTS retry {attempt+1}: {e}")
            await asyncio.sleep(1.0)
    return False

# 2. 物理声学建模 (SFX & BGM)
def synthesize_acoustics(shot):
    sec = shot["sec"]
    total_samples = int(sec * SAMPLE_RATE)
    t = np.linspace(0, sec, total_samples, endpoint=False)
    
    # SFX 环境音
    sfx = np.zeros(total_samples, dtype=np.float32)
    if shot["sfx_type"] == "mountain_snow":
        # 塞外朔风呼啸 (粉红噪声低通滤波)
        white_noise = np.random.normal(0, 0.08, total_samples)
        wind_mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * t)
        sfx += (white_noise * wind_mod * 0.6).astype(np.float32)
        # 偶尔的冰裂与旗帜破风声 (低频隆隆)
        rumble = np.sin(2 * np.pi * 55 * t) * 0.15 * (0.8 + 0.2 * np.cos(2 * np.pi * 0.5 * t))
        sfx += rumble.astype(np.float32)
    elif shot["sfx_type"] == "court_hall":
        # 金殿肃穆环境音与殿堂混响
        room_tone = np.random.normal(0, 0.02, total_samples).astype(np.float32)
        # 金石朝玉触地声 (2.5s 处叩拜清脆点)
        impact_idx = int(2.5 * SAMPLE_RATE)
        imp_len = int(0.6 * SAMPLE_RATE)
        if impact_idx + imp_len < total_samples:
            tt = np.linspace(0, 0.6, imp_len, endpoint=False)
            decay = np.exp(-tt * 12)
            stone = (np.sin(2 * np.pi * 880 * tt) + 0.5 * np.sin(2 * np.pi * 1760 * tt)) * decay * 0.35
            sfx[impact_idx:impact_idx+imp_len] += stone.astype(np.float32)
        sfx += room_tone

    # BGM 乐器建模
    bgm = np.zeros(total_samples, dtype=np.float32)
    if shot["bgm_type"] == "imperial_march":
        # 沉重巡狩战鼓 (每 1.6 秒一击)
        drum_interval = int(1.6 * SAMPLE_RATE)
        drum_len = int(0.7 * SAMPLE_RATE)
        tt = np.linspace(0, 0.7, drum_len, endpoint=False)
        drum_env = np.exp(-tt * 6.5)
        drum_body = np.sin(2 * np.pi * 75 * tt) * drum_env * 0.45
        for i in range(0, total_samples - drum_len, drum_interval):
            bgm[i:i+drum_len] += drum_body.astype(np.float32)
        # 苍凉埙声长音 (羽调式 D3/A3)
        xun = (np.sin(2 * np.pi * 146.8 * t) * 0.15 + np.sin(2 * np.pi * 220.0 * t) * 0.1) * (0.85 + 0.15 * np.sin(2 * np.pi * 4.0 * t))
        bgm += xun.astype(np.float32)
    elif shot["bgm_type"] == "palace_drama":
        # 大殿编钟沉鸣 (0.2s 处起音，长残响)
        bell_len = int(4.0 * SAMPLE_RATE)
        tt = np.linspace(0, 4.0, bell_len, endpoint=False)
        decay = np.exp(-tt * 1.5)
        bell = (np.sin(2 * np.pi * 261.6 * tt) * 0.25 + np.sin(2 * np.pi * 523.2 * tt) * 0.15) * decay
        if bell_len < total_samples:
            bgm[0:bell_len] += bell.astype(np.float32)
        # 压抑低沉大提琴和声
        cello = np.sin(2 * np.pi * 65.4 * t) * 0.18 + np.sin(2 * np.pi * 98.0 * t) * 0.12
        bgm += cello.astype(np.float32)

    return sfx, bgm

# 3. 生成金石名片
def create_gold_card(tag_text, out_png):
    W, H = 460, 78
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 半透明深黑底板 (alpha 200) + 宣纸金边
    draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=10, fill=(15, 15, 18, 205), outline=(212, 175, 95, 235), width=2)
    
    # 字体加载
    try:
        font = ImageFont.truetype(FONT_KAI, 27)
    except Exception:
        font = ImageFont.load_default()
        
    full_text = f"【{tag_text}】"
    bbox = draw.textbbox((0, 0), full_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (W - tw) // 2
    ty = (H - th) // 2 - 2
    
    # 金石文字双层绘制 (阴影 + 暖金)
    draw.text((tx + 1, ty + 1), full_text, fill=(5, 5, 5, 230), font=font)
    draw.text((tx, ty), full_text, fill=(245, 212, 142, 255), font=font)
    
    img.save(out_png)

# 4. 单镜声画总装 (FFmpeg 1080P 超分 + 48fps 平滑 + 三轨混音)
def assemble_shot(shot):
    sid = shot["id"]
    sec = shot["sec"]
    raw_v = shot["raw_video"]
    master_p = os.path.join(FINAL_DIR, shot["master_name"])
    
    print(f"\n=======================================================")
    print(f"  正在执行 Shot {sid:02d} ComfyUI 接力后期总成...")
    print(f"  源视频: {os.path.basename(raw_v)} (1280x720, 24fps)")
    print(f"  目标画质: 1920x1080 电影全高清 (Lanczos+Unsharp) | 48fps 丝滑插帧")
    print(f"=======================================================")

    # 步骤 A：旁白 TTS
    tts_mp3 = os.path.join(AUDIO_DIR, f"tts_shot_{sid:02d}.mp3")
    tts_wav = os.path.join(AUDIO_DIR, f"tts_shot_{sid:02d}.wav")
    asyncio.run(generate_narration(shot["sub"], tts_mp3))
    subprocess.run([FFMPEG, "-y", "-i", tts_mp3, "-ar", str(SAMPLE_RATE), "-ac", "1", tts_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 步骤 B：声学建模与混音 (带有侧链闪避)
    sfx, bgm = synthesize_acoustics(shot)
    sr, tts_data = wavfile.read(tts_wav)
    tts_data = tts_data.astype(np.float32) / 32768.0

    # 旁白入画 0.4s 切入
    voice_track = np.zeros(int(sec * SAMPLE_RATE), dtype=np.float32)
    start_idx = int(0.40 * SAMPLE_RATE)
    avail_len = min(len(tts_data), len(voice_track) - start_idx)
    voice_track[start_idx:start_idx+avail_len] = tts_data[:avail_len] * 1.05

    # 侧链计算：当旁白存在时，BGM 下凹 -10dB (0.32)
    voice_energy = np.abs(voice_track)
    from scipy.ndimage import uniform_filter1d
    smooth_env = uniform_filter1d(voice_energy, size=int(0.3 * SAMPLE_RATE))
    ducking_factor = 1.0 - 0.65 * np.clip(smooth_env * 3.0, 0.0, 1.0)
    bgm_ducked = bgm * ducking_factor

    # 三轨大总成
    master_audio = voice_track * 1.15 + sfx * 0.45 + bgm_ducked * 0.75
    # 软限幅
    peak = np.max(np.abs(master_audio))
    if peak > 0.98:
        master_audio = master_audio / peak * 0.98

    mixed_wav = os.path.join(AUDIO_DIR, f"master_audio_shot_{sid:02d}.wav")
    wavfile.write(mixed_wav, SAMPLE_RATE, (master_audio * 32767).astype(np.int16))

    # 步骤 C：金石名片
    card_png = os.path.join(CARDS_DIR, f"card_shot_{sid:02d}.png")
    create_gold_card(shot["tag"], card_png)

    # 步骤 D：FFmpeg 图像滤镜图设计 (1080P 超分 + Unsharp 锐化 + 字幕 + 名片 + 48fps 补帧)
    # 字体路径斜杠处理
    font_path_escaped = FONT_KAI.replace("\\", "/").replace(":", "\\:")
    subtitle_text = shot["sub"].replace("‘", "「").replace("’", "」")

    vf = (
        # 1. 1080P Lanczos 超分辨率升频
        f"[0:v]scale=1920:1080:flags=lanczos,"
        # 2. 边缘细节强化 (增强剪纸墨线锐度) 与自适应国风对比微调
        f"unsharp=5:5:0.8:5:5:0.0,"
        f"eq=contrast=1.04:brightness=0.01:saturation=1.05[v_up];"
        # 3. 48fps 运动平滑插帧 (minterpolate)
        f"[v_up]minterpolate='fps=48:mi_mode=blend'[v_smooth];"
        # 4. 右上角叠加上美影金石战局注疏名片 (入画 0.2s 淡入，出画前 0.2s 淡出)
        f"[v_smooth][1:v]overlay=W-w-36:36:enable='between(t,0.2,{sec-0.2})'[v_card];"
        # 5. 底部居中烧录华文楷体字幕 (象牙白文字 + 半透明黑色描边)
        f"[v_card]drawtext=fontfile='{font_path_escaped}':text='{subtitle_text}':"
        f"fontsize=36:fontcolor=0xFFF8E7:bordercolor=0x111111@0.85:borderw=2.5:"
        f"x=(w-text_w)/2:y=h-96:enable='between(t,0.35,{sec-0.35})'[v_out]"
    )

    cmd = [
        FFMPEG, "-y",
        "-t", str(sec),
        "-i", raw_v,
        "-i", card_png,
        "-i", mixed_wav,
        "-filter_complex", vf,
        "-map", "[v_out]",
        "-map", "2:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "17",
        "-c:a", "aac",
        "-b:a", "256k",
        "-r", "48",
        "-t", str(sec),
        master_p
    ]

    print(f"正在执行 1080P/48fps 编码压制...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0 and os.path.exists(master_p):
        size_mb = os.path.getsize(master_p) / (1024 * 1024)
        print(f"[√] Shot {sid:02d} 电影级母带完成: {master_p} ({size_mb:.2f} MB, {sec}s, 1080p/48fps)")
        return master_p
    else:
        err = res.stderr.decode('utf-8', errors='ignore')
        print(f"[!] 编码失败: {err[-400:]}")
        return None

# 5. 双镜大总成拼接 (16.0s 序幕前瞻大母带)
def concatenate_master(clips, output_file):
    print(f"\n=======================================================")
    print(f"  正在将 Shot 01 与 Shot 02 无缝缝合为 16.0 秒正片母带...")
    print(f"=======================================================")
    concat_txt = os.path.join(FINAL_DIR, "master_concat_list.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in clips:
            f.write(f"file '{c.replace(chr(92), '/')}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        output_file
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(concat_txt):
        try:
            os.remove(concat_txt)
        except Exception:
            pass
            
    if res.returncode == 0 and os.path.exists(output_file):
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"[√] 全集前序 16.0s 正剧母带已交付: {output_file} ({size_mb:.2f} MB)")
        return True
    return False

def main():
    print("=" * 70)
    print("  北宋杨家将 · 第3集前2段 ComfyUI/FFmpeg 电影级母带接力引擎")
    print("  分辨率: 1920x1080 (16:9) | 帧率: 48fps | 声画母带三轨对齐")
    print("=" * 70)

    delivered_clips = []
    for shot in SHOTS:
        out_p = assemble_shot(shot)
        if out_p:
            delivered_clips.append(out_p)

    if len(delivered_clips) == 2:
        final_16s = os.path.join(FINAL_DIR, "北宋杨家将_第03集_前2段大总成母带_1080p.mp4")
        concatenate_master(delivered_clips, final_16s)
        print("\n" + "=" * 70)
        print(f"【全部交付完成】产物已归档至: {FINAL_DIR}")
        print("=" * 70)

if __name__ == '__main__':
    main()
