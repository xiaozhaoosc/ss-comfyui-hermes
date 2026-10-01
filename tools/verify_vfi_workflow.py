#!/usr/bin/env python3
"""验证 workflows/jingling_vfi_enhance_ui.json — API 提交并轮询."""
import json, urllib.request, uuid, time, sys, os

BASE = "http://127.0.0.1:8188"
OUT_ROOT = r"D:\ai_projects\ComfyUI\output"

wf = {
    "1": {"class_type": "VHS_LoadVideo", "inputs": {
        "video": "jingling_v1/seg1_00001.mp4",
        "force_rate": 0, "custom_width": 0, "custom_height": 0,
        "frame_load_cap": 0, "skip_first_frames": 0, "select_every_nth": 1,
        "format": "AnimateDiff"
    }},
    "2": {"class_type": "ImageScale", "inputs": {
        "upscale_method": "lanczos", "width": 720, "height": 1280, "crop": "disabled",
        "image": ["1", 0]
    }},
    "3": {"class_type": "RIFEInterpolation", "inputs": {
        "source_fps": 24.0, "target_fps": 60.0, "scale": 1.0,
        "model_name": "flownet.pkl", "batch_size": 4, "use_fp16": True,
        "images": ["2", 0]
    }},
    "4": {"class_type": "VHS_VideoCombine", "inputs": {
        "frame_rate": 60, "loop_count": 0, "filename_prefix": "jingling_v1/final_720p_60fps",
        "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 18,
        "save_metadata": True, "trim_to_audio": False, "pingpong": False, "save_output": True,
        "images": ["3", 0], "audio": ["1", 2]
    }},
}

req = urllib.request.Request(f"{BASE}/prompt", data=json.dumps({"prompt": wf, "client_id": str(uuid.uuid4())}).encode(),
    headers={"Content-Type": "application/json"})
try:
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}:", e.read().decode(errors='replace')[:2000])
    sys.exit(1)
pid = r.get("prompt_id")
print(f"prompt_id={pid}")

t0 = time.time()
while time.time() - t0 < 900:
    try:
        h = json.loads(urllib.request.urlopen(f"{BASE}/history/{pid}", timeout=15).read())
        rec = h.get(pid)
        if rec:
            st = rec.get("status", {})
            print(f"  [{time.time()-t0:.0f}s] status_str={st.get('status_str')} completed={st.get('completed')}")
            if st.get("status_str") == "success" or st.get("completed"):
                outs = rec.get("outputs", {})
                for k, v in outs.items():
                    for fname in v.get("videos", []) + v.get("gifs", []) + v.get("images", []):
                        print(f"  output node {k}: {fname}")
                print(f"DONE {time.time()-t0:.0f}s")
                sys.exit(0)
            if st.get("status_str") == "error":
                print("ERROR:", json.dumps(st, ensure_ascii=False)[:600])
                sys.exit(1)
    except Exception as e:
        print("  q err:", e)
    time.sleep(10)
print("TIMEOUT")
sys.exit(2)
