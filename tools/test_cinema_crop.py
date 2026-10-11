import os
from PIL import Image, ImageFilter, ImageEnhance

# 制作电影级 9:16 景深扩展画幅
pure_art = Image.open("output/2026-10-09/yangjiajiang_ep03/clean_crops_test/clean_raw_art_shot02.png").convert("RGB")

W_target, H_target = 544, 960

# 1. 背景层：将原图充满 544x960 并进行古风柔焦虚化
bg = pure_art.resize((W_target, H_target), Image.Resampling.LANCZOS)
bg = bg.filter(ImageFilter.GaussianBlur(radius=25)) # 柔焦景深
enhancer = ImageEnhance.Brightness(bg)
bg = enhancer.enhance(0.85) # 微微压暗，突出前景

# 2. 前景层：保持原始比例居中放置
ratio = W_target / pure_art.width
fg_h = int(pure_art.height * ratio)
fg = pure_art.resize((W_target, fg_h), Image.Resampling.LANCZOS)

paste_y = (H_target - fg_h) // 2
bg.paste(fg, (0, paste_y))

out_p = "output/2026-10-09/yangjiajiang_ep03/clean_crops_test/test_cinema_shot02.jpg"
bg.save(out_p, quality=95)
print(f"Saved: {out_p}")
