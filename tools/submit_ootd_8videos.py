#!/usr/bin/env python3
"""OOTD 8 个正式视频生成：first_frame 单图锚定形象，提示词描述多套换装。
- 人物A(丸子头)=gpt/left.png  人物B(披肩)=gemini/1bh3ie(深蓝连衣裙)
- 672x1152 竖屏, length=192(≈8s), steps=20, cfg=1.0
- 发型描述统一跟随 first_frame（A丸子头/B披肩），避免发型冲突漂移
"""
import json, urllib.request, uuid, time

COMFY = "http://127.0.0.1:8188"
REF_A = "ootd/face/gpt/left.png"                       # 人物A 丸子头
REF_B = "ootd/face/gemini/Gemini_Generated_Image_1bh3ie1bh3ie1bh3.png"  # 人物B 披肩 深蓝连衣裙

STYLE = (
    "时尚穿搭OOTD展示，动作流畅连贯，表情自然自信，柔和室内光，"
    "高清细节，电影质感，皮肤真实，避免脸部变形、手指异常、文字乱码、卡通感。"
)

# (name, first_frame, 发型描述, prompt 主体)
VIDEOS = [
    ("v01_御姐显瘦", REF_A, "黑色长发扎丸子头",
     "她站在白色雕花木门前、浅色木地板上，先穿黑色吊带花卉连衣裙优雅转身，"
     "随后换白色露肩长裙单手叉腰微笑，再换黑色亮片短裙手轻抚胸口，目光直视镜头，表情温柔自信。"),
    ("v02_甜韩显嫩", REF_B, "黑色长发披肩",
     "她站在白色雕花门+木地板背景前，换穿多套甜美系穿搭：粉色连衣裙、粉色吊带裙、"
     "黑白水手服、白色短袖配灰色百褶裙。动作有双手举起掌心朝外、比耶、手放胸前闭眼甜笑，表情甜美可爱。"),
    ("v03_御姐舞蹈", REF_A, "黑色长发扎丸子头",
     "她佩戴珍珠发饰红唇妆容，穿白色短袖配黑色百褶裙随音乐轻轻舞蹈闭眼享受，"
     "再换棕色连衣裙配金色腰带旋转裙摆扬起，最后换粉色上衣配白色短裙展开双臂开心微笑，动作灵动自信有魅力。"),
    ("v04_夏日御姐", REF_A, "黑色长发扎丸子头",
     "她换穿夏日显瘦裙装：粉色吊带蓬蓬裙、米色褶皱吊带裙、深蓝连衣裙配白衬衫、黑色无袖裙配黑高跟。"
     "动作单手叉腰、展开双臂、右手握拳，表情自信微笑眼神坚定。"),
    ("v05_纯欲显瘦", REF_B, "黑色长发披肩",
     "她佩戴珍珠耳环与银项链红唇，换穿白色蕾丝露肩裙、白色连衣裙、粉色连衣裙、黑色无袖裙。"
     "动作展开双手掌心向上、双手交叉胸前、轻抬左手，表情自然优雅纯欲气质。"),
    ("v06_纯欲御姐舞蹈", REF_B, "黑色长发披肩",
     "她戴耳环，穿黑色吊带花卉裙闭眼微笑起舞，再换白色连衣裙、浅色抹胸渐变裙、灰色无袖紧身裙，"
     "双手抬起或胸前比心，表情开心愉悦。"),
    ("v07_梨型显瘦", REF_A, "黑色长发扎丸子头",
     "她换穿衬衫短裙组合：黑上衣配深蓝短裙、白衬衫配黄短裙、粉衬衫配白短裙黑高跟、米色衬衫配绿短裙。"
     "动作自然站立、挥手、双手比心，表情微笑自信干练。"),
    ("v08_甜韩显嫩", REF_B, "黑色长发披肩",
     "她佩戴珍珠项链与耳环，换穿甜韩系穿搭：白色露肩上衣配粉裙、粉色荷叶边短上衣配白色A字裙肉色高跟、"
     "灰衬衫配黑裙金色腰带、白衬衫配黑短裙。动作双手举起掌心向上展示上半身，表情微笑清新可爱。"),
]

def build(name, ref, hair, body, seed):
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

submitted = []
for i, (name, ref, hair, body) in enumerate(VIDEOS):
    seed = 100 + i
    wf = build(name, ref, hair, body, seed)
    try:
        r = post(f"{COMFY}/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        submitted.append({"name": name, "seed": seed, "pid": pid})
        print(f"已提交 {name} (seed={seed}) -> {pid}", flush=True)
    except Exception as e:
        print(f"提交失败 {name}: {e}", flush=True)
    time.sleep(1)

print(f"\n=== 共提交 {len(submitted)}/8 ===", flush=True)
with open("workflows/v1/ootd_v1_pids.json", "w", encoding="utf-8") as f:
    json.dump(submitted, f, ensure_ascii=False, indent=2)
print("prompt_ids 已存 workflows/v1/ootd_v1_pids.json", flush=True)
