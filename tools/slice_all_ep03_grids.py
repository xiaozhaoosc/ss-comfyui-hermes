import os
import shutil
from PIL import Image

def slice_all():
    artifact_dir = r"C:\Users\kenzhao\.gemini\antigravity\brain\6bb43a19-f574-41a1-a679-7d82b1966d15"
    out_dir = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/frames")
    input_dir = os.path.abspath("input/yang_ep03")
    grids_dir = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/grids")
    
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(grids_dir, exist_ok=True)

    grid_files = [
        "yang_ep03_grid01_1791472115813.jpg",
        "yang_ep03_grid02_1791550444596.jpg",
        "yang_ep03_grid03_1791550632582.jpg",
        "yang_ep03_grid04_1791550668116.jpg",
        "yang_ep03_grid05_1791550699143.jpg",
        "yang_ep03_grid06_1791550794066.jpg"
    ]

    for g_idx, g_file in enumerate(grid_files, 1):
        src_path = os.path.join(artifact_dir, g_file)
        if not os.path.exists(src_path):
            print(f"[!] Grid {g_idx} file not found: {src_path}")
            continue
            
        # 归档大图
        grid_copy = os.path.join(grids_dir, f"grid0{g_idx}.jpg")
        shutil.copy2(src_path, grid_copy)
        print(f"\n[+] Processing Grid 0{g_idx}: {grid_copy}")
        
        img = Image.open(src_path)
        W, H = img.size
        
        # 3x3 均匀网格
        col_w = W / 3.0
        row_h = H / 3.0
        
        for r in range(3):
            for c in range(3):
                shot_num = (g_idx - 1) * 9 + (r * 3 + c + 1)
                
                # 初始格边界
                left = c * col_w
                top = r * row_h
                right = (c + 1) * col_w
                bottom = (r + 1) * row_h
                
                # 裁切内缩：剥离黑线边框及底部的英文字幕说明栏（下部裁剪 14%）
                pad_x = col_w * 0.04
                pad_top = row_h * 0.04
                pad_bottom = row_h * 0.16 # 彻底去除英文底栏
                
                c_left = int(left + pad_x)
                c_top = int(top + pad_top)
                c_right = int(right - pad_x)
                c_bottom = int(bottom - pad_bottom)
                
                cropped = img.crop((c_left, c_top, c_right, c_bottom))
                
                # 目标规范尺寸: 544x960 或保持高解析度以供超分
                # 统一缩放至标准 544x960 (9:16)
                shot_544 = cropped.resize((544, 960), Image.Resampling.LANCZOS)
                
                save_f1 = os.path.join(out_dir, f"yang_ep03_shot{shot_num:02d}.jpg")
                save_f2 = os.path.join(input_dir, f"yang_ep03_shot{shot_num:02d}.jpg")
                
                shot_544.save(save_f1, quality=95)
                shot_544.save(save_f2, quality=95)
                
        print(f"  [√] Grid 0{g_idx} 切片完成 -> Shot {(g_idx-1)*9+1:02d} ~ Shot {g_idx*9:02d}")

    print("\n" + "="*60)
    print(f"全剧 54 镜首帧切片 100% 处理完毕！")
    print(f"存档目录: {out_dir}")
    print(f"输入目录: {input_dir}")
    print("="*60)

if __name__ == "__main__":
    slice_all()
