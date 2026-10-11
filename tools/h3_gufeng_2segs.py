#!/usr/bin/env python3
"""古风紫裙女子跳舞视频 - H3 2段衔接生成（960×544，每段5.17s = 10.3s 视频）

段1: 庭院全景 + 女子起舞（t2v）
段2: 女子舞动细节 + 手势变化（i2v, first_frame=段1末帧）

用法:
  python tools/h3_gufeng_2segs.py              # 提交2段
  python tools/h3_gufeng_2segs.py --720p        # 1280×720 单段试跑（OOM风险）
"""
import json, urllib.request, uuid, time, sys, os

BASE = "http://127.0.0.1:8188"
OUT_PREFIX = "gufeng_2segs"

STYLE_SUFFIX = (", real photography, ultra high detail, cinematic lighting, "
                "soft natural light, saturated colors, shallow depth of field, "
                "film grain, no AI artifacts, no deformed hands, no extra limbs")

# 段1：庭院全景 + 女子起舞
SEG1 = ("A young East Asian woman with a delicate face and sweet smile, "
        "twin braided hair, ornate hair accessories and earrings, fresh makeup. "
        "Wearing a purple strapless tight-fitting short dress with golden brocade "
        "embroidery, matching belt at the waist, a sheer light purple long-sleeved "
        "gauze robe draped over her shoulders, black lace-trimmed thigh-high socks. "
        "She is gracefully dancing, elegant flowing movements, hands making graceful "
        "gestures, body swaying to the rhythm. "
        "Classical Chinese courtyard interior, wooden lattice windows, traditional "
        "eaves, blooming purple wisteria flowers, dreamy atmosphere. "
        "Medium shot, fixed camera, soft bright lighting, high color saturation") + STYLE_SUFFIX

# 段2：舞动细节 + 手势特写（i2v 衔接）
SEG2 = ("Close-up medium shot, the same young East Asian woman with twin braids "
        "continuing to dance, wearing purple brocade dress with gauze robe, "
        "her hands flowing through elegant gestures, turning gracefully, "
        "fabric and sleeves flowing with the movement, smiling sweetly. "
        "Classical Chinese courtyard with wisteria flowers in background, "
        "soft bright light, high saturation, dreamy atmosphere") + STYLE_SUFFIX

NEG = "blurry, low quality, deformed, cartoon, anime style, extra fingers, extra limbs, watermark, text"

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
        raise

def build_seg1(width, height, length):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": SEG1,
            "width": width, "height": height, "length": length}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "seed": 20260830, "steps": 28, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["5", 1], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["7", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": f"{OUT_PREFIX}/seg1", "format": "video/h264-mp4",
            "pingpong": False, "save_output": True}},
    }

def build_seg2(first_frame_path, width, height, length):
    """seg2 带 first_frame 衔接"""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "9": {"class_type": "LoadImage", "inputs": {"image": first_frame_path}},
        "5": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "prompt": SEG2,
            "width": width, "height": height, "length": length,
            "first_frame": ["9", 0]}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "seed": 20260831, "steps": 28, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["5", 1], "denoise": 1.0}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["7", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": f"{OUT_PREFIX}/seg2", "format": "video/h264-mp4",
            "pingpong": False, "save_output": True}},
    }

def find_first_frame():
    """找 seg1 生成的最后一帧 PNG（ComfyUI VHS 会输出末帧PNG）"""
    d = r"D:\ai_projects\ComfyUI\output\gufeng_2segs"
    if not os.path.exists(d): return None
    pngs = sorted([f for f in os.listdir(d) if f.startswith('seg1') and f.endswith('.png')])
    if not pngs: return None
    return pngs[-1]

def main():
    use_720 = "--720p" in sys.argv
    if use_720:
        w, h, length = 1280, 720, 124
        print(f"⚠️ 720P 试跑: {w}×{h}×{length}帧（16GB 显存可能 OOM）")
        # 单段 t2v
        wf = build_seg1(w, h, length)
        wf["8"]["inputs"]["filename_prefix"] = "gufeng_720p/seg1"
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        print(f"✓ 720P 单段已提交 pid={r.get('prompt_id')[:13]}")
        return

    # 960×544 2段
    print("古风紫裙 2 段衔接（960×544×28步，每段5.17s → 10.3s 视频）")
    # 段1 先跑
    wf1 = build_seg1(960, 544, 124)
    r1 = post("/prompt", {"prompt": wf1, "client_id": str(uuid.uuid4())})
    pid1 = r1.get('prompt_id')
    print(f"✓ seg1 已提交 pid={pid1[:13]} (~10min)")
    # 保存 pid 供监控
    with open(r"D:\ai_projects\ComfyUI\tools\h3_gufeng_pids.json", "w") as f:
        json.dump({"seg1_pid": pid1}, f)

if __name__ == '__main__':
    main()
