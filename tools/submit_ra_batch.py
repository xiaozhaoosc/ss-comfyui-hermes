#!/usr/bin/env python3
"""
提交阮胺 30 个视频换脸任务到 ComfyUI 队列。
人脸源: face_swap_source.png
"""
import json, urllib.request, uuid, os, sys, shutil

URL = "http://127.0.0.1:8188"
FACE = "face_swap_source.png"
INPUT_DIR = r"D:\ai_projects\ComfyUI\input"
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\Ms_阮胺_faceswap"

def get_status():
    try:
        q = json.loads(urllib.request.urlopen(f"{URL}/queue", timeout=5).read())
        h = json.loads(urllib.request.urlopen(f"{URL}/history", timeout=5).read())
        return len(q.get("queue_running",[])), len(q.get("queue_pending",[])), len(h)
    except:
        return -1, -1, -1

def wf(video, prefix):
    return {
        '1': {'class_type': 'LoadVideo', 'inputs': {'file': video}},
        '2': {'class_type': 'GetVideoComponents', 'inputs': {'video': ['1', 0]}},
        '3': {'class_type': 'LoadImage', 'inputs': {'image': FACE}},
        '4': {'class_type': 'ReActorFaceSwap', 'inputs': {
            'enabled': True, 'input_image': ['2', 0], 'source_image': ['3', 0],
            'swap_model': 'inswapper_128.onnx', 'facedetection': 'retinaface_resnet50',
            'face_restore_model': 'GFPGANv1.4.pth', 'face_restore_visibility': 1.0,
            'codeformer_weight': 0.5, 'detect_gender_input': 'no',
            'detect_gender_source': 'no', 'input_faces_index': '0',
            'source_faces_index': '0', 'console_log_level': 1
        }},
        '5': {'class_type': 'CreateVideo', 'inputs': {'images': ['4', 0], 'audio': ['2', 1], 'fps': 30.0}},
        '6': {'class_type': 'SaveVideo', 'inputs': {'video': ['5', 0], 'filename_prefix': prefix, 'format': 'mp4', 'codec': 'h264'}}
    }

running, pending, completed = get_status()
if running < 0:
    print("⚠️ ComfyUI not responding")
    sys.exit(1)

# Check if 阮胺 batch already submitted
h = json.loads(urllib.request.urlopen(f"{URL}/history", timeout=5).read())
ra_count = sum(1 for info in h.values() for out in info.get('outputs',{}).values() for img in out.get('images',[]) if img.get('filename','').startswith('ra_'))

if ra_count > 0:
    if running == 0 and pending == 0:
        print(f"✅ 阮胺 batch COMPLETE! {ra_count} tasks finished")
    else:
        print(f"⏳ 阮胺 in progress: {ra_count} done, {running} running, {pending} pending")
    sys.exit(0)

if running > 0 or pending > 0:
    print(f"⏳ 队列中有其他任务: {running}R/{pending}P, {completed} total completed")
    print("先提交到队列等待...")

# Submit 阮胺 batch
videos_dir = os.path.join(INPUT_DIR, "阮胺")
if not os.path.exists(videos_dir):
    print(f"ERROR: 阮胺目录不存在: {videos_dir}")
    sys.exit(1)

videos = sorted([f for f in os.listdir(videos_dir) if f.endswith(('.mp4','.avi'))])
print(f"🚀 提交 {len(videos)} 个阮胺视频到 ComfyUI...")

os.makedirs(OUTPUT_DIR, exist_ok=True)

ok = 0
for i, vname in enumerate(videos):
    clean = f"ra_swap{i+1:02d}.mp4"
    src = os.path.join(videos_dir, vname)
    dst = os.path.join(INPUT_DIR, clean)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    prefix = f"ra_faceswap{i+1:02d}"
    w = wf(clean, prefix)
    payload = json.dumps({'prompt': w, 'client_id': str(uuid.uuid4())}).encode()
    req = urllib.request.Request(f'{URL}/prompt', data=payload, headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        r = json.loads(resp.read())
        ok += 1
        print(f"  OK [{i+1}/{len(videos)}]: {vname[:40]}")
    except Exception as e:
        print(f"  FAIL [{i+1}/{len(videos)}]: {vname[:40]} -> {e}")

print(f"\n✅ 已提交 {ok}/{len(videos)} 个阮胺视频到 ComfyUI 队列")
