#!/usr/bin/env python3
"""续跑 OOTD v04-v08（ComfyUI 崩溃后恢复，seed 与首次提交保持一致）"""
import json, urllib.request, uuid, time

COMFY = "http://127.0.0.1:8188"
REF_A = "ootd/face/gpt/left.png"
REF_B = "ootd/face/gemini/Gemini_Generated_Image_1bh3ie1bh3ie1bh3.png"

STYLE = (
    "时尚穿搭OOTD展示，动作流畅连贯，表情自然自信，柔和室内光，"
    "高清细节，电影质感，皮肤真实，避免脸部变形、手指异常、文字乱码、卡通感。"
)

VIDEOS = [
    ("v04_夏日御姐", REF_A, "黑色长发扎丸子头", 103,
     "她换穿夏日显瘦裙装：粉色吊带蓬蓬裙、米色褶皱吊带裙、深蓝连衣裙配白衬衫、黑色无袖裙配黑高跟。"
     "动作单手叉腰、展开双臂、右手握拳，表情自信微笑眼神坚定。"),
    ("v05_纯欲显瘦", REF_B, "黑色长发披肩", 104,
     "她佩戴珍珠耳环与银项链红唇，换穿白色蕾丝露肩裙、白色连衣裙、粉色连衣裙、黑色无袖裙。"
     "动作展开双手掌心向上、双手交叉胸前、轻抬左手，表情自然优雅纯欲气质。"),
    ("v06_纯欲御姐舞蹈", REF_B, "黑色长发披肩", 105,
     "她戴耳环，穿黑色吊带花卉裙闭眼微笑起舞，再换白色连衣裙、浅色抹胸渐变裙、灰色无袖紧身裙，"
     "双手抬起或胸前比心，表情开心愉悦。"),
    ("v07_梨型显瘦", REF_A, "黑色长发扎丸子头", 106,
     "她换穿衬衫短裙组合：黑上衣配深蓝短裙、白衬衫配黄短裙、粉衬衫配白短裙黑高跟、米色衬衫配绿短裙。"
     "动作自然站立、挥手、双手比心，表情微笑自信干练。"),
    ("v08_甜韩显嫩", REF_B, "黑色长发披肩", 107,
     "她佩戴珍珠项链与耳环，换穿甜韩系穿搭：白色露肩上衣配粉裙、粉色荷叶边短上衣配白色A字裙肉色高跟、"
     "灰衬衫配黑裙金色腰带、白衬衫配黑短裙。动作双手举起掌心向上展示上半身，表情微笑清新可爱。"),
]

def build(name, ref, hair, seed, body):
    prompt = f"一位年轻亚洲女性，{hair}，鹅蛋脸，大眼高鼻，白皙皮肤，苗条匀称身材。竖屏全身镜头，{body} {STYLE}"
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "12": {"class_type": "LoadImage", "inputs": {"image": ref}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": prompt,
            "width": 672, "height": 1152, "length": 192, "first_frame": ["12", 0]}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": seed, "steps": 20, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["6", 0],
            "latent_image": ["6", 1], "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["4", 0]}},
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": f"ootd_v1/{name}"}},
        "11": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["8", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": f"ootd_v1/{name}", "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }

def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def main(start=1):
    submitted = []
    for name, ref, hair, seed, body in VIDEOS[start:]:
        wf = build(name, ref, hair, seed, body)
        try:
            r = post(f"{COMFY}/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
            pid = r.get("prompt_id")
            submitted.append({"name": name, "seed": seed, "pid": pid})
            print(f"已提交 {name} (seed={seed}) -> {pid}", flush=True)
        except Exception as e:
            print(f"提交失败 {name}: {e}", flush=True)
        time.sleep(1)
    print(f"\n=== 共提交 {len(submitted)} 个 ===", flush=True)
    with open("workflows/v1/ootd_v1_resume_pids.json", "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=2)
    print("prompt_ids 已存 workflows/v1/ootd_v1_resume_pids.json", flush=True)

if __name__ == "__main__":
    import sys
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    main(start)
