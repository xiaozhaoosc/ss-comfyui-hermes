# -*- coding: utf-8 -*-
"""FLUX 文生图 v2 迭代: 强化 photorealistic + 严格东亚脸 + waist-up + steps 40
重跑 3 个 FLUX (fp8 / abli Q8 / abli Q4)。
"""
import json, time, urllib.request, uuid

HOST = "http://127.0.0.1:8188"
PREFIX = "2026-09-08/tennis_dance_t2i_test/v2"

PROMPT = ("photorealistic portrait of a beautiful young Chinese East Asian woman "
          "in her early 20s, clearly Chinese/Japanese-Korean facial features, thin "
          "almond dark eyes, fair porcelain skin, delicate small jaw, deep brown "
          "hair in a high ponytail with a few soft face-framing strands, fresh light "
          "makeup emphasizing the eye contour and rosy lips. Waist-up medium shot, "
          "standing in a graceful slightly twisting waist dance pose, one hand "
          "raised, confident bright smile. Outfit: white short-sleeve polo shirt "
          "with thin black piping on the collar and cuffs, navy-blue pleated mini "
          "skirt. Sunny bright summer daylight, vivid color, blurred soft campus "
          "background, person centered, healthy glowing skin, highly detailed, "
          "DSLR 85mm portrait, sharp focus. avoid anime, cartoon, 3d render, text, "
          "watermark, deformed hands, extra limbs, extra fingers, bad anatomy")

SEED = 12345
STEPS = 40
W, H = 768, 1152


def flux_workflow(unet_node, unet_name, prefix, width=W, height=H):
    return {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["11", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
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
            "scheduler": "simple", "steps": STEPS, "denoise": 1.0, "model": ["12", 0]}},
        "22": {"class_type": "BasicGuider", "inputs": {"model": ["12", 0], "conditioning": ["6", 0]}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": SEED}},
        "27": {"class_type": "EmptySD3LatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1}},
    }


JOBS = [
    ("v2_fp8", flux_workflow("UNETLoader", {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}, f"{PREFIX}/t2i_v2_fp8")),
    ("v2_abli_q8", flux_workflow("UnetLoaderGGUF", {"unet_name": "T8-flux.1-dev-abliterated-V2-GGUF-Q8_0.gguf"}, f"{PREFIX}/t2i_v2_abli_q8")),
    ("v2_abli_q4", flux_workflow("UnetLoaderGGUF", {"unet_name": "T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M.gguf"}, f"{PREFIX}/t2i_v2_abli_q4")),
]

for tag, wf in JOBS:
    data = json.dumps({"prompt": wf, "client_id": str(uuid.uuid4())}).encode()
    req = urllib.request.Request(HOST + "/prompt", data=data, headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=15).read())
    print("queued", tag, r["prompt_id"], flush=True)
    time.sleep(0.3)
print("submitted", len(JOBS), "FLUX v2 jobs")