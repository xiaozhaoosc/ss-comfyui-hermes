#!/usr/bin/env python3
"""生成「赤壁夜袭」标题落版：黑幕 + 底部火光 + 烫金标题 + 上升火星粒子（4s, 24fps）"""
import math, os, random, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1344, 768
FPS = 24
DURATION = 4
TOTAL = FPS * DURATION
FONT = r"C:\Windows\Fonts\simkai.ttf"   # 楷体（最接近汉隶的可用字体）
TITLE = "赤壁夜袭"
OUT = r"D:\ai_projects\ComfyUI\output\chibi\title_card.mp4"

random.seed(42)

# 预生成火星粒子（上升 + 水平漂移 + 闪烁）
embers = []
for _ in range(55):
    embers.append({
        'x': random.uniform(0, W),
        'y0': random.uniform(0, H + 120),
        'speed': random.uniform(35, 110),      # 像素/秒 向上
        'r': random.uniform(1.0, 3.8),
        'drift': random.uniform(-20, 20),      # 水平漂移
        'phase': random.uniform(0, 2 * math.pi),
        'flicker': random.uniform(0.35, 1.0),
    })

# 预加载字体
title_font = ImageFont.truetype(FONT, 130)

def draw_frame(i):
    t = i / FPS
    img = Image.new("RGB", (W, H), (2, 1, 0))
    draw = ImageDraw.Draw(img)

    # 底部火光渐变（橙红，微微闪烁）
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    base = H * 0.55
    flicker = 0.85 + 0.15 * math.sin(t * 2.7)
    for y in range(int(base), H):
        ratio = (y - base) / (H - base)
        rr = int(150 * ratio * flicker)
        gg = int(38 * ratio * flicker)
        gd.line([(0, y), (W, y)], fill=(rr, gg, 0))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(img, glow, 0.55)
    draw = ImageDraw.Draw(img)

    # 火星粒子（上升）
    period = H + 120
    for e in embers:
        y = (e['y0'] - e['speed'] * t) % period
        if y > H:
            continue
        x = (e['x'] + e['drift'] * t) % W
        fl = e['flicker'] * (0.55 + 0.45 * math.sin(e['phase'] + t * 11))
        if fl <= 0.05:
            continue
        r = e['r']
        col = (255, int(150 * fl), int(25 * fl))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=col)

    # 标题文字（前 1.2s 淡入）
    fade = min(1.0, t / 1.2)
    if fade <= 0:
        return img

    text = TITLE
    bbox = draw.textbbox((0, 0), text, font=title_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2 - bbox[0]
    y = int(H * 0.56) - bbox[1]

    # 淡入 alpha 合成
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)

    # 光晕（金色，模糊）
    glow_alpha = int(140 * fade)
    ld.text((x, y), text, font=title_font, fill=(255, 200, 70, glow_alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(9))
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))

    # 主体文字（烫金：金色填充 + 深铜描边，模拟烧焦边缘）
    ld = ImageDraw.Draw(layer) if False else None
    draw = ImageDraw.Draw(img)
    gold = (int(240 * fade), int(196 * fade), int(80 * fade))
    draw.text((x, y), text, font=title_font, fill=gold,
              stroke_width=3, stroke_fill=(int(60 * fade), int(38 * fade), 0))

    return img

# 渲染帧
tmp = tempfile.mkdtemp(prefix="title_")
frame_dir = os.path.join(tmp, "frames")
os.makedirs(frame_dir)
for i in range(TOTAL):
    img = draw_frame(i)
    img.save(os.path.join(frame_dir, f"f{i:04d}.png"))
print(f"已渲染 {TOTAL} 帧")

# 编码为视频
cmd = [
    "ffmpeg", "-y",
    "-framerate", str(FPS),
    "-i", os.path.join(frame_dir, "f%04d.png"),
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "fast",
    OUT,
]
r = subprocess.run(cmd, capture_output=True, text=True)
print("ffmpeg 退出码:", r.returncode)
if r.returncode != 0:
    print((r.stderr or "")[-800:])

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print("完成:", OUT, "| 存在:", os.path.exists(OUT))
