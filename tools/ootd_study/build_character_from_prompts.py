#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_character_from_prompts.py
=============================================================================
OOTD 纯提示词驱动：全新角色 + 5 套全新穿搭 一键生成全自动流水线

核心功能：
1. 接收 1 段角色人设提示词 (Character Prompt)
2. 接收 5 段独立服装描述 (5 Outfit Prompts)
3. 自动注入 Qwen-Image-2.1 / FLUX T2I 生成 5 张高质量正面全身无手机参考图
4. 自动调用 BiRefNet 提取 5 张 RGBA 纯透明背景模特立绘贴纸
5. 自动打包标准资产清单 looks_manifest.json
6. 一键触发 run_ootd_pipeline.py 启动 9 块剪枝视频渲染与卡点合成

用法示例：
  python tools/ootd_study/build_character_from_prompts.py \
      --project ootd_new_model_test \
      --char_name "french_asian_muse"
=============================================================================
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "tools", "ootd_study"))

import h3_fast_submit as base
from build_character_looks import extract_cutout_stickers

COMFY_URL = "http://127.0.0.1:8188"
T2I_WORKFLOW = os.path.join(ROOT, "workflows", "v4", "qwen_image_2_1_t2i_v4.json")

# 全新测试人设定义 (French-Asian Muse 混血超模)
DEFAULT_CHAR_PROMPT = (
    "masterpiece, ultra-detailed, high fashion photography, "
    "a gorgeous 22-year-old French-Asian chic fashion model with shoulder-length wavy dark brown hair, "
    "natural gentle soft smile, frontal full body view, standing upright in clean modern minimalist studio, "
    "empty hands, hands relaxed naturally by sides, no smartphone, perfect anatomy, soft studio lighting"
)

# 5 套全新风格穿搭提示词
DEFAULT_OUTFITS = [
    {
        "id": "g1",
        "name": "燕麦色轻奢羊绒大衣",
        "prompt": "wearing an elegant oversized oatmeal cashmere wool coat, cream turtleneck, tailored trousers"
    },
    {
        "id": "g2",
        "name": "祖母绿缎面露背吊带开叉裙",
        "prompt": "wearing a glamorous emerald green silk satin backless slip dress with side slit"
    },
    {
        "id": "g3",
        "name": "复古千鸟格小香风编织套装",
        "prompt": "wearing a vintage black-and-white houndstooth tweed jacket and matching pleated mini skirt"
    },
    {
        "id": "g4",
        "name": "甜酷皮质短夹克与高腰工装裤",
        "prompt": "wearing a trendy cropped black leather biker jacket, white crop top, and olive green high-waisted cargo pants"
    },
    {
        "id": "g5",
        "name": "曜石黑抹胸星光晚礼裙",
        "prompt": "wearing a luxury strapless obsidian black velvet evening gown, diamond choker necklace"
    }
]

NEGATIVE_PROMPT = (
    "worst quality, low quality, smartphone, cell phone, mobile phone, holding phone, selfie stick, "
    "distorted hands, extra fingers, deformed fingers, extra limbs, bad anatomy, blurry, watermark"
)


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def generate_reference_images(char_prompt, outfits, raw_dir, date_str):
    """通过 T2I 工作流生成 5 套全身穿搭图。"""
    os.makedirs(raw_dir, exist_ok=True)
    with open(T2I_WORKFLOW, "r", encoding="utf-8") as f:
        tpl = json.load(f)

    # 统一 9:16 竖屏全身图
    tpl["7"]["inputs"]["width"] = 768
    tpl["7"]["inputs"]["height"] = 1344
    tpl["6"]["inputs"]["text"] = NEGATIVE_PROMPT
    tpl["8"]["inputs"]["steps"] = 16

    generated_images = []
    for idx, item in enumerate(outfits, start=1):
        target_png = os.path.join(raw_dir, f"g{idx}_{item['id']}.png")
        if os.path.exists(target_png) and os.path.getsize(target_png) > 10000:
            log(f"[T2I生图] 复用已有参考图: {os.path.basename(target_png)}")
            generated_images.append(target_png)
            continue

        full_prompt = f"{char_prompt}, {item['prompt']}"
        prefix = f"{date_str}/raw_looks/g{idx}"
        wf = json.loads(json.dumps(tpl))
        wf["5"]["inputs"]["text"] = full_prompt
        wf["8"]["inputs"]["seed"] = 1000 + idx * 77
        wf["10"]["inputs"]["filename_prefix"] = prefix

        log(f"[T2I生图] 正在生成 Look {idx} ({item['name']})...")
        r = base._post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        rec = base.wait_done(pid)
        files = [p for p in base.find_output_files(rec) if p.lower().endswith(".png")]
        if files:
            shutil.copy2(files[0], target_png)
            log(f"[T2I生图] Look {idx} 生成成功 -> {os.path.basename(target_png)}")
            generated_images.append(target_png)
        else:
            raise RuntimeError(f"Look {idx} 生图产物未找到")

    return generated_images


def main():
    parser = argparse.ArgumentParser(description="OOTD 纯提示词驱动全新角色穿搭生成流水线")
    parser.add_argument("--project", default="ootd_new_char_test", help="项目标识名")
    parser.add_argument("--char_name", default="french_asian_muse", help="角色名标识")
    parser.add_argument("--launch_video", action="store_true", default=True, help="是否连贯启动后续视频流水线")
    args = parser.parse_args()

    today = datetime.date.today().strftime("%Y-%m-%d")
    proj_dir = os.path.join(ROOT, "output", today, args.project)
    raw_dir = os.path.join(proj_dir, "raw_looks")
    cutout_dir = os.path.join(proj_dir, "transparent_stickers")
    os.makedirs(proj_dir, exist_ok=True)

    log(f"=======================================================")
    log(f"★ OOTD 纯提示词全新流程启动: {args.project} ★")
    log(f"角色人设: {args.char_name}")
    log(f"=======================================================")

    # 1. T2I 提示词直出 5 张全新去手机穿搭图
    raw_images = generate_reference_images(DEFAULT_CHAR_PROMPT, DEFAULT_OUTFITS, raw_dir, today)

    # 2. 自动 BiRefNet 提取 5 张 RGBA 透明小人立绘贴纸
    log(f"[立绘提取] 批量提取 5 张透明背景模特立绘贴纸...")
    stickers = extract_cutout_stickers(raw_images, cutout_dir)

    # 3. 产出资产清单
    manifest = {
        "project": args.project,
        "character": args.char_name,
        "char_prompt": DEFAULT_CHAR_PROMPT,
        "outfits": DEFAULT_OUTFITS,
        "raw_images": [os.path.basename(p) for p in raw_images],
        "stickers": [os.path.basename(p) for p in stickers],
    }
    manifest_file = os.path.join(proj_dir, "looks_manifest.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log(f"[资产就绪] 5套全新穿搭与透明贴纸资产包已生成: {manifest_file}")

    # 4. 自动串联启动后台视频流水线
    if args.launch_video:
        log(f"[自动推进] 启动视频渲染流水线 run_ootd_pipeline.py ...")
        cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "ootd_study", "run_ootd_pipeline.py"),
            "--project", args.project,
            "--date", today,
            "--looks", raw_dir
        ]
        # 后台运行，与当前会话解耦
        subprocess.Popen(cmd, cwd=ROOT)
        log(f"[后台托管] 视频渲染流水线已提交后台运行！")
        log(f"成片将自动归档至: output/{today}/{args.project}/{args.project}_collage.mp4")

    log("=== 前置初始化与后台任务提交全部完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
