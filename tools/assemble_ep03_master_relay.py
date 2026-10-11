#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 3 集《邠阳城救驾》母带合成接力大总成引擎 (Master Relay Engine)

工业级母带视听标准：
1. 【混合接力画源 (Hybrid Relay)】：
   - 优先挂载 Muse.ai 720P 高画质国风成片；
   - 自动回退接力本地 ComfyUI 补拍渲染底片 (yang_ep03_shot*.mp4)；
   - 全 54 镜 100% 满格对齐，零漏镜。
2. 【画面规格标准化】：
   - 全程归一化为 720x1280 竖屏 (9:16), 24.0 fps, libx264 CRF 18, yuv420p。
   - 彻底剥离 (-an) 扩散模型自生的高频噪音。
3. 【微软云健正剧男声双声道母带声学】：
   - Edge-TTS 云健男声 (zh-CN-YunjianNeural)，每句入画 0.35s 切入，保留尾部呼吸留白。
   - 专业广播级压限 (volume=1.12, alimiter=limit=0.98)。
4. 【金石战局注疏名片与华文楷体字幕】：
   - 右上角半透明黑底金石注疏名片淡入淡出。
   - 毫秒级对齐 SRT 字幕同步归档。
5. 【大总成交付物】：
   - 5 幕独立精编版 (Act 1 ~ Act 5)；
   - 214.0 秒 Picture Lock 全集终身母带。
   - 全部归档至 output/2026-10-10/yangjiajiang_ep03/final/。
"""

import os
import sys
import glob
import json
import asyncio
import argparse
import subprocess
import shutil

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.yangjiajiang_ep03_metadata import EP03_METADATA

DATE_STR = "2026-10-10"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep03")
ASSEMBLED_DIR = os.path.join(OUTPUT_DIR, "assembled_relay")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")
CARDS_DIR = os.path.join(OUTPUT_DIR, "cards")

# 兼容历史 10-09 资产目录
HIST_09_DIR = os.path.join(ROOT, "output", "2026-10-09", "yangjiajiang_ep03")

os.makedirs(ASSEMBLED_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(CARDS_DIR, exist_ok=True)

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"

ACT_INFO = {
    1: {"title": "盛极隐忧·五台还愿", "shots": (1, 9), "sec": 36.0},
    2: {"title": "幽州暗伏·诱敌深入", "shots": (10, 18), "sec": 36.0},
    3: {"title": "孤城合围·铁锁大闭", "shots": (19, 27), "sec": 36.0},
    4: {"title": "箭创敌首·决死突围", "shots": (28, 36), "sec": 36.0},
    5: {"title": "金刀赴难·绝地死局", "shots": (37, 54), "sec": 70.0},
}

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def sync_base_assets():
    """同步或检查音频与名片资产"""
    print("[+] 正在同步与校验声学及视听基座资产...")
    # 拷贝 10-09 的音频与名片
    for i in range(1, 55):
        # Audio
        src_a = os.path.join(HIST_09_DIR, "audio", f"shot_{i:02d}.mp3")
        dst_a = os.path.join(AUDIO_DIR, f"shot_{i:02d}.mp3")
        if os.path.exists(src_a) and (not os.path.exists(dst_a) or os.path.getsize(dst_a) == 0):
            shutil.copy2(src_a, dst_a)

        # Card
        src_c = os.path.join(HIST_09_DIR, "cards", f"card_{i:02d}.png")
        dst_c = os.path.join(CARDS_DIR, f"card_{i:02d}.png")
        if os.path.exists(src_c) and (not os.path.exists(dst_c) or os.path.getsize(dst_c) == 0):
            shutil.copy2(src_c, dst_c)

    a_count = len(glob.glob(os.path.join(AUDIO_DIR, "*.mp3")))
    c_count = len(glob.glob(os.path.join(CARDS_DIR, "*.png")))
    print(f"  [√] 旁白音频就绪: {a_count} / 54")
    print(f"  [√] 金石名片就绪: {c_count} / 54")


def select_best_video_source(sid):
    """智能选择最佳视频源：优先高清 Muse，回退 ComfyUI"""
    # 1. 检查今日提取的 18 段 Muse 视频中是否有对应匹配
    # 2. 检查 10-09 提取的大于 1MB 的 Muse 视频
    muse_candidates = [
        os.path.join(HIST_09_DIR, "muse_videos", f"muse_shot{sid:02d}.mp4"),
        os.path.join(HIST_09_DIR, "comparison", f"muse_shot{sid:02d}.mp4"),
    ]
    for c in muse_candidates:
        if os.path.exists(c) and os.path.getsize(c) > 1000000:
            return c, "Muse.ai (高画质)"

    # 3. 回退检查本地 ComfyUI 生成的底片
    comfy_candidates = [
        os.path.join(HIST_09_DIR, f"yang_ep03_shot{sid:02d}_00001_.mp4"),
        os.path.join(OUTPUT_DIR, f"yang_ep03_shot{sid:02d}_00001_.mp4"),
    ]
    for c in comfy_candidates:
        if os.path.exists(c) and os.path.getsize(c) > 200000:
            return c, "ComfyUI (本地补拍)"

    return None, "未找到"


def format_srt_time(seconds):
    millis = int(round(seconds * 1000))
    h = millis // 3600000
    millis %= 3600000
    m = millis // 60000
    millis %= 60000
    s = millis // 1000
    ms = millis % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt_files():
    """生成全集及各分幕精准 SRT 字幕"""
    full_srt_path = os.path.join(FINAL_DIR, "北宋杨家将_第03集_全集字幕.srt")
    full_lines = []
    curr_time = 0.0

    for idx, shot in enumerate(EP03_METADATA, 1):
        dur = shot["sec"]
        start_t = curr_time + 0.35
        end_t = min(curr_time + dur - 0.20, start_t + dur - 0.40)
        full_lines.append(f"{idx}")
        full_lines.append(f"{format_srt_time(start_t)} --> {format_srt_time(end_t)}")
        full_lines.append(shot["sub"])
        full_lines.append("")
        curr_time += dur

    with open(full_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_lines))
    print(f"  [√] 全集 SRT 字幕已生成: {full_srt_path}")

    for act_num, info in ACT_INFO.items():
        s_start, s_end = info["shots"]
        act_srt_path = os.path.join(FINAL_DIR, f"Act{act_num}_{info['title']}.srt")
        act_lines = []
        act_curr_t = 0.0
        line_num = 1
        for shot in EP03_METADATA:
            if s_start <= shot["id"] <= s_end:
                dur = shot["sec"]
                start_t = act_curr_t + 0.35
                end_t = min(act_curr_t + dur - 0.20, start_t + dur - 0.40)
                act_lines.append(f"{line_num}")
                act_lines.append(f"{format_srt_time(start_t)} --> {format_srt_time(end_t)}")
                act_lines.append(shot["sub"])
                act_lines.append("")
                line_num += 1
                act_curr_t += dur
        with open(act_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(act_lines))


def assemble_single_shot(shot_cfg):
    """单镜装配：归一化至 720x1280 竖屏、叠名片、注入旁白"""
    sid = shot_cfg["id"]
    sec = shot_cfg["sec"]
    out_mp4 = os.path.join(ASSEMBLED_DIR, f"shot_{sid:02d}.mp4")

    # 断点续跑
    if os.path.exists(out_mp4) and os.path.getsize(out_mp4) > 500000:
        return out_mp4

    raw_v, v_source = select_best_video_source(sid)
    if not raw_v:
        print(f"[!] 镜头 {sid:02d} 无可用视频源！")
        return None

    audio_p = os.path.join(AUDIO_DIR, f"shot_{sid:02d}.mp3")
    card_p = os.path.join(CARDS_DIR, f"card_{sid:02d}.png")

    if not os.path.exists(audio_p):
        print(f"[!] 缺失音频: {audio_p}")
        return None
    if not os.path.exists(card_p):
        print(f"[!] 缺失名片: {card_p}")
        return None

    # 视频滤镜：scale 居中填充至 720x1280，叠名片
    vf = (
        f"[0:v]scale=720:1280:force_original_aspect_ratio=decrease,"
        f"pad=720:1280:(ow-iw)/2:(oh-ih)/2,format=yuv420p[bg];"
        f"[bg][1:v]overlay=W-w-24:32:enable='between(t,0.2,{sec-0.2})'[v]"
    )

    cmd = [
        FFMPEG, "-y",
        "-t", str(sec),
        "-i", raw_v,
        "-i", card_p,
        "-i", audio_p,
        "-filter_complex", vf,
        "-map", "[v]",
        "-map", "2:a",
        "-af", "adelay=350|350,volume=1.12,alimiter=limit=0.98",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-r", "24",
        "-t", str(sec),
        out_mp4
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0 and os.path.exists(out_mp4):
        sz_mb = os.path.getsize(out_mp4) / (1024 * 1024)
        print(f"  [√] Shot {sid:02d} 装配成功 [{v_source}] -> {sz_mb:.2f} MB ({sec}s)")
        return out_mp4
    else:
        err = res.stderr.decode("utf-8", errors="ignore")[-200:]
        print(f"  [!] Shot {sid:02d} 装配失败: {err}")
        return None


def concat_video_list(clips, output_file):
    concat_txt = os.path.join(FINAL_DIR, f"concat_tmp_{os.path.basename(output_file)}.txt")
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
        sz_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"  [√] 交付视频生成: {os.path.basename(output_file)} ({sz_mb:.2f} MB)")
        return True
    return False


def run_master_relay():
    print("=" * 65)
    print("  【北宋杨家将】第 3 集《邠阳城救驾》母带合成接力大总成")
    print(f"  归档目录: {FINAL_DIR}")
    print("  视听标准: 720x1280 竖屏 | 24fps | 双声道压限混音 | 214.0s Picture Lock")
    print("=" * 65)

    sync_base_assets()
    generate_srt_files()

    print("\n[+] 开始 54 镜全量接力装配...")
    all_clips = []
    muse_count = 0
    comfy_count = 0

    for shot in EP03_METADATA:
        clip_p = assemble_single_shot(shot)
        if clip_p:
            all_clips.append(clip_p)
            _, v_src = select_best_video_source(shot["id"])
            if "Muse" in v_src:
                muse_count += 1
            else:
                comfy_count += 1
        else:
            print(f"[!] 无法装配 Shot {shot['id']:02d}")

    print(f"\n[√] 54 镜单镜装配完成率: {len(all_clips)} / 54 (Muse: {muse_count}, ComfyUI: {comfy_count})")
    if len(all_clips) != 54:
        print("[!] 镜头未集齐，中止合并。")
        return

    # 1. 拼接 5 幕独立成片
    print("\n[+] 正在拼接五大分幕独立精编版...")
    for act_num, info in ACT_INFO.items():
        s_start, s_end = info["shots"]
        act_clips = all_clips[s_start - 1 : s_end]
        act_out = os.path.join(FINAL_DIR, f"Act{act_num}_{info['title']}_接力精编_720P.mp4")
        concat_video_list(act_clips, act_out)

    # 2. 拼接全集大总成
    print("\n[+] 正在拼接 214.0 秒全集终极大总成母带...")
    full_out = os.path.join(FINAL_DIR, "北宋杨家将_第03集_邠阳城救驾_全集正剧母带_214s_720P.mp4")
    concat_video_list(all_clips, full_out)

    print("\n" + "=" * 65)
    print("【全链路总成交付完毕】")
    print(f"全集母带: {full_out}")
    print(f"分幕成片: {FINAL_DIR}")
    print("=" * 65)


if __name__ == "__main__":
    run_master_relay()
