#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_character_looks.py
=============================================================================
OOTD 角色定义与 5 款穿搭透明立绘资产生成器 (Asset Studio)

职责与架构定位：
与视频渲染流水线彻底解耦，专职负责前置阶段的：
1. 【角色定义 (Character IP)】：绑定模特面容（Face）、身材比例与基础人设
2. 【5 款换装 (5-Look Wardrobe)】：组织 5 套无手机正面站姿穿搭（支持导入、换脸、或已有成衣图）
3. 【RGBA 透明立绘提取】：自动调用 BiRefNet 提取 5 张去背景模特贴纸 (RGBA PNG)
4. 【标准化资产包交付】：生成 looks_manifest.json，可直接供 run_ootd_pipeline.py 一键加载

用法示例：
  # 从已有 5 张穿搭图快速提取角色贴纸资产包：
  python tools/ootd_study/build_character_looks.py \
      --character oriental_woman_v3 \
      --looks_dir output/2026-10-03/ootd_multilook_nophone/swap_nophone \
      --out_dir output/character_assets/autumn_collection_01
=============================================================================
"""
import argparse
import datetime
import glob
import json
import os
import shutil
import sys
import time

ROOT = r"D:\ai_projects\ComfyUI"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BIREFNET_MODEL = r"D:\OLLAMA_MODELS\models\background_removal\BiRefNet-general.safetensors"
DEFAULT_CHAR_DIR = os.path.join(ROOT, "input", "characters", "v3")


# 默认内置角色定义库
PRESET_CHARACTERS = {
    "oriental_woman_v3": {
        "name": "东方温婉女模 V3",
        "face_image": os.path.join(DEFAULT_CHAR_DIR, "C01_FACE_FRONT.png"),
        "body_image": os.path.join(DEFAULT_CHAR_DIR, "C02_BODY_FRONT.png"),
        "features": "22 years old asian elegant female, natural makeup, gentle soft smile, symmetrical face",
        "negative_prompt": "smartphone, cell phone, selfie stick, holding phone, deformed fingers, extra limbs, blur",
    }
}


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def extract_cutout_stickers(input_images, output_dir):
    """调用 BiRefNet 离线模型，批量将 5 张服装参考图转换为 RGBA 透明背景小人贴纸。"""
    os.makedirs(output_dir, exist_ok=True)
    log("[立绘提取] 加载 BiRefNet 抠像模型...")
    from comfy.bg_removal_model import load
    import numpy as np
    from PIL import Image
    import torch

    model = load(BIREFNET_MODEL)
    stickers = []

    for k, src in enumerate(input_images, start=1):
        dst = os.path.join(output_dir, f"g{k}_cutout.png")
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            log(f"[立绘提取] 复用已有贴纸: g{k}_cutout.png")
            stickers.append(dst)
            continue

        log(f"[立绘提取] 正在处理 g{k}: {os.path.basename(src)} ...")
        t0 = time.time()
        pil_img = Image.open(src).convert("RGB")
        w, h = pil_img.size

        img_np = np.array(pil_img).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_np).unsqueeze(0)

        with torch.no_grad():
            mask_tensor = model.encode_image(img_tensor)

        mask_np = mask_tensor.squeeze().cpu().numpy()
        mask_uint8 = np.clip(mask_np * 255.0, 0, 255).astype(np.uint8)

        r, g, b = pil_img.split()
        alpha = Image.fromarray(mask_uint8)
        rgba = Image.merge("RGBA", (r, g, b, alpha))
        rgba.save(dst, format="PNG")
        log(f"[立绘提取] g{k} 抠像完成 -> {os.path.basename(dst)} ({round(time.time() - t0, 2)}s)")
        stickers.append(dst)

    return stickers


def main():
    parser = argparse.ArgumentParser(description="OOTD 角色定义与 5 款穿搭透明立绘资产生成器")
    parser.add_argument("--character", default="oriental_woman_v3", help="角色预设 ID 或自定义角色配置文件 (JSON)")
    parser.add_argument("--looks_dir", default=None, help="输入的 5 张穿搭参考图所在目录")
    parser.add_argument("--out_dir", default=None, help="资产包输出目录")
    args = parser.parse_args()

    today = datetime.date.today().strftime("%Y-%m-%d")
    out_dir = args.out_dir or os.path.join(ROOT, "output", today, "character_assets", args.character)
    raw_dir = os.path.join(out_dir, "raw_looks")
    cutout_dir = os.path.join(out_dir, "transparent_stickers")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(cutout_dir, exist_ok=True)

    log(f"=== OOTD 角色穿搭资产工坊启动: character={args.character} ===")

    # 1. 解析角色定义
    if args.character in PRESET_CHARACTERS:
        char_info = PRESET_CHARACTERS[args.character]
        log(f"[角色定义] 载入内置角色预设: {char_info['name']}")
    elif os.path.exists(args.character):
        with open(args.character, "r", encoding="utf-8") as f:
            char_info = json.load(f)
        log(f"[角色定义] 载入外部角色文件: {args.character}")
    else:
        char_info = {
            "name": args.character,
            "features": "custom female model",
            "negative_prompt": "smartphone, holding phone, blur, deformed hands"
        }
        log(f"[角色定义] 创建新角色档案: {args.character}")

    # 2. 定位或收集 5 款参考图
    if args.looks_dir and os.path.isdir(args.looks_dir):
        src_files = sorted(glob.glob(os.path.join(args.looks_dir, "*.png")) +
                           glob.glob(os.path.join(args.looks_dir, "*.jpg")))[:5]
    else:
        # 兜底读取最近一次无手机参考图目录
        default_dir = os.path.join(ROOT, "output", "2026-10-03", "ootd_multilook_nophone", "swap_nophone")
        src_files = sorted(glob.glob(os.path.join(default_dir, "g*_00001_.png")))[:5]

    if len(src_files) < 5:
        log(f"[错误] 未能找到足额 5 张服装参考图 (当前仅找到 {len(src_files)} 张)")
        return 1

    # 拷贝并规范化命名入 raw_looks/
    copied_raw = []
    for k, p in enumerate(src_files, start=1):
        dst = os.path.join(raw_dir, f"g{k}_raw.png")
        shutil.copy2(p, dst)
        copied_raw.append(dst)
    log(f"[参考图归档] 5 款穿搭原图已归档至: {raw_dir}")

    # 3. 提取 5 款透明立绘贴纸
    stickers = extract_cutout_stickers(copied_raw, cutout_dir)

    # 4. 生成标准化资产清单清单文件 (looks_manifest.json)
    manifest = {
        "character": char_info,
        "created_at": datetime.datetime.now().isoformat(),
        "total_looks": 5,
        "looks": [
            {
                "id": f"g{k}",
                "index": k,
                "raw_image": os.path.relpath(copied_raw[k - 1], out_dir),
                "cutout_sticker": os.path.relpath(stickers[k - 1], out_dir),
                "is_transparent": True
            }
            for k in range(1, 6)
        ]
    }

    manifest_path = os.path.join(out_dir, "looks_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    log(f"\n=======================================================")
    log(f"★ 角色穿搭资产包构建完成! ★")
    log(f"资产包目录: {out_dir}")
    log(f"清单文件: {manifest_path}")
    log(f"透明立绘: {cutout_dir} (5 张 RGBA PNG)")
    log(f"后续制作: 直接将本目录作为 --looks 传给 run_ootd_pipeline.py 即可！")
    log(f"=======================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
