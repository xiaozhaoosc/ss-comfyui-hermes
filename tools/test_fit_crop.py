import os
from PIL import Image, ImageOps
import numpy as np

# 测试 shot02：提取真实纯净画芯，并用 ImageOps.fit 生成不拉伸、无黑边、无英文的完美 9:16 首帧
img = Image.open("output/2026-10-09/yangjiajiang_ep03/grids/grid01.jpg").convert("RGB")
W, H = img.size
cell_w, cell_h = W // 3, H // 3

# cell 0, 1 (Shot 02)
cell_img = img.crop((cell_w, 0, cell_w * 2, cell_h))
cell_gray = np.array(cell_img.convert("L"))

# 找横竖黑线
row_black = (cell_gray < 55).sum(axis=1)
dark_rows = np.where(row_black > cell_w * 0.5)[0]
col_black = (cell_gray < 55).sum(axis=0)
dark_cols = np.where(col_black > cell_h * 0.35)[0]

top = dark_rows[0] + 3
bottom = dark_rows[-1] - 3
left = dark_cols[0] + 3
right = dark_cols[-1] - 3

pure_art = cell_img.crop((left, top, right, bottom))
print(f"Pure art box: ({left}, {top}, {right}, {bottom}), size: {pure_art.size}")

# 方式 1：ImageOps.fit (满幅不拉伸，居中偏上微裁)
fit_9x16 = ImageOps.fit(pure_art, (544, 960), centering=(0.5, 0.45), method=Image.Resampling.LANCZOS)
fit_9x16.save("output/2026-10-09/yangjiajiang_ep03/clean_crops_test/test_fit_shot02.jpg", quality=95)

# 方式 2：古宣纸背景纵向延伸 (保持完整画芯不裁切，上下宣纸底纹延伸)
bg = Image.new("RGB", (544, 960), (238, 233, 222)) # 宣纸米白色调
# 将 pure_art 按宽度 544 等比缩放
ratio = 544.0 / pure_art.width
new_h = int(pure_art.height * ratio)
scaled_art = pure_art.resize((544, new_h), Image.Resampling.LANCZOS)
paste_y = (960 - new_h) // 2
bg.paste(scaled_art, (0, paste_y))
bg.save("output/2026-10-09/yangjiajiang_ep03/clean_crops_test/test_canvas_shot02.jpg", quality=95)

print("Saved test_fit_shot02.jpg and test_canvas_shot02.jpg")
