import json, time, urllib.request

COMFY = "http://127.0.0.1:8188"

# 首帧=造型A(蓝色瑜伽背心)  尾帧=造型B(黑T+黑皮靴)  同为 gemini 人物
FIRST = "ootd/face/gemini/Gemini_Generated_Image_69pomz69pomz69po.png"
LAST  = "ootd/face/gemini/Gemini_Generated_Image_t1o16zt1o16zt1o1.png"

PROMPT = (
    "一位年轻亚洲女性，深棕色长发披肩，鹅蛋脸，大眼高鼻，白皙皮肤，苗条匀称身材。"
    "竖屏全身镜头，简洁室内背景，柔和光。她起初穿蓝色瑜伽背心配高腰紧身裤站立，"
    "随后优雅转身，服装逐渐变换为黑色短袖T恤、黑色紧身裤和黑色皮靴，完成换装转场。"
    "动作流畅连贯，表情微笑自信，时尚换装展示，高清细节，电影质感。"
)

WF = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
    "12": {"class_type": "LoadImage", "inputs": {"image": FIRST}},
    "13": {"class_type": "LoadImage", "inputs": {"image": LAST}},
    "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
        "clip": ["2", 0], "vae": ["3", 0], "prompt": PROMPT,
        "width": 672, "height": 1152, "length": 124,
        "first_frame": ["12", 0], "last_frame": ["13", 0]}},
    "7": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": 42, "steps": 20, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["6", 0],
        "latent_image": ["6", 1], "denoise": 1.0}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
    "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": "ootd_swap/seg01"}},
    "11": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["8", 0], "frame_rate": 24.0, "loop_count": 0,
        "filename_prefix": "ootd_swap/seg01", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
}

def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

r = post(f"{COMFY}/prompt", {"prompt": WF})
pid = r.get("prompt_id")
print("SUBMITTED prompt_id=", pid, flush=True)
