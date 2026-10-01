#!/usr/bin/env python3
"""LTX-2.3 优化批量：512×896×12步 = 实测 5min/段，8段 ≈ 40min

基于测速结果（speedtest_times.json, 2026-08-30）：
  B_512x896_s12: 5.03 min/段，画质合格，速度达标

用法: python3 tools/ltx_ootd_8videos_optimized.py [start_index] [end_index]
  默认全部 8 段。也可分段跑：0 2 = 只跑前2段
"""
import json, urllib.request, uuid, time, sys, os

COMFY = "http://127.0.0.1:8188"

# ---------- 优化参数（实测验证） ----------
WIDTH = 512        # 原为 768
HEIGHT = 896       # 原为 1280 → 竖版 1080p 宽高比
STEPS = 12         # 原为 24
NAG_SCALE = 6.0    # 原为 11.0（NAG 降低换速度）
LORA_STRENGTH = 0.6
SEED_BASE = 20260830

REF_B = "Gemini_Generated_Image_1bh3ie1bh3ie1bh3.png"

STYLE = (
    "Style: realistic, cinematic. A young Asian woman with an oval face, "
    "large eyes, high nose bridge, fair skin, slim figure, straight black hair "
    "worn down to the shoulders. Full-body vertical shot on a balcony with "
    "classical stone railing, warm indoor-outdoor lighting, smooth natural "
    "movements, photorealistic skin detail, high quality."
)

NEG = (
    "blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, "
    "compression artifacts, jpeg artifacts, glitches, watermark, text, logo, "
    "poor anatomy, deformed face, extra fingers, extra limbs, cartoon style, "
    "sudden clothing change, identity change, scene jump, camera shake"
)

NAG_NEG = "poor anatomy, deformed face, extra fingers, low detail, artifacts"

# 8 段穿搭视频
VIDEOS = [
    ("ltx_v01_御姐显瘦",
     "She stands at a white carved wooden door on light wooden flooring. "
     "She wears a black floral sleeveless dress and turns gracefully, "
     "then changes into a white off-shoulder long dress and smiles with one hand on her hip, "
     "then changes into a black sequin short dress, touching her chest gently, "
     "looking at the camera with a warm confident expression."),
    ("ltx_v02_甜韩显嫩",
     "She stands before a white carved door with wooden flooring, changing through cute outfits: "
     "a pink dress, a pink sleeveless dress, a black-and-white sailor uniform, "
     "a white short-sleeve top with a gray pleated skirt. "
     "She raises both hands with palms out, makes a peace sign, and smiles sweetly with eyes closed."),
    ("ltx_v03_御姐舞蹈",
     "She wears a pearl hair accessory and red lip makeup, dancing gently to music in a "
     "white short-sleeve top with a black pleated skirt, eyes closed enjoying the moment, "
     "then changes into a brown dress with a golden belt, spinning so the skirt lifts, "
     "finally changing into a pink top with a white short skirt, opening her arms with a happy smile."),
    ("ltx_v04_夏日御姐",
     "She changes through summer slim outfits: a pink sleeveless puff dress, a beige pleated "
     "sleeveless dress, a navy dress with a white shirt, a black sleeveless dress with black heels. "
     "She poses with one hand on her hip, arms spread, right fist raised, confident smile with firm gaze."),
    ("ltx_v05_纯欲显瘦",
     "She wears pearl earrings, a silver necklace and red lips, changing through: a white lace "
     "off-shoulder dress, a white dress, a pink dress, a black sleeveless dress. "
     "She spreads her arms with palms up, crosses her arms over her chest, and lifts her left hand, "
     "natural elegant pure charm."),
    ("ltx_v06_纯欲御姐舞蹈",
     "She wears earrings, dancing in a black floral sleeveless dress with eyes closed and a smile, "
     "then changes into a white dress, a light gradient strapless dress, and a gray sleeveless fitted dress, "
     "raising her hands or making a heart sign with her fingers, happy and joyful."),
    ("ltx_v07_梨型显瘦",
     "She changes through shirt-and-skirt outfits: a black top with navy shorts, a white shirt with "
     "a yellow skirt, a pink shirt with a white skirt and black heels, a beige shirt with a green skirt. "
     "She stands naturally, waves, and makes a heart with both hands, smiling with confident composure."),
    ("ltx_v08_甜韩显嫩",
     "She wears a pearl necklace and earrings, changing through sweet Korean looks: a white "
     "off-shoulder top with a pink skirt, a pink ruffle top with a white A-line skirt and nude heels, "
     "a gray shirt with a black skirt and gold belt, a white shirt with a black short skirt. "
     "She raises both hands with palms up to show the outfit, smiling fresh and lovely."),
]

def post(path, payload):
    req = urllib.request.Request(f"{COMFY}{path}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP {e.code} 错误: {body[:2000]}")
        raise

def build(name, prompt_body, seed):
    prompt = f"{prompt_body} {STYLE}"
    return {
        # 主模型：PinkCherry Q5_K_M（稳定版）
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {
            "unet_name": "PinkCherry_FineTune_Q5_K_M_v18_LTX23.gguf"}},
        # 文本编码器：gemma GGUF + 投影层
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "gemma-3-12b-it-heretic-v2-Q5_K_M.gguf",
            "clip_name2": "ltx-2.3_text_projection_bf16.safetensors", "type": "ltxv"}},
        # VAE
        "3": {"class_type": "VAELoader", "inputs": {
            "vae_name": "LTX23_video_vae_bf16.safetensors"}},
        # 首帧参考图
        "4": {"class_type": "LoadImage", "inputs": {"image": REF_B}},
        # LoRA 增强
        "5": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0],
            "lora_name": "LTX-2.3\\ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
            "strength_model": LORA_STRENGTH}},
        # 正向提示词
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": NEG}},
        "14": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": NAG_NEG}},
        # LTX 条件化
        "6": {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["9", 0], "negative": ["10", 0], "frame_rate": 24.0}},
        # i2v 锚定
        "11": {"class_type": "LTXVImgToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["6", 1],
            "vae": ["3", 0], "image": ["4", 0],
            "width": WIDTH, "height": HEIGHT, "length": 121,
            "strength": 1.0, "batch_size": 1}},
        # NAG 增强
        "13": {"class_type": "LTX2_NAG", "inputs": {
            "model": ["5", 0],
            "nag_scale": NAG_SCALE, "nag_alpha": 0.25, "nag_tau": 2.5,
            "nag_cond_video": ["14", 0], "nag_cond_audio": ["14", 0], "inplace": True}},
        # 采样器
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["13", 0], "positive": ["11", 0], "negative": ["11", 1],
            "latent_image": ["11", 2], "seed": seed, "steps": STEPS, "cfg": 1.0,
            "sampler_name": "euler_ancestral_cfg_pp", "scheduler": "simple", "denoise": 1.0}},
        # VAE 解码
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        # 视频合并
        "12": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["8", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": f"LTX23_ootd_optimized/{name}",
            "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }

def free_gpu():
    """释放 VRAM（等 FLUX 模型卸载完成）"""
    try:
        q = json.loads(urllib.request.urlopen(f"{COMFY}/queue", timeout=8).read())
        run = q.get('queue_running', [])
        if run:
            print("⚠️ ComfyUI 仍在运行中，请等待当前任务完成")
            return False
    except:
        pass
    # attempt free
    try:
        post("/free", {"unload_models": True, "free_memory": True})
        print("✅ 已请求释放 VRAM")
    except Exception as e:
        print(f"⚠️ free 请求失败: {e}，继续尝试提交")
    import time; time.sleep(2)
    return True

def main():
    args = sys.argv[1:]
    lo, hi = 0, 8
    if len(args) >= 2:
        lo, hi = int(args[0]), int(args[1])
    elif len(args) == 1:
        lo = int(args[0]); hi = lo + 1

    print(f"LTX 优化批量: 第 {lo}~{hi} 段 (共 {hi-lo} 段)")
    print(f"参数: {WIDTH}×{HEIGHT} × {STEPS}步, NAG={NAG_SCALE}, LoRA={LORA_STRENGTH}")

    os.makedirs(r"D:\ai_projects\ComfyUI\output\LTX23_ootd_optimized", exist_ok=True)

    # 先释放 VRAM
    free_gpu()

    submitted = []
    for i in range(lo, hi):
        name, prompt_body = VIDEOS[i]
        seed = SEED_BASE + i
        wf = build(name, prompt_body, seed)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        submitted.append({"idx": i, "name": name, "seed": seed, "pid": pid})
        print(f"✓ [{i}] {name} pid={pid[:13]}...", flush=True)
        time.sleep(0.5)

    # 写入记录
    with open(r"D:\ai_projects\ComfyUI\tools\ltx_ootd_optimized_pids.json", "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=1)
    print(f"\n已提交 {len(submitted)} 段 → output/LTX23_ootd_optimized/")
    print(f"PID 记录 → tools/ltx_ootd_optimized_pids.json")

if __name__ == '__main__':
    main()
