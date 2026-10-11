import shutil
import glob
import os

brain_dir = r"C:\Users\kenzhao\.gemini\antigravity\brain\4aefe332-d92f-4d3d-b105-afe461645605"
input_dir = r"D:\ai_projects\ComfyUI\input"
os.makedirs(input_dir, exist_ok=True)

mapping = {
    "shot04": "ep01_shot04_cinnabar",
    "shot05": "ep01_shot05_crimson_sun",
    "shot06": "ep01_shot06_horizon",
    "shot07": "ep01_shot07_titlecard",
    "shot08": "ep01_shot08_frosty_dawn",
    "shot09": "ep01_shot09_outpost_tower",
    "shot10": "ep01_shot10_tower_flag",
    "shot11": "ep01_shot11_banner_closeup",
    "shot12": "ep01_shot12_sentinel",
}

for shot_name, prefix in mapping.items():
    cands = glob.glob(os.path.join(brain_dir, f"{prefix}*.jpg"))
    if not cands:
        cands = glob.glob(os.path.join(brain_dir, f"{prefix}*.png"))
    if cands:
        cands.sort(key=os.path.getmtime, reverse=True)
        src = cands[0]
        dst = os.path.join(input_dir, f"yang_ep01_{shot_name}.jpg")
        shutil.copy(src, dst)
        print(f"Copied {os.path.basename(src)} -> {os.path.basename(dst)}")

copied = sorted([f for f in os.listdir(input_dir) if f.startswith("yang_ep01_")])
print("Final copied files in input/:", copied)
