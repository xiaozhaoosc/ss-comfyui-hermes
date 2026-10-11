import shutil
import os

brain_dir = r"C:\Users\kenzhao\.gemini\antigravity\brain\f970c72f-40d0-4e19-b5f8-9f70bb48ecc5"
target_dir = r"D:\ai_projects\ComfyUI\input"

mapping = {
    13: "ep01_shot13_two_columns_1791109956324.jpg",
    14: "ep01_shot14_cavalry_clash_1791109978421.jpg",
    15: "ep01_shot15_arrow_caught_1791109996170.jpg",
    16: "ep01_shot16_melee_combat_1791110015792.jpg",
    17: "ep01_shot17_pan_unseated_1791110041222.jpg",
    18: "ep01_shot18_pan_grudge_1791110059951.jpg",
    19: "ep01_shot19_ambush_pincer_1791110079630.jpg",
}

for sid, fn in mapping.items():
    src = os.path.join(brain_dir, fn)
    dst = os.path.join(target_dir, f"yang_ep01_shot{sid:02d}.jpg")
    shutil.copy(src, dst)
    print(f"Copied {fn} -> yang_ep01_shot{sid:02d}.jpg ({os.path.getsize(dst)} bytes)")

print("Successfully replaced all 7 inputs!")
