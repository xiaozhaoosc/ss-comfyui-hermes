#!/usr/bin/env python3
"""OOTD v04 单段诊断提交（ComfyUI 两次崩在 v04，隔离测试）"""
import json, urllib.request, uuid

COMFY = "http://127.0.0.1:8188"
REF_A = "ootd/face/gpt/left.png"

STYLE = ("时尚穿搭OOTD展示，动作流畅连贯，表情自然自信，柔和室内光，"
         "高清细节，电影质感，皮肤真实，避免脸部变形、手指异常、文字乱码、卡通感。")
BODY = ("她换穿夏日显瘦裙装：粉色吊带蓬蓬裙、米色褶皱吊带裙、深蓝连衣裙配白衬衫、黑色无袖裙配黑高跟。"
        "动作单手叉腰、展开双臂、右手握拳，表情自信微笑眼神坚定。")
PROMPT = f"一位年轻亚洲女性，黑色长发扎丸子头，鹅蛋脸，大眼高鼻，白皙皮肤，苗条匀称身材。竖屏全身镜头，{BODY} {STYLE}"

WF = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
    "12": {"class_type": "LoadImage", "inputs": {"image": REF_A}},
    "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": PROMPT,
        "width": 672, "height": 1152, "length": 192, "first_frame": ["12", 0]}},
    "7": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": 103, "steps": 20, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["6", 0],
        "latent_image": ["6", 1], "denoise": 1.0}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
    "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": "ootd_v1/v04_夏日御姐"}},
    "11": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["8", 0], "frame_rate": 24.0, "loop_count": 0,
        "filename_prefix": "ootd_v1/v04_夏日御姐", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
}

req = urllib.request.Request(f"{COMFY}/prompt", data=json.dumps({"prompt": WF, "client_id": str(uuid.uuid4())}).encode(),
    headers={"Content-Type": "application/json"})
r = json.loads(urllib.request.urlopen(req, timeout=30).read())
pid = r.get("prompt_id")
print("v04 诊断单段已提交 ->", pid, flush=True)
with open("workflows/v1/v04_diag_pid.txt", "w") as f:
    f.write(pid)
