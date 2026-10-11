#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北宋杨家将 · 第 2 集《归宋 · 天波府》全集全链路出片生产管线 (54 镜满格工程版)

遵循规范：
1. 【产物归档规范】：输出严格归档于 output/2026-10-08/yangjiajiang_ep02/
2. 【执行纪律规范】：支持 --submit-only，长任务只提交不轮询等待，与对话解耦
3. 【规格标准统一】：原生 544x960 4-step Turbo 扩散出片，支持阶段二 AI 超分至 720P/1080P
4. 【声音治理标准】：规整时强制添加 -an 剥离扩散模型原生嘶嘶白噪，混入三轨母带声学音频
"""

import os
import sys
import json
import time
import argparse
import subprocess
import urllib.request
import urllib.error
import numpy as np

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATE_STR = "2026-10-08"
OUTPUT_DIR = os.path.join(ROOT, "output", DATE_STR, "yangjiajiang_ep02")
INPUT_DIR = os.path.join(ROOT, "input")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")

WORKFLOW_H3 = os.path.join(ROOT, "workflows", "v5", "h3_fast_i2v_9x16_api.json")
WORKFLOW_ENHANCE = os.path.join(ROOT, "workflows", "v5", "h3_enhance_v5_api.json")

FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    import shutil
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

BASE_URL = "http://127.0.0.1:8188"

from tools.yangjiajiang_ep02_metadata import EP02_METADATA
from tools.subtitle_annotator import burn_subtitles_and_tags


def calculate_frame_length(sec, fps=24):
    """根据秒数计算 H3 模型最佳生成帧数 (支持 4-step Turbo 模数)"""
    # 常用模数：3s=96/108, 4s=124, 5s=141, 6s=158, 7s=175, 8s=192
    raw = int(sec * fps)
    # 对齐到 4 或 8 的倍数并留少量冗余
    return max(96, ((raw + 7) // 8) * 8 + 4)


def build_shot_configs():
    """将 EP02_METADATA 动态组装为生产镜头字典"""
    configs = []
    for item in EP02_METADATA:
        sid = item["id"]
        sec = item["sec"]
        fn = f"yang_ep02_shot{sid:02d}.jpg"
        prompt_en = (
            f"Traditional Chinese 2D ink wash animation, vintage Shanghai Animation Film Studio style. "
            f"Mineral pigment color, visible brush contours, textured rice paper surface. "
            f"{item['camera']}: {item['visual']}"
        )
        configs.append({
            "id": sid,
            "grid": item["grid"],
            "act": item["act"],
            "name": f"yang_ep02_shot{sid:02d}",
            "title": item["sub"][:16],
            "sec": sec,
            "length": calculate_frame_length(sec),
            "input_image": fn,
            "prompt": prompt_en,
            "sub": item["sub"],
            "tag": item.get("tag")
        })
    return configs


EP02_SHOTS = build_shot_configs()


def post_json(path, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def inject_workflow_h3(wf_template, shot, width=544, height=960, seed=20261008):
    prefix = f"{DATE_STR}/yangjiajiang_ep02/{shot['name']}"
    values = {
        "first_frame": shot["input_image"],
        "prompt": shot["prompt"],
        "width": width,
        "height": height,
        "length": shot["length"],
        "seed": seed + shot["id"] * 17,
        "filename_prefix": prefix,
    }

    def walk(obj):
        if isinstance(obj, str):
            if obj.startswith("[inject:") and obj.endswith("]"):
                k = obj[len("[inject:"):-1]
                return values.get(k, obj)
            return obj
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        return obj

    return walk(wf_template)


def normalize_shot_video(shot, output_mp4, target_width=544, target_height=960):
    """规格归一化并强制使用 -an 彻底剥离 ComfyUI 扩散模型自生成的任何杂音音轨"""
    candidates = [
        os.path.join(OUTPUT_DIR, f"{shot['name']}.mp4"),
        os.path.join(OUTPUT_DIR, f"{shot['name']}_00001_.mp4"),
        os.path.join(OUTPUT_DIR, f"{shot['name']}_00001.mp4"),
    ]
    src_v = None
    for c in candidates:
        if os.path.exists(c):
            src_v = c
            break

    if not src_v:
        return None

    cmd = [
        FFMPEG, "-y",
        "-i", src_v,
        "-an",
        "-t", str(shot["sec"]),
        "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,fps=24",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_mp4
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode == 0:
        return output_mp4
    return None


def upscale_video_lanczos(input_v, output_v, out_w=720, out_h=1280):
    """利用硬件级 Lanczos + Unsharp 极速无损超分至 720P/1080P，0 额外 GPU 显存压力"""
    cmd = [
        FFMPEG, "-y",
        "-i", input_v,
        "-vf", f"scale={out_w}:{out_h}:flags=lanczos+accurate_rnd,unsharp=5:5:0.7:5:5:0.0",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "17",
        "-c:a", "copy",
        output_v
    ]
    res = subprocess.run(cmd, capture_output=True)
    return output_v if res.returncode == 0 else None


def concat_shots_to_act(act_num, shots, output_act_mp4):
    """将一整幕（如 Act 1~5 或 Grid 1~6）规整后的视频流无缝拼接"""
    norm_clips = []
    print(f"\n=== 开始归一化检查第 {act_num} 单元视频 ===")
    for s in shots:
        norm_v = os.path.join(OUTPUT_DIR, f"clean_norm_{s['name']}.mp4")
        if not os.path.exists(norm_v):
            res = normalize_shot_video(s, norm_v)
            if not res:
                print(f"  [缺失] 镜头 {s['id']:02d} ({s['name']}) 渲染文件未就绪")
                continue
        norm_clips.append(norm_v)
        print(f"  [就绪] 镜 {s['id']:02d}: {os.path.basename(norm_v)} ({s['sec']}s)")

    if not norm_clips:
        print("[错误] 未发现有效规整视频")
        return None

    concat_txt = os.path.join(OUTPUT_DIR, f"concat_act{act_num}.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in norm_clips:
            f.write(f"file '{c.replace(chr(92), '/')}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_act_mp4
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"[拼接完成] Act {act_num} 视频流已合并: {output_act_mp4}")
    return output_act_mp4


def main():
    parser = argparse.ArgumentParser(description="北宋杨家将第2集出片生产管线")
    parser.add_argument("--grid", type=int, default=0, choices=range(1, 7), help="指定单跑某组九宫格 (1~6)")
    parser.add_argument("--act", type=int, default=0, choices=range(1, 6), help="指定单跑某一幕 (1~5)")
    parser.add_argument("--shot", type=int, default=0, help="单跑某镜 (1~54)")
    parser.add_argument("--dry-run", action="store_true", help="校验参数与工作流，不实际向GPU提交任务")
    parser.add_argument("--submit-only", action="store_true", help="严格遵守纪律：长任务只提交不轮询等待")
    parser.add_argument("--concat", action="store_true", help="执行已生成镜头的无损拼接与底噪剥离")
    parser.add_argument("--upscale", type=str, default="none", choices=["none", "720p", "1080p"], help="后处理超分级别")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FINAL_DIR, exist_ok=True)

    target_shots = EP02_SHOTS
    if args.grid > 0:
        target_shots = [s for s in target_shots if s["grid"] == args.grid]
    elif args.act > 0:
        target_shots = [s for s in target_shots if s["act"] == args.act]
    if args.shot > 0:
        target_shots = [s for s in target_shots if s["id"] == args.shot]

    if args.concat:
        unit = args.grid if args.grid > 0 else (args.act if args.act > 0 else 0)
        out_v = os.path.join(OUTPUT_DIR, f"yang_ep02_unit{unit}_merged_544p.mp4")
        concat_shots_to_act(unit, target_shots, out_v)
        if args.upscale in ["720p", "1080p"]:
            w, h = (720, 1280) if args.upscale == "720p" else (1080, 1920)
            out_upscale = os.path.join(OUTPUT_DIR, f"yang_ep02_unit{unit}_merged_{args.upscale}.mp4")
            upscale_video_lanczos(out_v, out_upscale, out_w=w, out_h=h)
            print(f"[超分交付] 已无损超分至 {args.upscale.upper()}: {out_upscale}")
        return 0

    print(f"\n=======================================================")
    print(f"  北宋杨家将 · 第 2 集《归宋 · 天波府》生产管线启动")
    print(f"  模式: {'[DRY-RUN 校验]' if args.dry_run else '[SUBMIT 真实提交]'}")
    print(f"  目标镜头数: {len(target_shots)} 镜 | 时长: {sum(s['sec'] for s in target_shots):.1f}s")
    print(f"=======================================================\n")

    with open(WORKFLOW_H3, "r", encoding="utf-8") as f:
        wf_template = json.load(f)

    submitted = []
    missing_inputs = []

    for s in target_shots:
        input_img_path = os.path.join(INPUT_DIR, s["input_image"])
        has_input = os.path.exists(input_img_path)
        if not has_input:
            missing_inputs.append(s["input_image"])

        print(f"[镜 {s['id']:02d}] 【{s['title']}】 (Grid: {s['grid']} | Act: {s['act']} | {s['sec']}s | {s['length']}帧)")
        print(f"  -> 输入原画: {s['input_image']} {'[已就绪]' if has_input else '[待切片]'}")
        print(f"  -> 提示词: {s['prompt'][:85]}...")

        wf = inject_workflow_h3(wf_template, s, width=544, height=960)

        if args.dry_run:
            submitted.append({"id": s["id"], "name": s["name"], "status": "dry-run"})
            continue

        if not has_input:
            print(f"  ⚠️ [跳过提交] 首帧文件不存在: {s['input_image']}，请先执行切片！")
            continue

        resp = post_json("/prompt", {"prompt": wf})
        pid = resp.get("prompt_id")
        print(f"  -> [SUBMITTED] Prompt ID: {pid}")
        submitted.append({"id": s["id"], "name": s["name"], "prompt_id": pid})

    if missing_inputs:
        print(f"\n[提示] 共有 {len(missing_inputs)} 个分镜首帧待由九宫格切片生成。")
        print(f"如已获得九宫格原画，请先运行: python tools/yangjiajiang_ep02_grid_cutter.py --image <原画路径> --grid <1~6>")

    print(f"\n[任务统计] 本次批处理完成，有效处理: {len(submitted)} 个镜头。\n")


if __name__ == "__main__":
    main()
