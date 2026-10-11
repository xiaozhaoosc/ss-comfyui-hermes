#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 全剧连贯性核验与 final 目录归档交付器"""

import os
import sys
import shutil
import subprocess

ROOT = r"D:\ai_projects\ComfyUI"
OUTPUT_DIR = os.path.join(ROOT, "output", "2026-10-04", "yangjiajiang_ep01")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    import shutil
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

os.makedirs(FINAL_DIR, exist_ok=True)

acts = [
    {
        "act": 1,
        "name": "Act1_出征序章",
        "file": os.path.join(OUTPUT_DIR, "yang_ep01_act1_annotated.mp4"),
        "srt": os.path.join(OUTPUT_DIR, "yang_ep01_1min_ancient_ost_sub.srt"),
        "desc": "Shot 01~12: 开宝二年塞北风雪，卧雪残碑，太原城下旌旗连营，哨卒按刀待战。"
    },
    {
        "act": 2,
        "name": "Act2_晋阳血战",
        "file": os.path.join(OUTPUT_DIR, "yang_ep01_act2_annotated.mp4"),
        "srt": os.path.join(OUTPUT_DIR, "yang_ep01_act2_clean_merged_sub.srt"),
        "desc": "Shot 13~19: 两军精骑出营对撞，神驹衔矢护主，杨业金刀挑翻潘仁美，两路伏兵断敌归路。"
    },
    {
        "act": 3,
        "name": "Act3_夜劫空营",
        "file": os.path.join(OUTPUT_DIR, "yang_ep01_act3_annotated.mp4"),
        "srt": os.path.join(OUTPUT_DIR, "yang_ep01_act3_clean_merged_sub.srt"),
        "desc": "Shot 20~27: 宋太祖夜谋劫营，杨业识破玄机案上布阵，信炮爆闪宋军自乱，太祖叹才。"
    },
    {
        "act": 4,
        "name": "Act4_塞北连雨",
        "file": os.path.join(OUTPUT_DIR, "yang_ep01_act4_annotated.mp4"),
        "srt": os.path.join(OUTPUT_DIR, "yang_ep01_act4_clean_merged_sub.srt"),
        "desc": "Shot 28~33: 晋阳数月连阴雨两军相持，太祖跺泥受阻，杨业借雨分派诸子设伏，信炮破敌。"
    },
]

print("=== 1. 检查各幕成片完整性与视听指标 ===")
valid_clips = []
for a in acts:
    p = a["file"]
    if not os.path.exists(p):
        print(f"  [缺失] {a['name']}: {p}")
        continue
    sz = os.path.getsize(p)
    # 获取时长
    dur_cmd = [FFMPEG, "-i", p]
    res = subprocess.run(dur_cmd, capture_output=True, text=True)
    dur_str = "未知"
    for line in res.stderr.splitlines():
        if "Duration:" in line:
            dur_str = line.split("Duration:")[1].split(",")[0].strip()
            break
    print(f"  [完整] {a['name']} | 文件大小: {sz/1024/1024:.2f} MB | 时长: {dur_str}")
    print(f"         剧情脉络: {a['desc']}")
    valid_clips.append(p)

    # 归档该幕独立带字幕版到 final/
    dst_mp4 = os.path.join(FINAL_DIR, f"{a['name']}_annotated.mp4")
    shutil.copy2(p, dst_mp4)
    if os.path.exists(a["srt"]):
        shutil.copy2(a["srt"], os.path.join(FINAL_DIR, f"{a['name']}.srt"))

print(f"\n=== 2. 执行 Act 1~4 全链路大总拼（时间轴无缝衔接）===")
concat_txt = os.path.join(FINAL_DIR, "concat_final_list.txt")
with open(concat_txt, "w", encoding="utf-8") as f:
    for c in valid_clips:
        f.write(f"file '{c.replace(chr(92), '/')}'\n")

total_merged_mp4 = os.path.join(FINAL_DIR, "北宋杨家将_第01集_Act1至Act4全连贯大片_annotated.mp4")
merge_cmd = [
    FFMPEG, "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", concat_txt,
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    total_merged_mp4
]
print(f"正在无缝拼接全链路总成片: {os.path.basename(total_merged_mp4)} ...")
subprocess.run(merge_cmd, capture_output=True, check=True)

if os.path.exists(total_merged_mp4):
    sz_total = os.path.getsize(total_merged_mp4)
    print(f"[大总拼完成] 总成片大小: {sz_total/1024/1024:.2f} MB")

print("\n=== final 目录归档完毕 ===")
