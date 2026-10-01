"""
benchmark_gfpgan.py - Benchmark GFPGANv1.4 face restoration and speed optimization
"""
import json
import urllib.request
import urllib.error
import time
import os
import sys
import cv2
import numpy as np

COMFY = "http://127.0.0.1:8188"

def build_swap_workflow(
    face_restore_model="none",
    face_restore_visibility=1.0,
    frame_load_cap=60,
    select_every_nth=1,
    prefix="bench_face"
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
        "2": {"class_type": "LoadImage", "inputs": {"image": "characters/v3/C01_FACE_FRONT.png"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": "characters/v3/C03_LEFT_3Q.png"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": "characters/v3/C04_RIGHT_3Q.png"}},
        "6": {"class_type": "ImageBatch", "inputs": {"image1": ["2", 0], "image2": ["3", 0]}},
        "7": {"class_type": "ImageBatch", "inputs": {"image1": ["6", 0], "image2": ["4", 0]}},
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
        "11": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["10", 0],
                "audio": ["1", 2],
                "frame_rate": 30.0 if select_every_nth == 1 else 15.0,
                "loop_count": 0,
                "filename_prefix": prefix,
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
            return res.get("prompt_id")
    except Exception as e:
        print(f"Failed to submit: {e}")
        return None

def wait_for_task(pid, timeout=600):
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
                    if status.get("completed", False):
                        elapsed = time.time() - start_time
                        return True, outputs, elapsed
        except Exception:
            pass
        time.sleep(2)
    return False, {}, time.time() - start_time

def run_test_case(name, restore_model, visibility, frame_cap, step, prefix):
    print(f"\n==========================================")
    print(f"Running Test Case: {name}")
    print(f"Model: {restore_model}, Visibility: {visibility}, Frames: {frame_cap}, Step: {step}")
    print(f"==========================================")
    wf = build_swap_workflow(
        face_restore_model=restore_model,
        face_restore_visibility=visibility,
        frame_load_cap=frame_cap,
        select_every_nth=step,
        prefix=prefix
    )
    pid = submit_workflow(wf)
    if not pid:
        return None
    success, outputs, elapsed = wait_for_task(pid)
    if not success:
        print(f"Test case {name} failed or timed out.")
        return None
    
    # Get video path
    video_path = None
    if "11" in outputs and "gifs" in outputs["11"] and len(outputs["11"]["gifs"]) > 0:
        video_path = outputs["11"]["gifs"][0].get("fullpath")
    
    actual_frames = frame_cap // step if step > 1 else frame_cap
    fps_perf = actual_frames / elapsed if elapsed > 0 else 0
    print(f"Finished {name}: {elapsed:.2f}s | {fps_perf:.2f} fps (total processed frames: {actual_frames})")
    return {
        "name": name,
        "restore_model": restore_model,
        "visibility": visibility,
        "elapsed": elapsed,
        "frames": actual_frames,
        "fps": fps_perf,
        "video_path": video_path
    }

def main():
    results = []

    # Case 1: Baseline (No face restore) - 60 frames
    res1 = run_test_case(
        name="Baseline (None)",
        restore_model="none",
        visibility=1.0,
        frame_cap=60,
        step=1,
        prefix="bench_gfpgan_none"
    )
    if res1: results.append(res1)

    # Case 2: Full GFPGANv1.4 (visibility 1.0) - 60 frames
    res2 = run_test_case(
        name="GFPGANv1.4 (Full 1.0)",
        restore_model="GFPGANv1.4.pth",
        visibility=1.0,
        frame_cap=60,
        step=1,
        prefix="bench_gfpgan_v10"
    )
    if res2: results.append(res2)

    # Case 3: Tuned GFPGANv1.4 (visibility 0.8 natural blend) - 60 frames
    res3 = run_test_case(
        name="GFPGANv1.4 (Natural 0.8)",
        restore_model="GFPGANv1.4.pth",
        visibility=0.8,
        frame_cap=60,
        step=1,
        prefix="bench_gfpgan_v08"
    )
    if res3: results.append(res3)

    # Case 4: Speed Optimized (select_every_nth: 2, 30 frames processed)
    res4 = run_test_case(
        name="GFPGANv1.4 (Optimized 15fps)",
        restore_model="GFPGANv1.4.pth",
        visibility=0.8,
        frame_cap=60,
        step=2,
        prefix="bench_gfpgan_opt_15fps"
    )
    if res4: results.append(res4)

    # Save summary report
    summary_path = r"C:\Users\kenzhao\.gemini\antigravity-ide\brain\e7ffce2a-ce49-4a6b-b8fa-359c0c02abae\scratch\gfpgan_benchmark_results.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll tests completed! Summary saved to {summary_path}")

if __name__ == "__main__":
    main()
