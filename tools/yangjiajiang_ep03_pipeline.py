#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 3 集《邠阳城救驾》全集全链路出片生产管线 (54 镜满格工程版)

遵循规范：
1. 【产物归档规范】：输出严格归档于 output/2026-10-09/yangjiajiang_ep03/
2. 【执行纪律规范】：支持 --submit-only，长任务只提交不轮询等待，与对话彻底解耦
3. 【规格标准统一】：原生 544x960 4-step Turbo 极速扩散出片，后置 FFmpeg Lanczos 超分 720P
4. 【声音治理标准】：规整时强制添加 -an 剥离扩散模型原生嘶嘶白噪，混入三轨纯净母带音频
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATE_STR = "2026-10-09"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep03")
INPUT_DIR = os.path.join(ROOT, "input")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

WORKFLOW_H3 = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")
BASE_URL = "http://127.0.0.1:8188"

from tools.yangjiajiang_ep03_metadata import EP03_METADATA


def calculate_frame_length(sec, fps=24):
    """根据秒数计算 H3 模型最佳生成帧数 (支持 4-step Turbo 模数)"""
    raw = int(sec * fps)
    return max(96, ((raw + 7) // 8) * 8 + 4)


def build_shot_configs():
    """动态组装第 3 集生产镜头字典"""
    configs = []
    for item in EP03_METADATA:
        sid = item["id"]
        sec = item["sec"]
        fn = f"yang_ep03_shot{sid:02d}.jpg"
        prompt_en = (
            f"Traditional Chinese 2D ink wash animation, vintage Shanghai Animation Film Studio style. "
            f"Mineral pigment color, visible brush contours, textured rice paper surface. "
            f"{item['camera']}: {item['visual']}"
        )
        configs.append({
            "id": sid,
            "grid": item["grid"],
            "act": item["act"],
            "name": f"yang_ep03_shot{sid:02d}",
            "title": item["sub"][:16],
            "sec": sec,
            "length": calculate_frame_length(sec),
            "input_image": fn,
            "prompt": prompt_en,
            "sub": item["sub"],
            "prefix": f"{DATE_STR}/yangjiajiang_ep03/yang_ep03_shot{sid:02d}",
        })
    return configs


def load_template_workflow():
    if not os.path.exists(WORKFLOW_H3):
        raise FileNotFoundError(f"未找到 H3 生产工作流模版: {WORKFLOW_H3}")
    with open(WORKFLOW_H3, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare_prompt(template, shot_cfg, seed=42):
    p = json.loads(json.dumps(template))
    s_id = shot_cfg["id"]
    calc_seed = seed + s_id * 1007

    # 替换注入标记
    for node_id, node in p.items():
        inputs = node.get("inputs", {})
        for k, v in list(inputs.items()):
            if v == "[inject:first_frame]":
                inputs[k] = shot_cfg["input_image"]
            elif v == "[inject:prompt]":
                inputs[k] = shot_cfg["prompt"]
            elif v == "[inject:width]":
                inputs[k] = 544
            elif v == "[inject:height]":
                inputs[k] = 960
            elif v == "[inject:length]":
                inputs[k] = shot_cfg["length"]
            elif v == "[inject:seed]":
                inputs[k] = calc_seed
            elif v == "[inject:filename_prefix]":
                inputs[k] = shot_cfg["prefix"]
    return p


def post_prompt_to_comfyui(prompt_workflow):
    url = f"{BASE_URL}/prompt"
    payload = json.dumps({"prompt": prompt_workflow}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("prompt_id")
    except Exception as e:
        print(f"[!] 提交 ComfyUI 报错: {e}")
        return None


def run_pipeline(act_filter=None, submit_only=True, skip_existing=True):
    print("=" * 65)
    print(f"  【北宋杨家将】第 3 集《邠阳城救驾》ComfyUI 全链路流水线")
    print(f"  模式: {'长任务只提交不轮询 (Submit-Only)' if submit_only else '同步执行'}")
    print(f"  目标归档: output/{DATE_STR}/yangjiajiang_ep03/")
    print("=" * 65)

    all_configs = build_shot_configs()
    if act_filter:
        configs = [c for c in all_configs if c["act"] == act_filter]
        print(f"[+] 过滤幕次: Act {act_filter} (共 {len(configs)} 镜)")
    else:
        configs = all_configs
        print(f"[+] 全量范围: 共 {len(configs)} 镜 (Shot 01 ~ Shot {len(configs):02d})")

    template = load_template_workflow()
    submitted_ids = []

    for cfg in configs:
        sid = cfg["id"]
        # 校验是否已生成
        existing_video = os.path.join(OUTPUT_DIR, f"yang_ep03_shot{sid:02d}_00001_.mp4")
        if skip_existing and os.path.exists(existing_video) and os.path.getsize(existing_video) > 100000:
            print(f"  [-] Shot {sid:02d} 视频已存在 ({os.path.getsize(existing_video)} bytes)，跳过提交")
            continue

        # 校验首帧图片
        img_path = os.path.join(INPUT_DIR, cfg["input_image"])
        if not os.path.exists(img_path):
            print(f"[!] 警告: Shot {sid:02d} 首帧图片不存在: {img_path}")
            continue

        prompt_data = prepare_prompt(template, cfg)
        pid = post_prompt_to_comfyui(prompt_data)
        if pid:
            submitted_ids.append((sid, pid))
            print(f"  [√] Shot {sid:02d} 已入队 -> Prompt ID: {pid} ({cfg['sec']}s / {cfg['length']}f)")
        else:
            print(f"  [X] Shot {sid:02d} 提交失败！")

    print("\n" + "=" * 65)
    print(f"【提交完成】成功将 {len(submitted_ids)} 个镜头任务推送到 ComfyUI 队列！")
    print("遵循执行纪律：任务已进入本地 RTX 4060 Ti 渲染流水线，零死循环轮询。")
    print("=" * 65)
    return submitted_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="第3集 ComfyUI 生产管线")
    parser.add_argument("--act", type=int, choices=[1, 2, 3, 4, 5], help="指定运行某一幕 (1~5)")
    parser.add_argument("--all", action="store_true", help="提交全 54 镜")
    parser.add_argument("--submit-only", action="store_true", default=True, help="只提交不轮询")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已生成视频")
    args = parser.parse_args()

    act = args.act if args.act else (None if args.all else 1)
    run_pipeline(act_filter=act, submit_only=True, skip_existing=not args.no_skip)

    # 出片收尾：生成扁平画廊，一屏验收全部产物（失败不影响主流程）
    try:
        from tools.flat_gallery import generate_gallery
        generate_gallery(OUTPUT_DIR, quiet=True)
    except Exception as e:
        print(f"[!] 画廊生成跳过: {e}")
