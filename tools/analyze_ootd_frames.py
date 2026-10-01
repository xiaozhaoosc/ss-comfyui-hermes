#!/usr/bin/env python3
"""抽帧分析 OOTD 8 个视频：每段抓首/中(2个)/尾帧，GLM 判断换装转场质量"""
import os, subprocess, sys, json

from pathlib import Path

BASE = "output/ootd_v1"
FR = Path(BASE) / "frames"
FR.mkdir(exist_ok=True)

VIDEOS = sorted([x for x in Path(BASE).glob("*.mp4")])
print(f"共 {len(VIDEOS)} 个视频待分析\n")

def get_duration(fp):
    out = subprocess.check_output([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "json", str(fp)
    ]).decode()
    return float(json.loads(out)["format"]["duration"])

idx_map = {}
for i, vpath in enumerate(VIDEOS, 1):
    dur = get_duration(vpath)
    # 抓 4 帧: 0s, dur*0.33, dur*0.66, dur-0.2s
    times = [0.1, dur * 0.33, dur * 0.66, dur - 0.2]
    outs = []
    for j, t in enumerate(times):
        out_f = FR / f"{vpath.stem}_f{j}.png"
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(t), "-i", str(vpath),
            "-vframes", "1", "-q:v", "2", str(out_f)
        ], capture_output=True)
        outs.append(out_f)
    idx_map[vpath.name] = {"duration": dur, "frames": [str(p) for p in outs]}
    print(f"{i}/8 {vpath.name} ({dur:.1f}s) → {len(outs)} 帧", flush=True)

print(f"\n所有帧已存到: {FR}")
print(f"\n下一步用 GLM-4V 分析换装质量")
