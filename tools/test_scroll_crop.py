import os
from PIL import Image, ImageDraw
import numpy as np

pure_art = Image.open("output/2026-10-09/yangjiajiang_ep03/clean_crops_test/clean_raw_art_shot02.png").convert("RGBA")
W_target, H_target = 544, 960

# 取原画边缘平均背景色 (通常为温暖宣纸色，如 RGB 240, 236, 226)
top_edge = np.array(pure_art)[0, :, :3]
bg_color = tuple(int(x) for x in top_edge.mean(axis=0))

# 建立 544x960 宣纸底画布
bg = Image.new("RGBA", (W_target, H_target), bg_color + (255,))

# 缩放前景至宽度 544
ratio = W_target / pure_art.width
fg_h = int(pure_art.height * ratio)
fg = pure_art.resize((W_target, fg_h), Image.Resampling.LANCZOS)

# 创建上下边缘羽化遮罩 (渐变透明度)
mask = Image.new("L", (W_target, fg_h), 255)
draw = ImageDraw.Draw(mask)
fade_h = 24
for y in range(fade_h):
    alpha = int(255 * (y / fade_h))
    draw.line([(0, y), (W_target, y)], fill=alpha)
    draw.line([(0, fg_h - 1 - y), (W_target, fg_h - 1 - y)], fill=alpha)

paste_y = (H_target - fg_h) // 2
bg.paste(fg, (0, paste_y), mask=mask)

out_p = "output/2026-10-09/yangjiajiang_ep03/clean_crops_test/test_scroll_shot02.jpg"
bg.convert("RGB").save(out_p, quality=95)
print(f"Saved: {out_p}")
