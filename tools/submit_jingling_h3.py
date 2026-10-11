#!/usr/bin/env python3
"""华丽精灵造型 - H3 图生视频 (10s, C02 全身参考). 一次性任务提交脚本."""
import json, urllib.request, uuid, time, os

BASE = "http://127.0.0.1:8188"
PROMPT = (
    "A beautiful young East Asian woman with the same face and figure as the reference image, "
    "gorgeous elfin warrior look blending classical oriental fantasy. Long straight glossy black "
    "hair flowing and swaying naturally with her movement. She wears a golden strapless bodice "
    "with an emerald-green gemstone pendant inlaid at the chest, metallic pauldron armor on the "
    "shoulders, golden arm rings on her arms, yellow tassel ornaments tied at the wrists, and a "
    "flowing red long dress with exquisite floral embroidery on the skirt. Red lips, bright "
    "confident lively eyes, a charming playful smile throughout. She tilts her body slightly, "
    "moving both hands gently and rhythmically in front of her chest to the beat, head swaying "
    "subtly to the music, confident flirtatious micro-expressions. Dreamy magical forest palace "
    "background with soft golden-pink glow and floating light particles. Background music is an "
    "upbeat energetic EDM dance track sung by a bright female voice, fast strong rhythm, "
    "passionate unrestrained atmosphere., real photography, ultra high detail, cinematic "
    "lighting, saturated colors, shallow depth of field, high-class fantasy fashion showcase, "
    "glossy skin, no AI artifacts, no deformed hands, no extra limbs, clean composition"
)

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())

wf = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax", "device": "default"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"shift_video": 12.0, "shift_audio": 3.0, "model": ["1", 0]}},
    "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
        "prompt": PROMPT, "width": 736, "height": 1088, "length": 241,
        "clip": ["2", 0], "vae": ["3", 0], "first_frame": ["9", 0]}},
    "6": {"class_type": "KSampler", "inputs": {
        "seed": 20260905, "steps": 28, "cfg": 1.0, "sampler_name": "euler",
        "scheduler": "simple", "denoise": 1.0,
        "model": ["4", 0], "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["5", 1]}},
    "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
    "8": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["6", 0], "vae": ["10", 0]}},
    "9": {"class_type": "LoadImage", "inputs": {"image": "gemini_ken1/C02_PADDED.png"}},
    "10": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "11": {"class_type": "VHS_VideoCombine", "inputs": {
        "frame_rate": 24.0, "loop_count": 0, "filename_prefix": "jingling_v1/seg1",
        "format": "video/h264-mp4", "pix_fmt": "yuv420p10le", "crf": 19,
        "save_metadata": True, "trim_to_audio": False, "pingpong": False, "save_output": True,
        "images": ["7", 0], "audio": ["8", 0]}},
}
r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print("prompt_id =", pid)
with open(r"D:\ai_projects\ComfyUI\tools\jingling_pid.txt", "w") as f:
    f.write(pid or "")
