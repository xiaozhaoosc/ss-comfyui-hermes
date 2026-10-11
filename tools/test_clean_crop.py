import os
from PIL import Image, ImageOps, ImageFilter
import numpy as np

grids_dir = "output/2026-10-09/yangjiajiang_ep03/grids"
test_dir = "output/2026-10-09/yangjiajiang_ep03/clean_crops_test"
os.makedirs(test_dir, exist_ok=True)

# 自动在给定 cell 内探测连续黑边框 (内部为纯净画芯)
def find_inner_box(arr_gray, min_w=150, min_h=100):
    H, W = arr_gray.shape
    # 找横线
    row_black = (arr_gray < 60).sum(axis=1)
    dark_rows = np.where(row_black > W * 0.6)[0]
    # 找竖线
    col_black = (arr_gray < 60).sum(axis=0)
    dark_cols = np.where(col_black > H * 0.4)[0]
    
    if len(dark_rows) >= 2 and len(dark_cols) >= 2:
        top = dark_rows[0] + 2
        bottom = dark_rows[-1] - 2
        left = dark_cols[0] + 2
        right = dark_cols[-1] - 2
        if right - left >= min_w and bottom - top >= min_h:
            return (left, top, right, bottom)
    return None

def process_grid_to_clean_shots(grid_path, start_id=1):
    img = Image.open(grid_path).convert("RGB")
    W, H = img.size
    cell_w = W // 3
    cell_h = H // 3
    
    clean_images = []
    
    for r in range(3):
        for c in range(3):
            sid = start_id + r * 3 + c
            # 当前 cell 区域
            x_min, y_min = c * cell_w, r * cell_h
            x_max, y_max = (c + 1) * cell_w, (r + 1) * cell_h
            cell_img = img.crop((x_min, y_min, x_max, y_max))
            
            # 转灰度探测内部黑边
            cell_gray = np.array(cell_img.convert("L"))
            box = find_inner_box(cell_gray)
            
            if box:
                clean_art = cell_img.crop(box)
            else:
                # 容错 fallback: 去掉顶部 12% 和底部 28% (文字区)
                clean_art = cell_img.crop((int(cell_w * 0.08), int(cell_h * 0.10), int(cell_w * 0.95), int(cell_h * 0.74)))
                
            clean_images.append((sid, clean_art))
            
    return clean_images

# 测试 grid01
clean_shots = process_grid_to_clean_shots(os.path.join(grids_dir, "grid01.jpg"), start_id=1)
for sid, art in clean_shots[:3]:
    out_p = os.path.join(test_dir, f"clean_raw_art_shot{sid:02d}.png")
    art.save(out_p)
    print(f"Saved: {out_p} ({art.size})")

print("Clean art detection test done!")
