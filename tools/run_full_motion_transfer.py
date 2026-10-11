import os
import sys
import json
import shutil
import urllib.request
import subprocess
from datetime import date

ROOT = r"d:\ai_projects\ComfyUI"
COMFY_URL = "http://127.0.0.1:8188"
FFMPEG = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
BGM = r"D:\ai_projects\ComfyUI\input\ken4\face\bgm原创\Calling_Through_The_Screen (1).mp3"

API_TEMPLATE = os.path.join(ROOT, "workflows", "v3", "wan_animate_pure_pose_api.json")
TODAY_STR = date.today().strftime("%Y-%m-%d")
OUT_DIR = os.path.join(ROOT, "output", TODAY_STR, "motion_transfer_full")
os.makedirs(OUT_DIR, exist_ok=True)

CHAR_IMG = "005-822807425_18090503405430819_9034340549182780041_n.jpeg"

TASKS = [
    {
        "name": "ig14",
        "title": "Instagram14 (6.07s / 182 frames)",
        "video": "Instagram14_video.mp4",
        "pose": "motion_poses/ig14_user_test/ig14_user_test_full_pose_pure.mp4",
        "face": "motion_poses/ig14_user_test/ig14_user_test_full_face_pure.mp4",
        "total_frames": 182,
        # Chunks:
        # chunk 0: offset 0 (already generated)
        # chunk 1: offset 45, length 49 (frames 45..93)
        # chunk 2: offset 89, length 49 (frames 89..137)
        # chunk 3: offset 133, length 49 (frames 133..181)
        "chunks": [
            {"idx": 1, "offset": 45, "length": 49},
            {"idx": 2, "offset": 89, "length": 49},
            {"idx": 3, "offset": 133, "length": 49}
        ]
    },
    {
        "name": "ig18",
        "title": "Instagram18 (7.07s / 212 frames)",
        "video": "Instagram18_video.mp4",
        "pose": "motion_poses/ig18_user_test/ig18_user_test_full_pose_pure.mp4",
        "face": "motion_poses/ig18_user_test/ig18_user_test_full_face_pure.mp4",
        "total_frames": 212,
        # Chunks:
        # chunk 0: offset 0 (already generated)
        # chunk 1: offset 45, length 49 (frames 45..93)
        # chunk 2: offset 89, length 49 (frames 89..137)
        # chunk 3: offset 133, length 49 (frames 133..181)
        # chunk 4: offset 163, length 49 (frames 163..211)
        "chunks": [
            {"idx": 1, "offset": 45, "length": 49},
            {"idx": 2, "offset": 89, "length": 49},
            {"idx": 3, "offset": 133, "length": 49},
            {"idx": 4, "offset": 163, "length": 49}
        ]
    }
]

def post_prompt(workflow_prompt):
    payload = json.dumps({"prompt": workflow_prompt}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data.get("prompt_id")

def submit_all_chunks():
    with open(API_TEMPLATE, "r", encoding="utf-8") as f:
        template = json.load(f)

    submitted = []
    for task in TASKS:
        print(f"\n=======================================================")
        print(f"Submitting remaining chunks for: {task['title']}")
        print(f"=======================================================")
        
        for chk in task["chunks"]:
            wf = json.loads(json.dumps(template))
            out_prefix = f"{TODAY_STR}/motion_transfer_full/{task['name']}_chk{chk['idx']}"
            
            wf["10"]["inputs"]["image"] = CHAR_IMG
            wf["12"]["inputs"]["file"] = task["video"]
            wf["22"]["inputs"]["file"] = task["pose"]
            wf["24"]["inputs"]["file"] = task["face"]
            
            wf["17"]["inputs"]["width"] = 480
            wf["17"]["inputs"]["height"] = 832
            wf["17"]["inputs"]["length"] = chk["length"]
            wf["17"]["inputs"]["video_frame_offset"] = chk["offset"]
            wf["18"]["inputs"]["seed"] = 20261008 + chk["idx"] * 10
            wf["21"]["inputs"]["filename_prefix"] = out_prefix
            
            pid = post_prompt(wf)
            print(f"  ✔ Chunk {chk['idx']} (offset={chk['offset']}, len={chk['length']}) -> Prompt ID: {pid}")
            submitted.append({
                "task": task["name"],
                "chunk_idx": chk["idx"],
                "prompt_id": pid,
                "output_prefix": out_prefix
            })
            
    record_file = os.path.join(OUT_DIR, "submitted_jobs.json")
    with open(record_file, "w", encoding="utf-8") as f:
        json.dump(submitted, f, indent=2)
    print(f"\nAll {len(submitted)} remaining chunks successfully queued in ComfyUI!")
    print(f"Job record saved to: {record_file}")
    return submitted

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--submit":
        submit_all_chunks()
    else:
        print("Usage: python tools/run_full_motion_transfer.py --submit")
