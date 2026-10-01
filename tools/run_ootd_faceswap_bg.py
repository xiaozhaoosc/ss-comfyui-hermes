
def ensure_date_prefix(p):
    today = datetime.date.today().strftime('%Y-%m-%d')
    if not p.startswith(today):
        return f'{today}/{p}'
    return p
"""
run_ootd_faceswap_bg.py - Run FaceSwap + Background Replacement workflow
"""
import json
import urllib.request
import urllib.error
import time
import datetime
import os
import sys

COMFY = "http://127.0.0.1:8188"

def build_workflow(
    face_restore_model="none",
    face_restore_visibility=1.0,
    bg_image="bg_paris_terrace.jpg",
    frame_load_cap=90,
    select_every_nth=1,
    prefix="ootd_swap_bg_v3"
):
    wf = {
        "1": {
            "class_type": "VHS_LoadVideo",
            "inputs": {
                "video": "ootd_target.mp4",
                "force_rate": 0,
                "custom_width": 720,
                "custom_height": 1280,
                "frame_load_cap": frame_load_cap,
                "skip_first_frames": 0,
                "select_every_nth": select_every_nth,
                "format": "AnimateDiff"
            }
        },
        "2": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "characters/v3/C01_FACE_FRONT.png"
            }
        },
        "3": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "characters/v3/C03_LEFT_3Q.png"
            }
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {
                "image": "characters/v3/C04_RIGHT_3Q.png"
            }
        },
        "6": {
            "class_type": "ImageBatch",
            "inputs": {
                "image1": ["2", 0],
                "image2": ["3", 0]
            }
        },
        "7": {
            "class_type": "ImageBatch",
            "inputs": {
                "image1": ["6", 0],
                "image2": ["4", 0]
            }
        },
        "9": {
            "class_type": "ReActorBuildFaceModel",
            "inputs": {
                "images": ["7", 0],
                "save_mode": False,
                "send_only": False,
                "face_model_name": "Mean",
                "compute_method": "Mean"
            }
        },
        "10": {
            "class_type": "ReActorFaceSwap",
            "inputs": {
                "input_image": ["1", 0],
                "face_model": ["9", 0],
                "enabled": True,
                "swap_model": "inswapper_128.onnx",
                "facedetection": "YOLOv5l",
                "face_restore_model": face_restore_model,
                "face_restore_visibility": face_restore_visibility,
                "codeformer_weight": 0.5,
                "detect_gender_input": "no",
                "detect_gender_source": "no",
                "input_faces_index": "0",
                "source_faces_index": "0",
                "console_log_level": 1
            }
        },
        "20": {
            "class_type": "LoadImage",
            "inputs": {
                "image": bg_image
            }
        },
        "21": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["20", 0],
                "upscale_method": "lanczos",
                "width": 720,
                "height": 1280,
                "crop": "center"
            }
        },
        "25": {
            "class_type": "RepeatImageBatch",
            "inputs": {
                "image": ["21", 0],
                "amount": ["1", 1]
            }
        },
        "22": {
            "class_type": "LoadBackgroundRemovalModel",
            "inputs": {
                "bg_removal_name": "BiRefNet-general.safetensors"
            }
        },
        "23": {
            "class_type": "RemoveBackground",
            "inputs": {
                "bg_removal_model": ["22", 0],
                "image": ["10", 0]
            }
        },
        "24": {
            "class_type": "ImageCompositeMasked",
            "inputs": {
                "destination": ["25", 0],
                "source": ["10", 0],
                "mask": ["23", 0],
                "x": 0,
                "y": 0,
                "resize_source": False
            }
        },
        "11": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["24", 0],
                "audio": ["1", 2],
                "frame_rate": 30.0,
                "loop_count": 0,
                "filename_prefix": ensure_date_prefix(prefix),
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 18,
                "save_metadata": True,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True
            }
        }
    }
    return wf

def submit_workflow(wf):
    data = json.dumps({"prompt": wf}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY}/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            pid = res.get("prompt_id")
            print(f"Submitted Task! Prompt ID: {pid}")
            return pid
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8')
        print(f"Failed to submit: HTTP {e.code} - {err}")
        return None
    except Exception as e:
        print(f"Failed: {e}")
        return None

def wait_for_task(pid, timeout=600):
    print(f"Waiting for prompt {pid} to complete...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(f"{COMFY}/history/{pid}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if pid in data:
                    item = data[pid]
                    status = item.get("status", {})
                    outputs = item.get("outputs", {})
                    completed = status.get("completed", False)
                    messages = status.get("messages", [])
                    print(f"Task completed: {completed}, outputs count: {len(outputs)}")
                    elapsed = time.time() - start_time
                    print(f"Total time elapsed: {elapsed:.1f}s")
                    return True, outputs, elapsed
        except Exception as e:
            pass
        time.sleep(3)
    return False, {}, time.time() - start_time

def main():
    face_restore = sys.argv[1] if len(sys.argv) > 1 else "none"
    visibility = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    frames = int(sys.argv[3]) if len(sys.argv) > 3 else 90
    prefix = sys.argv[4] if len(sys.argv) > 4 else "ootd_swap_bg_v3"

    # 1. Generate and save standard API workflow
    wf_full = build_workflow(
        face_restore_model=face_restore,
        face_restore_visibility=visibility,
        bg_image="bg_paris_terrace.jpg",
        frame_load_cap=0,  # Full 421 frames in official saved json
        select_every_nth=1,
        prefix="ootd_swap_bg_v3"
    )
    api_path = r"D:\ai_projects\ComfyUI\workflows\v3\ootd_faceswap_bg_v3_api.json"
    os.makedirs(os.path.dirname(api_path), exist_ok=True)
    with open(api_path, "w", encoding="utf-8") as f:
        json.dump(wf_full, f, indent=2, ensure_ascii=False)
    print(f"Saved production API workflow (full cap=0) to: {api_path}")

    # 2. Build test workflow (with specified frames)
    wf_test = build_workflow(
        face_restore_model=face_restore,
        face_restore_visibility=visibility,
        bg_image="bg_paris_terrace.jpg",
        frame_load_cap=frames,
        select_every_nth=1,
        prefix=prefix
    )

    pid = submit_workflow(wf_test)
    if not pid:
        return
    
    success, outputs, elapsed = wait_for_task(pid, timeout=600)
    if success:
        print(f"SUCCESS! Output details: {json.dumps(outputs, indent=2)}")
    else:
        print("Task timed out or failed.")

if __name__ == "__main__":
    main()
