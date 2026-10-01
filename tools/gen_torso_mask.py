#!/usr/bin/env python3
"""
生成 torso mask — 用于 IDM-VTON 换装
白 = 换装区域 (30%~95% 高度)
黑 = 保留区域 (脸+头发+腿)

用法:
    python tools/gen_torso_mask.py --input output/faceswap_comfyui/swap_restored_00001.png
    python tools/gen_torso_mask.py --input output/faceswap_comfyui/ --output masks/
    python tools/gen_torso_mask.py --input image.png --top 0.25 --bottom 0.92
"""
import os
import sys
import argparse
import numpy as np
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image


def gen_torso_mask(width, height, top_ratio=0.30, bottom_ratio=0.95, feather=15):
    """生成 torso mask (白=换装, 黑=保留)"""
    mask = np.zeros((height, width), dtype=np.uint8)
    
    top_px = int(height * top_ratio)
    bottom_px = int(height * bottom_ratio)
    
    # 主体白色区域
    mask[top_px:bottom_px, :] = 255
    
    # 边缘羽化
    if feather > 0:
        for i in range(feather):
            alpha = int(255 * (i / feather))
            if top_px - feather + i >= 0:
                mask[top_px - feather + i, :] = alpha
            if bottom_px + i < height:
                mask[bottom_px + i, :] = 255 - alpha
    
    return mask


def process_image(img_path, output_path, top_ratio, bottom_ratio, feather):
    """处理单张图片"""
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    
    mask = gen_torso_mask(w, h, top_ratio, bottom_ratio, feather)
    mask_img = Image.fromarray(mask, mode="L")
    mask_img.save(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="生成 torso mask (白=换装区域)")
    parser.add_argument("--input", required=True, help="输入图片或目录")
    parser.add_argument("--output", default=None, help="输出路径 (默认: 同目录, 文件名加 _mask)")
    parser.add_argument("--top", type=float, default=0.30, help="mask起始高度比例 (默认0.30)")
    parser.add_argument("--bottom", type=float, default=0.95, help="mask结束高度比例 (默认0.95)")
    parser.add_argument("--feather", type=int, default=15, help="边缘羽化像素 (默认15)")
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if input_path.is_dir():
        # 批量处理
        out_dir = Path(args.output) if args.output else input_path / "masks"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in exts and "_mask" not in f.stem])
        
        print(f"找到 {len(files)} 张图片")
        for i, f in enumerate(files, 1):
            out_path = out_dir / f"{f.stem}_mask.png"
            process_image(str(f), str(out_path), args.top, args.bottom, args.feather)
            print(f"  [{i}/{len(files)}] {f.name} → {out_path.name}")
        
        print(f"\n✅ 完成! {len(files)} 个 mask 已保存到 {out_dir}")
    else:
        # 单张处理
        if args.output:
            out_path = Path(args.output)
        else:
            out_path = input_path.parent / f"{input_path.stem}_mask.png"
        
        process_image(str(input_path), str(out_path), args.top, args.bottom, args.feather)
        print(f"✅ {input_path.name} → {out_path.name}")


if __name__ == "__main__":
    main()
