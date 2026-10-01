# -*- coding: utf-8 -*-
"""网球裙扭腰舞 - 文生图跨模型对比测试
用相同提示词分别在 6 个图片模型上出图, 固定 seed, 对比效果差异。
"""
import json, time, urllib.request, os

HOST = "http://127.0.0.1:8188"
OUT = "output/2026-09-08/tennis_dance_t2i_test"
os.makedirs(OUT, exist_ok=True)

PROMPT = ("photorealistic medium shot of a young East Asian woman in her early 20s, "
          "captured mid dance pose twisting her waist, confident bright smile, "
          "animated sparkling eyes. Deep brown long hair tied in a high ponytail "
          "with a few soft face-framing strands. Fresh light makeup emphasizing "
          "the eye contour and rosy lips. Outfit: white short-sleeve polo shirt "
          "with thin black piping on collar and cuffs, navy-blue pleated mini skirt, "
          "fresh vibrant campus-girl style. Sunny bright summer daylight, vivid "
          "colorful, blurred soft sunny background, person centered, healthy "
          "glowing skin, high detail. avoid anime, cartoon, 3d render, text, "
          "watermark, deformed hands, extra fingers")

SEED = 12345


def flux_workflow(unet_node, unet_name, prefix, width=768, height=1152):
    """FLUX 现代采样链, 参数化 UNET 加载方式"""
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["11", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"{prefix}", "images": ["8", 0]}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "flux-vae-bf16.safetensors"}},
        "11": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "12": {"class_type": unet_node, "inputs": unet_name},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["25", 0], "guider": ["22", 0], "sampler": ["16", 0],
            "sigmas": ["17", 0], "latent_image": ["27", 0]}},
        "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "17": {"class_type": "BasicScheduler", "inputs": {
            "scheduler": "simple", "steps": 22, "denoise": 1.0, "model": ["12", 0]}},
        "22": {"class_type": "BasicGuider", "inputs": {"model": ["12", 0], "conditioning": ["6", 0]}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": SEED}},
        "27": {"class_type": "EmptySD3LatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1}},
    }


def sd15_workflow(ckpt, prefix, width=512, height=768):
    """SD1.5 标准 KSampler 链"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, deformed", "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
            "latent_image": ["4", 0], "seed": SEED, "steps": 28, "cfg": 7.0,
            "sampler_name": "euler", "scheduler": "karras", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"{prefix}", "images": ["6", 0]}},
    }


PREFIX_BASE = "2026-09-08/tennis_dance_t2i_test"
JOBS = [
    ("flux_fp8", flux_workflow("UNETLoader", {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}, f"{PREFIX_BASE}/t2i_01_flux_fp8")),
    ("flux_abli_q8", flux_workflow("UnetLoaderGGUF", {"unet_name": "T8-flux.1-dev-abliterated-V2-GGUF-Q8_0.gguf"}, f"{PREFIX_BASE}/t2i_02_flux_abli_q8")),
    ("flux_abli_q4", flux_workflow("UnetLoaderGGUF", {"unet_name": "T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M.gguf"}, f"{PREFIX_BASE}/t2i_03_flux_abli_q4")),
    ("sd15_majic", sd15_workflow("majicmixRealistic_v7.safetensors", f"{PREFIX_BASE}/t2i_04_sd15_majic")),
    ("sd15_aom3", sd15_workflow("AOM3A3_orangemixs.safetensors", f"{PREFIX_BASE}/t2i_05_sd15_aom3")),
    ("sd15_counterfeit", sd15_workflow("Counterfeit-V3.0_fp16.safetensors", f"{PREFIX_BASE}/t2i_06_sd15_counterfeit")),
]

# 先清空队列, 避免与残留任务混跑
def enqueue(wf, client):
    data = json.dumps({"prompt": wf, "client_id": client}).encode()
    req = urllib.request.Request(HOST + "/prompt", data=data, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

# 提交
pids = {}
import uuid
for tag, wf in JOBS:
    r = enqueue(wf, str(uuid.uuid4()))
    pids[tag] = r["prompt_id"]
    print(f"queued {tag}: {r['prompt_id']}", flush=True)
    time.sleep(0.3)

with open(os.path.join(OUT, "pids.json"), "w", encoding="utf-8") as f:
    json.dump(pids, f, ensure_ascii=False, indent=2)
print("submitted", len(JOBS), "jobs")