import os
import shutil
import glob

def setup():
    # 查找所有包含 shot01.jpg 的路径
    matches = glob.glob("output/**/shot01.jpg", recursive=True)
    print("Found shot01 matches:", matches)
    
    today_comp_dir = os.path.abspath("output/2026-10-09/yangjiajiang_ep03/comparison")
    os.makedirs(today_comp_dir, exist_ok=True)
    
    if matches:
        src = matches[0]
        src_dir = os.path.dirname(src)
        print(f"Copying from {src_dir} to {today_comp_dir}...")
        for f in os.listdir(src_dir):
            if f.endswith((".jpg", ".png")):
                shutil.copy2(os.path.join(src_dir, f), os.path.join(today_comp_dir, f))
                
    files = os.listdir(today_comp_dir)
    print(f"Files in {today_comp_dir}:", files)
    target = os.path.join(today_comp_dir, "shot01.jpg")
    print("Target shot01 exists:", os.path.exists(target), "Size:", os.path.getsize(target) if os.path.exists(target) else 0)

if __name__ == "__main__":
    setup()
