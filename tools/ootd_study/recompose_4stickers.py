#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recompose_4stickers.py
重新合成 OOTD 成片：
1. 四角标升级为 4 个槽位（左上、右上、左下、右下完整轮转）
2. 角标采用纯人物+服装透明贴纸（去除矩形卡片背景墙，四角透光）
3. 严格对齐 BGM 卡点音轨
4. 抽取 5 款服装核心帧供视觉复核
"""
import os
import sys
import time
import cv2

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "tools", "ootd_study"))

import multilook_compose as mc
import ootd_multilook as ml
import ootd_outfit_swap as swap
import h3_fast_segmented as seg

OUT = os.path.join(ROOT, "output", "2026-10-03", "ootd_multilook_nophone")
BGM_PATH = os.path.join(ROOT, "input", "ken4", "face", "bgm原创", "Calling_Through_The_Screen (1).mp3")
out_path = os.path.join(OUT, "ootd_multilook_nophone_collage.mp4")

# 5 款已渲染好的 1080P/30fps 主画面视频
versions_cfg = [
    {"id": f"g{k}", "video": os.path.join(OUT, "versions", f"v{k}_30_00001_.mp4"), "shift": 0.0}
    for k in range(1, 6)
]

# 5 张透明小人贴纸
cutout_stickers = [
    os.path.join(OUT, "swap_cutout", f"g{k}_cutout.png")
    for k in range(1, 6)
]

# 4 槽位对称布局（左上、右上、左下、右下）
tile_defs = [
    {"x": 30, "y": 60, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
    {"x": 750, "y": 60, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
    {"x": 30, "y": 1300, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
    {"x": 750, "y": 1300, "w": 300, "h": 533, "offset": 0.0, "radius": 0, "border": 0},
]

cfg = {
    "project": "ootd_multilook_nophone",
    "date": "2026-10-03",
    "driving": os.path.join(ROOT, "input", "ootd_target_clean.mp4"),
    "plate": os.path.join(ROOT, "output", "2026-10-02", "ootd_multilook_poc", "plate_clean.png"),
    "out_dir": OUT,
    "out_path": out_path,
    "versions": versions_cfg,
    "looks": cutout_stickers,
    "tiles_mode": "ref",         # 静态参考模式（配合 RGBA 透明小人）
    "tile_defs": tile_defs,      # 显式锁定 4 个角标槽位
    "no_main_dash": True,        # 主人物去虚线
    "remove_worn": True,         # 换装后直接去除对应角标
    "bgm": BGM_PATH,             # 显式载入 BGM 原创音轨
    "bgm_auto": False,           # 已有精确卡点，直接使用
    "cuts": [2.926, 5.329, 7.732, 10.135],
    "fps": 30,
    "size": [1080, 1920],
    "single_person": False,
}

print(f"[recompose] 开始执行 4 槽位透明贴纸重合成 -> {out_path}")
t0 = time.time()
res = mc.run_compose(cfg)
elapsed = round(time.time() - t0, 1)
print(f"[recompose] 画面合成完成，耗时={elapsed}s")

# 检查/补充混入 BGM
if not seg.has_audio(out_path):
    print(f"[recompose] 正在补混 BGM: {os.path.basename(BGM_PATH)} ...")
    temp_with_audio = os.path.join(OUT, "temp_recompose_audio.mp4")
    swap.mix_bgm(out_path, BGM_PATH, temp_with_audio, total_sec=11.233, cut_sec=11.233)
    if os.path.exists(temp_with_audio) and seg.has_audio(temp_with_audio):
        os.replace(temp_with_audio, out_path)
        print("[recompose] BGM 混音完成！")

# 规格核验
dur = seg.probe_duration(out_path)
fps_val = seg.probe_fps(out_path)
frames = ml.probe_nb_frames(out_path)
size_mb = os.path.getsize(out_path) / 1e6
has_a = seg.has_audio(out_path)
print(f"[recompose] 成片指标: {dur:.2f}s | {fps_val:.1f}fps | {frames}帧 | {size_mb:.1f}MB | 音轨={has_a}")

# 重新抽取 5 张核心帧供复核
chk_ts = [1.5, 4.0, 6.5, 8.8, 10.8]
cap = cv2.VideoCapture(out_path)
for ts in chk_ts:
    idx = int(round(ts * fps_val))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame = cap.read()
    if ok:
        out_f = os.path.join(OUT, f"chk_t{ts:.1f}s.png")
        cv2.imwrite(out_f, frame)
        print(f"[recompose] 抽帧保存: t={ts}s -> {os.path.basename(out_f)}")
cap.release()

print("[recompose] 全部流程顺利完成！")
