"""
run_ootd_faceswap.py - Run face-swap for OOTD video using Character V2 and V3 assets.
"""
import json
import time
import sys
import os
import urllib.request
import urllib.error
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
INPUT_VIDEO = "ootd_target.mp4"

# Character V2 (Intellectual Gallery)
V2_FRONT = "characters/v2/C01_FACE_FRONT.png"
V2_LEFT = "characters/v2/C03_LEFT_3Q.png"
V2_RIGHT = "characters/v2/C04_RIGHT_3Q.png"

# Character V3 (Pure Desire Long Hair)
V3_FRONT = "characters/v3/C01_FACE_FRONT.png"
V3_LEFT = "characters/v3/C03_LEFT_3Q.png"
V3_RIGHT = "characters/v3/C04_RIGHT_3Q.png"

def make_workflow(video_name, front_img, left_img, right_img, output_prefix):
    return {
        "1": {
            "class_type": "VHS_LoadVideo",
            "inputs": {
                "video": video_name,
                "force_rate": 0,
                "custom_width": 720,
                "custom_height": 1280,
                "frame_load_cap": 0,
                "skip_first_frames": 0,
                "select_every_nth": 1,
                "format": "AnimateDiff",
            },
        },
        "2": {"class_type": "LoadImage", "inputs": {"image": front_img}},
        "3": {"class_type": "LoadImage", "inputs": {"image": left_img}},
        "4": {"class_type": "LoadImage", "inputs": {"image": right_img}},
        "6": {"class_type": "ImageBatch", "inputs": {"image1": ["2", 0], "image2": ["3", 0]}},
        "7": {"class_type": "ImageBatch", "inputs": {"image1": ["6", 0], "image2": ["4", 0]}},
        "9": {
            "class_type": "ReActorBuildFaceModel",
            "inputs": {
                "images": ["7", 0],
                "save_mode": False,
                "send_only": False,
                "face_model_name": "Mean",
                "compute_method": "Mean",
            },
        },
        "10": {
            "class_type": "ReActorFaceSwap",
            "inputs": {
                "input_image": ["1", 0],
                "face_model": ["9", 0],
                "enabled": True,
                "swap_model": "inswapper_128.onnx",
                "facedetection": "YOLOv5l",
                "face_restore_model": "none",
                "face_restore_visibility": 1.0,
                "codeformer_weight": 0.5,
                "detect_gender_input": "no",
                "detect_gender_source": "no",
                "input_faces_index": "0",
                "source_faces_index": "0",
                "console_log_level": 1,
            },
        },
        "11": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["10", 0],
                "audio": ["1", 2],
                "frame_rate": 30.0,
                "loop_count": 0,
                "filename_prefix": output_prefix,
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 18,
                "save_metadata": True,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True,
            },
        },
    }

def submit_prompt(workflow):
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_queue():
    with urllib.request.urlopen(f"{COMFY}/queue", timeout=10) as resp:
        q = json.loads(resp.read().decode("utf-8"))
        running = len(q.get("queue_running", []))
        pending = len(q.get("queue_pending", []))
        return running, pending

def main():
    print("=== Submitting OOTD Video Face Swap Jobs ===")
    
    # Save workflow copy to workflows/v3/ per project rules
    wf_v2 = make_workflow(INPUT_VIDEO, V2_FRONT, V2_LEFT, V2_RIGHT, "ootd_swap_v2_character")
    wf_v3 = make_workflow(INPUT_VIDEO, V3_FRONT, V3_LEFT, V3_RIGHT, "ootd_swap_v3_character")
    
    os.makedirs(r"d:\ai_projects\ComfyUI\workflows\v3", exist_ok=True)
    with open(r"d:\ai_projects\ComfyUI\workflows\v3\ootd_faceswap_v2_api.json", "w", encoding="utf-8") as f:
        json.dump(wf_v2, f, indent=2, ensure_ascii=False)
    with open(r"d:\ai_projects\ComfyUI\workflows\v3\ootd_faceswap_v3_api.json", "w", encoding="utf-8") as f:
        json.dump(wf_v3, f, indent=2, ensure_ascii=False)
        
    print("[1/2] Submitting Job for Character V2 (知性盘发)...")
    res_v2 = submit_prompt(wf_v2)
    prompt_id_v2 = res_v2.get("prompt_id")
    print(f"  -> Prompt ID: {prompt_id_v2}")
    
    print("[2/2] Submitting Job for Character V3 (纯欲披发)...")
    res_v3 = submit_prompt(wf_v3)
    prompt_id_v3 = res_v3.get("prompt_id")
    print(f"  -> Prompt ID: {prompt_id_v3}")
    
    print("\nWaiting for jobs to process...")
    start_time = time.time()
    time.sleep(3)
    while True:
        try:
            running, pending = get_queue()
            elapsed = int(time.time() - start_time)
            print(f"  [{elapsed}s] Queue: {running} running, {pending} pending...")
            if running == 0 and pending == 0:
                print("\nAll face swap jobs completed!")
                break
        except Exception as e:
            print(f"  Warning polling queue: {e}")
        time.sleep(5)
        
    print("\n=== Execution Summary ===")
    output_dir = Path(r"d:\ai_projects\ComfyUI\output")
    for f in output_dir.glob("ootd_swap_v*.*"):
        if f.stat().st_mtime > start_time - 10:
            print(f"  Generated: {f.name} ({f.stat().st_size / 1024 / 1024:.2f} MB)")

if __name__ == "__main__":
    main()
