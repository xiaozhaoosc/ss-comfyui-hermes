#!/usr/bin/env python3
"""LTX-2.3 正式换装 i2v 批量脚本（16GB GGUF 优化，对齐质量版参数）

复用 OOTD 8 段穿搭提示词（转英文 gemma 风格），首帧锚定参考图。
参数对齐质量验证版：LoRA 0.6 + 40步 + euler_ancestral_cfg_pp + NAG(11/0.25/2.5)

用法: python3 tools/ltx_ootd_8videos.py [start_index] [end_index]
  start_index/end_index 用于分批发（0-7），默认全跑。
"""
import json, urllib.request, uuid, time, sys, glob, os

COMFY = "http://127.0.0.1:8188"
# 人物B 披肩深蓝连衣裙（冒烟测试已用的参考图，放 input/ 根目录）
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

# (name, prompt 主体英文)
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
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP {e.code} 错误响应:")
        print(body[:3000])
        raise

def build(name, body, seed):
    prompt = f"{body} {STYLE}"
    wf = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {
            "unet_name": "PinkCherry_FineTune_Q5_K_M_v18_LTX23.gguf"}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "gemma-3-12b-it-heretic-v2-Q5_K_M.gguf",
            "clip_name2": "ltx-2.3_text_projection_bf16.safetensors",
            "type": "ltxv"}},
        "3": {"class_type": "VAELoader", "inputs": {
            "vae_name": "LTX23_video_vae_bf16.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": REF_B}},
        "5": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0],
            "lora_name": "LTX-2.3\\ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
            "strength_model": 0.6}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 0], "text": prompt}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 0], "text": NEG}},
        "14": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 0],
            "text": "poor anatomy, deformed face, extra fingers, low detail, artifacts"}},
        "6": {"class_type": "LTXVConditioning", "inputs": {
            "positive": ["9", 0], "negative": ["10", 0], "frame_rate": 24.0}},
        "11": {"class_type": "LTXVImgToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["6", 1],
            "vae": ["3", 0], "image": ["4", 0],
            "width": 768, "height": 1280, "length": 121,
            "strength": 1.0, "batch_size": 1}},
        "13": {"class_type": "LTX2_NAG", "inputs": {
            "model": ["5", 0],
            "nag_scale": 11.0, "nag_alpha": 0.25, "nag_tau": 2.5,
            "nag_cond_video": ["14", 0], "inplace": True}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["13", 0],
            "positive": ["11", 0], "negative": ["11", 1],
            "latent_image": ["11", 2],
            "seed": seed, "steps": 24, "cfg": 1.0,
            "sampler_name": "euler_ancestral_cfg_pp",
            "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {
            "samples": ["7", 0], "vae": ["3", 0]}},
        "12": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["8", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": f"LTX23_ootd/{name}",
            "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }
    return wf

def main():
    lo, hi = 0, len(VIDEOS)
    if len(sys.argv) >= 3:
        lo, hi = int(sys.argv[1]), int(sys.argv[2])
    elif len(sys.argv) == 2:
        lo = int(sys.argv[1]); hi = lo + 1

    submitted = []
    for i in range(lo, min(hi, len(VIDEOS))):
        name, body = VIDEOS[i]
        seed = 200 + i
        wf = build(name, body, seed)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        submitted.append({"name": name, "seed": seed, "pid": pid})
        print(f"提交 {i+1}/{len(VIDEOS)}: {name} seed={seed} pid={pid}", flush=True)
        time.sleep(2)

    with open(r"D:/ai_projects/ComfyUI/tools/ltx_ootd_pids.json", "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=1)
    print(f"\n共提交 {len(submitted)} 个任务 -> tools/ltx_ootd_pids.json")

if __name__ == "__main__":
    main()
