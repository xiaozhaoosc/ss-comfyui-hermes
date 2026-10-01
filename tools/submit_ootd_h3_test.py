import json, time, urllib.request, sys

COMFY = "http://127.0.0.1:8188"

# 参考图相对 ComfyUI input 目录的路径
REF_IMAGE = "ootd/face/gpt/left.png"   # gpt 丸子头人物，1122x1402 竖构图

PROMPT = (
    "一位年轻亚洲女性，黑色长发扎丸子头，鹅蛋脸，大而有神的眼睛，高挺鼻，"
    "白皙皮肤，苗条纤细身材。竖屏全身镜头，站在白色雕花木门前、浅色木地板上，"
    "柔和室内光。她微笑着从侧身缓缓转身面向镜头，双手自然垂落，随后单手叉腰展示穿搭，"
    "身穿白色短袖T恤配黑色高腰紧身裤。动作流畅优雅，表情温柔自信，"
    "时尚穿搭OOTD展示，高清细节，电影质感。"
)

WF = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
    "12": {"class_type": "LoadImage", "inputs": {"image": REF_IMAGE}},
    "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
        "clip": ["2", 0], "vae": ["3", 0], "prompt": PROMPT,
        "width": 672, "height": 1152, "length": 124, "first_frame": ["12", 0]}},
    "7": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": 42, "steps": 20, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["6", 0],
        "latent_image": ["6", 1], "denoise": 1.0}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
    "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": "ootd_h3/seg01"}},
    "11": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["8", 0], "frame_rate": 24.0, "loop_count": 0,
        "filename_prefix": "ootd_h3/seg01", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
}

def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

r = post(f"{COMFY}/prompt", {"prompt": WF})
pid = r.get("prompt_id")
print("SUBMITTED prompt_id=", pid, flush=True)

# 轮询直到完成
while True:
    try:
        h = post(f"{COMFY}/history/{pid}", {})
    except Exception as e:
        print("poll err", e, flush=True); time.sleep(10); continue
    if pid in h:
        status = h[pid].get("status", {})
        if status.get("completed"):
            print("COMPLETED", flush=True)
            outs = h[pid].get("outputs", {})
            for nid, o in outs.items():
                for kind, items in o.items():
                    if isinstance(items, list):
                        for it in items:
                            print(f"OUTPUT node={nid} {kind}:", it.get("filename") or it.get("name") or it, flush=True)
            break
        if status.get("status_str") == "error":
            print("ERROR:", json.dumps(h[pid], ensure_ascii=False)[:2000], flush=True)
            break
    time.sleep(15)
