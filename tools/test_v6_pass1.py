import json
import urllib.request
import time
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

COMFY_URL = "http://127.0.0.1:8188"

pass1_prompt = {
    "2": {
        "class_type": "VHS_LoadVideo",
        "inputs": {
            "video": "runcha_dance.mp4",
            "force_rate": 24,
            "custom_width": 0,
            "custom_height": 0,
            "frame_load_cap": 277,
            "skip_first_frames": 0,
            "select_every_nth": 1,
            "format": "AnimateDiff"
        }
    },
    "3": {
        "class_type": "ImageScaleBy",
        "inputs": {
            "image": ["2", 0],
            "upscale_method": "lanczos",
            "scale_by": 0.5
        }
    },
    "4": {
        "class_type": "LoadMoGeModel",
        "inputs": {
            "model_name": "moge_3_vitl_fp16.safetensors"
        }
    },
    "5": {
        "class_type": "MoGeInference",
        "inputs": {
            "moge_model": ["4", 0],
            "image": ["3", 0],
            "resolution_level": 9,
            "fov_x_degrees": 0.0,
            "batch_size": 4,
            "force_projection": True,
            "apply_mask": True,
            "refine_steps": 3
        }
    },
    "6": {
        "class_type": "MoGeRender",
        "inputs": {
            "moge_geometry": ["5", 0],
            "output": "normal_opengl"
        }
    },
    "7": {
        "class_type": "LoadBackgroundRemovalModel",
        "inputs": {
            "bg_removal_name": "BiRefNet-general.safetensors"
        }
    },
    "8": {
        "class_type": "RemoveBackground",
        "inputs": {
            "bg_removal_model": ["7", 0],
            "image": ["3", 0]
        }
    },
    "9": {
        "class_type": "ImageCompositeMasked",
        "inputs": {
            "destination": ["3", 0],
            "source": ["6", 0],
            "x": 0,
            "y": 0,
            "resize_source": False,
            "mask": ["8", 0]
        }
    },
    "33": {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["9", 0],
            "frame_rate": 24.0,
            "loop_count": 0,
            "filename_prefix": "2026-10-13/v6_two_pass/runcha_normal_ref",
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 19,
            "save_metadata": False,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True
        }
    }
}

def submit_prompt(prompt_data):
    p = {"prompt": prompt_data, "client_id": "v6-pass1-test"}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req)
        res = json.loads(resp.read().decode('utf-8'))
        return res.get("prompt_id")
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code, e.read().decode('utf-8'))
        return None

def wait_for_prompt(prompt_id, timeout=600):
    print(f"Waiting for prompt {prompt_id} to finish...")
    start_t = time.time()
    while time.time() - start_t < timeout:
        time.sleep(3)
        try:
            req = urllib.request.Request(f"{COMFY_URL}/history/{prompt_id}")
            resp = urllib.request.urlopen(req)
            hist = json.loads(resp.read().decode('utf-8'))
            if prompt_id in hist:
                status = hist[prompt_id].get("status", {})
                print(f"Status: {status.get('status_str')}, completed: {status.get('completed')}")
                if status.get("status_str") == "error":
                    for msg in status.get("messages", []):
                        if msg[0] == "execution_error":
                            print("Execution Error Detail:", json.dumps(msg[1], indent=2))
                    return False, hist[prompt_id]
                if status.get("completed"):
                    outputs = hist[prompt_id].get("outputs", {})
                    print("Outputs:", json.dumps(outputs, indent=2))
                    return True, hist[prompt_id]
        except Exception as e:
            print("Poll error:", e)
    return False, None

def free_vram():
    data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/free", data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)
    print("VRAM freed after Pass 1")

if __name__ == "__main__":
    print("--- Submitting Pass 1 (Normal extraction + Masking) ---")
    pid = submit_prompt(pass1_prompt)
    if not pid:
        sys.exit(1)
    ok, res = wait_for_prompt(pid)
    if ok:
        print("Pass 1 SUCCESS!")
        free_vram()
    else:
        print("Pass 1 FAILED!")
        sys.exit(1)
