"""
ComfyUI API 批量换装处理
对已提取的帧逐个提交 IDM-VTON 工作流，等待完成，下载结果
"""
import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.parse
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"
COMFY_INPUT = r"D:\ai_projects\ComfyUI\input"
COMFY_OUTPUT = r"D:\ai_projects\ComfyUI\output"

FRAMES_DIR = r"D:\ai_projects\ComfyUI\output\tryon_faceswap\2_faceswap_tryon.mp4_tmp\input_frames"
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\tryon_faceswap\2_faceswap_tryon.mp4_tmp\output_frames"
os.makedirs(OUTPUT_DIR, exist_ok=True)

GARMENT = "garment.jpg"
MASK = "torso_mask.png"
GARMENT_DESC = "an elegant nude-apricot dress"
WIDTH, HEIGHT = 768, 1024
STEPS = 30
SEED = 42

def upload_to_input(src_path: str) -> str:
    """Copy image to ComfyUI input dir, return filename"""
    fname = os.path.basename(src_path)
    dest = os.path.join(COMFY_INPUT, fname)
    if not os.path.exists(dest) or os.path.getmtime(src_path) > os.path.getmtime(dest):
        shutil.copy2(src_path, dest)
    return fname

def queue_prompt(workflow):
    data = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["prompt_id"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Queue failed: {e.code} {body}")

def wait_for_result(prompt_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}") as resp:
                history = json.loads(resp.read())
            if prompt_id in history:
                s = history[prompt_id].get("status", {}).get("status_str", "?")
                if s == "success":
                    return history[prompt_id]
                elif s == "error":
                    msgs = history[prompt_id].get("status", {}).get("messages", [])
                    for m in msgs:
                        if m[0] == "execution_error":
                            raise RuntimeError(f"Node {m[1].get('node_id')}: {m[1].get('exception_message')}")
                    raise RuntimeError("Unknown error")
        except urllib.error.HTTPError:
            pass
        time.sleep(3)
    raise TimeoutError(f"Timeout after {timeout}s")

def download_result(history_entry, output_path):
    for nid, out in history_entry.get("outputs", {}).items():
        if "images" in out:
            for img in out["images"]:
                params = urllib.parse.urlencode({
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": "output"
                })
                url = f"{COMFYUI_URL}/view?{params}"
                urllib.request.urlretrieve(url, output_path)
                return True
    return False

def make_workflow(person_fn, garment_fn, mask_fn):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": person_fn, "upload": "image"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": garment_fn, "upload": "image"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": mask_fn, "upload": "image"}},
        "5": {"class_type": "DensePosePreprocessor", "inputs": {"image": ["1", 0]}},
        "6": {"class_type": "PipelineLoader", "inputs": {"weight_dtype": "float16"}},
        "7": {"class_type": "IDM-VTON", "inputs": {
            "pipeline": ["6", 0], "human_img": ["1", 0], "pose_img": ["5", 0],
            "mask_img": ["3", 0], "garment_img": ["2", 0],
            "garment_description": GARMENT_DESC,
            "negative_prompt": "monochrome, lowres, bad anatomy, worst quality, low quality",
            "width": WIDTH, "height": HEIGHT, "num_inference_steps": STEPS,
            "guidance_scale": 2.0, "strength": 1.0, "seed": SEED}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "tryon_v2"}}
    }

def main():
    frames = sorted(Path(FRAMES_DIR).glob("frame_*.png"))
    total = len(frames)
    print(f"Total frames: {total}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Estimated time: {total * 2.5:.0f} min ({total * 2.5 / 60:.1f} hours)")
    print()

    # Pre-upload garment and mask
    upload_to_input(os.path.join(COMFY_INPUT, GARMENT))
    upload_to_input(os.path.join(COMFY_INPUT, MASK))

    times = []
    done_count = 0

    for i, frame_path in enumerate(frames):
        stem = frame_path.stem.replace("frame_", "")
        out_name = f"tryon_v2_{stem}.png"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        # Skip if already done
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
            done_count += 1
            continue

        t0 = time.time()

        # Upload frame
        frame_fn = upload_to_input(str(frame_path))

        # Queue workflow
        wf = make_workflow(frame_fn, GARMENT, MASK)
        try:
            pid = queue_prompt(wf)
            result = wait_for_result(pid, timeout=300)
            download_result(result, out_path)
        except Exception as e:
            print(f"  [{i+1}/{total}] ERROR: {e}")
            print(f"  Resume with: checking existing files")
            continue

        elapsed = time.time() - t0
        times.append(elapsed)
        avg = sum(times[-10:]) / len(times[-10:])
        remaining = avg * (total - i - 1 + done_count)

        if (i + 1) % 1 == 0 or i == total - 1:
            print(f"  [{i+1}/{total}] {frame_path.name} → {elapsed:.1f}s "
                  f"(avg={avg:.0f}s, ETA={remaining/60:.0f}min)")

    print(f"\n✅ Done! Processed {len(times)} frames, skipped {done_count}")

if __name__ == "__main__":
    main()
