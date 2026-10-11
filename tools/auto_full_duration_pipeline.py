import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import json
import subprocess
import cv2
import urllib.request
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

TASKS = {
    "ig14": {
        "title": "Instagram14 (6.07s / 182 frames)",
        "src_video": r"C:\Users\kenzhao\Downloads\Instagram14_video.mp4",
        "input_video": "Instagram14_video.mp4",
        "pose_rel": "motion_poses/ig14_user_test/ig14_user_test_full_pose_pure.mp4",
        "face_rel": "motion_poses/ig14_user_test/ig14_user_test_full_face_pure.mp4",
        "pose_abs": os.path.join(ROOT, "input", "motion_poses", "ig14_user_test", "ig14_user_test_full_pose_pure.mp4"),
        "chunk0_file": os.path.join(ROOT, "output", "2026-10-08", "motion_transfer", "ig14_user_test_00001_.mp4"),
        "total_frames": 182,
        "fps": 30.0,
        "chunk_defs": [
            {"idx": 1, "offset": 45, "length": 49, "trim": (0, 44)},
            {"idx": 2, "offset": 89, "length": 49, "trim": (0, 44)},
            {"idx": 3, "offset": 133, "length": 49, "trim": (0, 49)}
        ],
        "chunk0_trim": (0, 45)
    },
    "ig18": {
        "title": "Instagram18 (7.07s / 212 frames)",
        "src_video": r"C:\Users\kenzhao\Downloads\Instagram18_video.mp4",
        "input_video": "Instagram18_video.mp4",
        "pose_rel": "motion_poses/ig18_user_test/ig18_user_test_full_pose_pure.mp4",
        "face_rel": "motion_poses/ig18_user_test/ig18_user_test_full_face_pure.mp4",
        "pose_abs": os.path.join(ROOT, "input", "motion_poses", "ig18_user_test", "ig18_user_test_full_pose_pure.mp4"),
        "chunk0_file": os.path.join(ROOT, "output", "2026-10-04", "motion_transfer", "ig18_user_test_00001_.mp4"),
        "total_frames": 212,
        "fps": 30.0,
        "chunk_defs": [
            {"idx": 1, "offset": 45, "length": 49, "trim": (0, 44)},
            {"idx": 2, "offset": 89, "length": 49, "trim": (0, 44)},
            {"idx": 3, "offset": 133, "length": 49, "trim": (0, 30)},
            {"idx": 4, "offset": 163, "length": 49, "trim": (0, 49)}
        ],
        "chunk0_trim": (0, 45)
    }
}

def log(msg):
    t = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{t} {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(os.path.join(OUT_DIR, "pipeline_execution.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

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

def is_prompt_done(pid):
    try:
        req = urllib.request.Request(f"{COMFY_URL}/history/{pid}")
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            if pid in data:
                status = data[pid].get("status", {})
                return status.get("completed", False) or status.get("status_str") == "success", data[pid].get("outputs", {})
    except Exception:
        pass
    return False, {}

def submit_task_chunks(task_key):
    t_info = TASKS[task_key]
    with open(API_TEMPLATE, "r", encoding="utf-8") as f:
        template = json.load(f)

    submitted = []
    log(f"Submitting chunks for {t_info['title']}...")
    for chk in t_info["chunk_defs"]:
        wf = json.loads(json.dumps(template))
        out_prefix = f"{TODAY_STR}/motion_transfer_full/{task_key}_chk{chk['idx']}"
        
        wf["10"]["inputs"]["image"] = CHAR_IMG
        wf["12"]["inputs"]["file"] = t_info["input_video"]
        wf["22"]["inputs"]["file"] = t_info["pose_rel"]
        wf["24"]["inputs"]["file"] = t_info["face_rel"]
        
        wf["17"]["inputs"]["width"] = 480
        wf["17"]["inputs"]["height"] = 832
        wf["17"]["inputs"]["length"] = chk["length"]
        wf["17"]["inputs"]["video_frame_offset"] = chk["offset"]
        wf["18"]["inputs"]["seed"] = 20261008 + chk["idx"] * 17
        wf["21"]["inputs"]["filename_prefix"] = out_prefix
        
        pid = post_prompt(wf)
        log(f"  -> Chunk {chk['idx']} submitted (offset={chk['offset']}, len={chk['length']}): Prompt ID {pid}")
        submitted.append({
            "chunk_idx": chk["idx"],
            "prompt_id": pid,
            "prefix": out_prefix,
            "trim": chk["trim"]
        })
    return submitted

def trim_video_frames(src_video, start_f, end_f, out_trimmed):
    cap = cv2.VideoCapture(src_video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    tmp_out = out_trimmed + ".tmp.mp4"
    vw = cv2.VideoWriter(tmp_out, fourcc, fps, (w, h))
    
    curr = 0
    written = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if start_f <= curr < end_f:
            vw.write(frame)
            written += 1
        curr += 1
    cap.release()
    vw.release()
    
    # Reencode with x264 for compatibility
    cmd = [
        FFMPEG, "-y",
        "-i", tmp_out,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        out_trimmed
    ]
    subprocess.run(cmd, capture_output=True)
    if os.path.exists(tmp_out):
        os.remove(tmp_out)
    return written

def stitch_task(task_key, job_list):
    t_info = TASKS[task_key]
    log(f"Starting seamless stitching for {t_info['title']}...")
    
    trimmed_parts = []
    # 1. Chunk 0
    c0_src = t_info["chunk0_file"]
    c0_trim_out = os.path.join(OUT_DIR, f"{task_key}_c0_trim.mp4")
    c0_written = trim_video_frames(c0_src, t_info["chunk0_trim"][0], t_info["chunk0_trim"][1], c0_trim_out)
    log(f"  Chunk 0 trimmed: {c0_written} frames -> {c0_trim_out}")
    trimmed_parts.append(c0_trim_out)
    
    # 2. Remaining chunks
    for job in job_list:
        idx = job["chunk_idx"]
        # Find output file
        c_file = None
        for cand in os.listdir(OUT_DIR):
            if cand.startswith(f"{task_key}_chk{idx}") and cand.endswith(".mp4") and "trim" not in cand:
                c_file = os.path.join(OUT_DIR, cand)
                break
        if not c_file:
            log(f"  [ERROR] Output file for chunk {idx} not found in {OUT_DIR}")
            continue
        c_trim_out = os.path.join(OUT_DIR, f"{task_key}_c{idx}_trim.mp4")
        cnt = trim_video_frames(c_file, job["trim"][0], job["trim"][1], c_trim_out)
        log(f"  Chunk {idx} trimmed: {cnt} frames -> {c_trim_out}")
        trimmed_parts.append(c_trim_out)
        
    # Concat
    concat_txt = os.path.join(OUT_DIR, f"{task_key}_concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p in trimmed_parts:
            f.write(f"file '{p}'\n")
            
    final_out = os.path.join(OUT_DIR, f"{task_key}_1to1_full_duration.mp4")
    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
    ]
    if os.path.exists(BGM):
        cmd.extend(["-stream_loop", "-1", "-i", BGM, "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-c:a", "aac", "-b:a", "192k"])
    cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", final_out])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(concat_txt):
        os.remove(concat_txt)
        
    if os.path.exists(final_out):
        cap = cv2.VideoCapture(final_out)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur = tot / fps if fps > 0 else 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        sz = os.path.getsize(final_out) / 1024 / 1024
        log(f"[SUCCESS] {t_info['title']} 1:1 Full Video Created Successfully!")
        log(f"  Path: {final_out}")
        log(f"  Resolution: {w}x{h}, Frames: {tot}, Duration: {dur:.2f}s, Size: {sz:.2f}MB")
        
        # Side-by-Side Comparison
        cmp_out = os.path.join(OUT_DIR, f"{task_key}_full_side_by_side.mp4")
        filter_complex = (
            "[0:v]scale=480:832:force_original_aspect_ratio=decrease,pad=480:832:(ow-iw)/2:(oh-ih)/2[v0];"
            "[1:v]scale=480:832[v1];"
            "[v0][v1]hstack=inputs=2[outv]"
        )
        cmp_cmd = [
            FFMPEG, "-y",
            "-i", t_info["src_video"],
            "-i", final_out,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-t", str(dur),
            "-c:v", "libx264", "-pix_fmt", "yuv420p"
        ]
        if os.path.exists(BGM):
            cmp_cmd.extend(["-stream_loop", "-1", "-i", BGM, "-map", "2:a:0", "-shortest", "-c:a", "aac", "-b:a", "192k"])
        cmp_cmd.append(cmp_out)
        subprocess.run(cmp_cmd, capture_output=True)
        if os.path.exists(cmp_out):
            log(f"[OK] Comparison video created: {cmp_out}")
    else:
        log(f"[ERROR] Concat failed: {res.stderr[:300]}")

def run_orchestrator():
    log("=== Starting Automated Full Duration Pipeline Orchestrator ===")
    
    # 1. Wait for IG14 pose file to be ready
    log("Checking Instagram14 pose file readiness...")
    while not os.path.exists(TASKS["ig14"]["pose_abs"]):
        time.sleep(5)
    log("[OK] Instagram14 full pose video detected!")
    
    # 2. Submit IG14 chunks
    ig14_jobs = submit_task_chunks("ig14")
    
    # 3. Wait for IG18 pose file to be ready
    log("Checking Instagram18 pose file readiness...")
    while not os.path.exists(TASKS["ig18"]["pose_abs"]):
        time.sleep(5)
    log("[OK] Instagram18 full pose video detected!")
    
    # 4. Submit IG18 chunks
    ig18_jobs = submit_task_chunks("ig18")
    
    # 5. Monitor and stitch IG14
    log("Monitoring Instagram14 chunk completion...")
    for job in ig14_jobs:
        pid = job["prompt_id"]
        while True:
            done, _ = is_prompt_done(pid)
            if done:
                log(f"Chunk {job['chunk_idx']} (Prompt {pid}) completed!")
                break
            time.sleep(10)
    stitch_task("ig14", ig14_jobs)
    
    # 6. Monitor and stitch IG18
    log("Monitoring Instagram18 chunk completion...")
    for job in ig18_jobs:
        pid = job["prompt_id"]
        while True:
            done, _ = is_prompt_done(pid)
            if done:
                log(f"Chunk {job['chunk_idx']} (Prompt {pid}) completed!")
                break
            time.sleep(10)
    stitch_task("ig18", ig18_jobs)
    
    log("===============================================================")
    log("[ALL DONE] ALL 1:1 FULL DURATION VIDEOS COMPLETED AND STITCHED!")
    log("===============================================================")

if __name__ == "__main__":
    run_orchestrator()

