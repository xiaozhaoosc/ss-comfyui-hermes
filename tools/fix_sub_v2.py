#!/usr/bin/env python3
"""字幕叠加 + 拼接 (使用本地字体)"""
import os, subprocess

BASE = r"D:\ai_projects\ComfyUI\output\zombie_girlfriend"
FINAL_DIR = os.path.join(BASE, "final")
FONT = os.path.join(BASE, "msyh.ttc").replace("\\", "/")

SCENES = {
    1: "这日子没法过了！外头全是丧尸，俺得赶紧找个地方躲起来！",
    2: "嘘...别出声...千万别叫它们发现了...老天爷，吓死俺了。",
    3: "哎？这个丧尸...她咋不咬人呢？长得还挺好看嘞...",
    4: "嗯...嗯...",
    5: "她...她居然在保护我？一个丧尸在保护我？这到底是咋回事？",
    6: "走，俺带你去逛街！虽然商场都废了，但咱也得有点仪式感不是？",
    7: "来来来，这样按，对对对，你学嘞还挺快嘞！",
    8: "饿了吧？来，吃点东西。虽然你可能不饿，但俺觉得你还是得尝尝。",
    9: "她总是这样...俺睡着了她就在旁边守着...比闹钟还准时。",
    10: "你看那个星星，像不像你的眼睛？嗯...虽然你现在眼睛有点红...",
    11: "不好！外头来了一大群丧尸！快快快，把门堵上！",
    12: "她...她居然对着那些丧尸吼？就为了保护我？",
    13: "没事没事，就擦破点皮，别哭了别哭了，俺又没死。",
    14: "嗯...嗯嗯...",
    15: "药！找到药了！太好了，有救了有救了！",
    16: "我...我没死？她一直在我旁边守着？眼圈都红了...",
    17: "别怕了，有俺在呢，以后咱俩再也不分开了。",
    18: "虽然俺没有钻戒，但这个银勺子戒指...你能接受不？嫁给我吧！",
    19: "我愿意。虽然没有亲朋好友，但这夕阳...比啥都美。",
    20: "新的世界，新的开始。走吧，咱去看看前头还有啥。",
}

print("📺 叠加字幕...", flush=True)
ok_count = 0
for scene_num, text in SCENES.items():
    input_file = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}.mp4")
    output_file = os.path.join(FINAL_DIR, f"scene_{scene_num:02d}_sub.mp4")

    if not os.path.exists(input_file):
        continue

    text_esc = text.replace("'", "\\'").replace(":", "\\:")
    vf = f"drawtext=fontfile='{FONT}':text='{text_esc}':fontcolor=white:fontsize=24:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-60"

    cmd = [
        "ffmpeg", "-y", "-i", input_file,
        "-vf", vf,
        "-c:v", "libx264", "-c:a", "copy",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_file
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode == 0:
        ok_count += 1
        print(f"  OK scene_{scene_num:02d}", flush=True)
    else:
        print(f"  FAIL scene_{scene_num:02d}: {result.stderr.decode('utf-8','ignore')[-150:]}", flush=True)

print(f"  字幕: {ok_count}/20", flush=True)

# 拼接4集
print("\n🎞️ 拼接4集...", flush=True)
episodes = {
    1: ("第一集_相遇篇", range(1, 6)),
    2: ("第二集_相处篇", range(6, 11)),
    3: ("第三集_危机篇", range(11, 16)),
    4: ("第四集_重生篇", range(16, 21)),
}
for ep_num, (ep_title, scene_range) in episodes.items():
    concat_file = os.path.join(FINAL_DIR, f"concat_ep{ep_num}.txt")
    scene_files = []
    for sn in scene_range:
        sub = os.path.join(FINAL_DIR, f"scene_{sn:02d}_sub.mp4")
        normal = os.path.join(FINAL_DIR, f"scene_{sn:02d}.mp4")
        if os.path.exists(sub) and os.path.getsize(sub) > 0:
            scene_files.append(sub)
        elif os.path.exists(normal):
            scene_files.append(normal)

    if not scene_files:
        continue

    with open(concat_file, "w") as f:
        for sf in scene_files:
            f.write(f"file '{sf}'\n")

    output_file = os.path.join(FINAL_DIR, f"{ep_title}.mp4")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
           "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_file]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode == 0:
        size_mb = os.path.getsize(output_file) / 1024 / 1024
        print(f"  OK {ep_title} ({size_mb:.1f}MB)", flush=True)
    else:
        print(f"  FAIL {ep_title}", flush=True)

print("\n🎉 完成!", flush=True)
