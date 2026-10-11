#!/usr/bin/env python3
"""
为 ComfyUI 生成的图片/视频添加水印标识
用法:
  python watermark.py --input image.png --output watermarked.png
  python watermark.py --input video.mp4 --output watermarked.mp4
  python watermark.py --dir output/folder/  # 批量处理目录
"""
import cv2
import numpy as np
import subprocess
import os
import glob
import argparse

WATERMARK_TEXT = "comfyui ai生成-ken"

def add_watermark_to_image(img, text=WATERMARK_TEXT, font_scale=0.6, thickness=1):
    """在图片底部添加半透明水印条"""
    h, w = img.shape[:2]
    
    # 计算文字大小
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    
    # 水印条高度
    bar_h = th + 16
    bar_y = h - bar_h
    
    # 创建半透明黑色底条
    overlay = img.copy()
    cv2.rectangle(overlay, (0, bar_y), (w, h), (0, 0, 0), -1)
    alpha = 0.5
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    
    # 居中绘制白色文字
    text_x = (w - tw) // 2
    text_y = bar_y + th + 6
    cv2.putText(img, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    
    return img


def process_image(input_path, output_path=None):
    """为单张图片添加水印"""
    img = cv2.imread(input_path)
    if img is None:
        print(f"  无法读取: {input_path}")
        return False
    
    img = add_watermark_to_image(img)
    
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_wm{ext}"
    
    cv2.imwrite(output_path, img)
    return True


def process_video(input_path, output_path=None):
    """为视频添加水印（用 ffmpeg drawtext）"""
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_wm{ext}"
    
    # 用 ffmpeg drawtext 添加水印（带半透明黑色底条）
    # 注意：ffmpeg 不支持中文路径，所以用临时文件
    tmp_in = None
    tmp_out = None
    
    try:
        # 检查路径是否含中文
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in input_path)
        
        if has_chinese:
            import shutil
            tmp_in = input_path + "_wm_tmp_input.mp4"
            tmp_out = output_path + "_wm_tmp_output.mp4"
            shutil.copy2(input_path, tmp_in)
            actual_in = tmp_in
            actual_out = tmp_out
        else:
            actual_in = input_path
            actual_out = output_path
        
        # drawtext filter: 底部半透明黑条 + 白色文字
        escaped_text = WATERMARK_TEXT.replace("'", "\\'").replace(":", "\\:")
        drawtext_filter = (
            f"drawbox=y=ih-40:color=black@0.5:width=iw:height=40:t=fill,"
            f"drawtext=text='{escaped_text}':"
            f"fontcolor=white:fontsize=24:"
            f"x=(w-text_w)/2:y=h-32:"
            f"fontfile=C\\\\:/Windows/Fonts/msyh.ttc"
        )
        
        cmd = [
            "ffmpeg", "-y", "-i", actual_in,
            "-vf", drawtext_filter,
            "-c:a", "copy",
            "-c:v", "libx264", "-crf", "18",
            actual_out
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            # 如果中文字体失败，用默认字体
            drawtext_filter2 = (
                f"drawbox=y=ih-40:color=black@0.5:width=iw:height=40:t=fill,"
                f"drawtext=text='{escaped_text}':"
                f"fontcolor=white:fontsize=24:"
                f"x=(w-text_w)/2:y=h-32"
            )
            cmd2 = [
                "ffmpeg", "-y", "-i", actual_in,
                "-vf", drawtext_filter2,
                "-c:a", "copy",
                "-c:v", "libx264", "-crf", "18",
                actual_out
            ]
            result = subprocess.run(cmd2, capture_output=True, text=True)
        
        if result.returncode == 0:
            if has_chinese and tmp_out:
                import shutil
                shutil.move(tmp_out, output_path)
            return True
        else:
            print(f"  ffmpeg错误: {result.stderr[-200:]}")
            return False
    
    finally:
        if tmp_in and os.path.exists(tmp_in):
            os.remove(tmp_in)
        if tmp_out and os.path.exists(tmp_out):
            os.remove(tmp_out)


def process_directory(dir_path, suffix="_wm"):
    """批量处理目录中的所有图片和视频"""
    img_exts = ('.png', '.jpg', '.jpeg', '.webp')
    vid_exts = ('.mp4', '.avi', '.mov', '.mkv')
    
    files = []
    for f in os.listdir(dir_path):
        ext = os.path.splitext(f)[1].lower()
        if ext in img_exts or ext in vid_exts:
            if suffix not in f:  # 跳过已加水印的
                files.append(f)
    
    print(f"找到 {len(files)} 个文件待处理")
    
    for i, f in enumerate(files):
        path = os.path.join(dir_path, f)
        ext = os.path.splitext(f)[1].lower()
        base = os.path.splitext(f)[0]
        out = os.path.join(dir_path, f"{base}{suffix}{ext}")
        
        print(f"  [{i+1}/{len(files)}] {f}", end=" ")
        
        if ext in img_exts:
            ok = process_image(path, out)
        else:
            ok = process_video(path, out)
        
        print("✅" if ok else "❌")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="添加 'comfyui ai生成-ken' 水印")
    parser.add_argument("--input", "-i", help="输入文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--dir", "-d", help="批量处理目录")
    args = parser.parse_args()
    
    if args.dir:
        process_directory(args.dir)
    elif args.input:
        ext = os.path.splitext(args.input)[1].lower()
        if ext in ('.mp4', '.avi', '.mov', '.mkv'):
            process_video(args.input, args.output)
        else:
            process_image(args.input, args.output)
    else:
        print("用法: python watermark.py --input image.png")
        print("      python watermark.py --dir output/folder/")
