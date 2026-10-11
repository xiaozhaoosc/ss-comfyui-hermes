# -*- coding: utf-8 -*-
"""Q6_K 底模 + 多 LoRA 网格对照: 同一批代表性场景/种子, 仅更换 LoRA, 观察不同人像 LoRA 的效果差异。
输出: output/2026-09-08/asian_lora_diff/<scene>/<lora_tag>/
"""
import json, sys, time, urllib.request, uuid

HOST = "http://127.0.0.1:8188"
UNET = "T8-flux.1-dev-abliterated-V2-GGUF-Q6_K.gguf"
UNET_NODE = "UnetLoaderGGUF"
STEPS = 24
GUIDANCE = 3.5
W, H = 1024, 1024
BASE_PREFIX = "2026-09-08/asian_lora_diff"

# (name, prompt) 挑 3 类代表性景别: 面部特写 / 半身 / 全身
SCENES = [
    ("face", "01", "A close-up beauty portrait of a gorgeous 21-year-old East Asian young woman, natural double eyelids, gentle almond-shaped dark brown eyes, soft high bridge nose, delicate jawline, healthy radiant skin with subtle natural texture. Soft neutral daylight illuminating her face from a nearby window, gentle catchlights in her eyes, calm expression, straight dark hair. 85mm f/1.8, sharp focus, creamy bokeh, photorealistic."),
    ("half", "08", "A medium shot of a gorgeous 21-year-old East Asian young woman sitting at a rustic wooden cafe table, wearing an oversized beige cashmere knit sweater. Holding a warm ceramic coffee mug, gazing out a rain-streaked window. Warm cafe lights, cinematic bokeh, 50mm f/1.4, photorealistic."),
    ("full", "22", "A full-body long shot of a gorgeous 21-year-old East Asian woman walking barefoot along the wet shoreline at twilight. Holding sandals in one hand, wearing a flowing terracotta maxi dress in the ocean breeze. Wet sand reflecting the orange and purple twilight sky, cinematic, photorealistic."),
]

LORAS = [
    ("hinaDevAsianMix_v12", "hinaFluxDevAsianMix_v12.safetensors"),
    ("hinaKreaAsianMix_v195", "hinaFluxKreaAsianMix_v195.safetensors"),
    ("hinaKreaAsianMix_v19", "hinaFluxKreaAsianMix_v19-rev2.safetensors"),
    ("ppango", "flux-ppango.safetensors"),
    ("ThaiShorty_F1D", "Thai_shorty_F1D.safetensors"),
]

SEED_BASE = 5000
LS = 0.75

def wf(prompt, seed, lora, fn_prefix):
    return {
        "2": {"class_type": UNET_NODE, "inputs": {"unet_name": UNET}},
        "4": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3": {"class_type": "LoraLoader", "inputs": {
            "model": ["2", 0], "clip": ["4", 0], "lora_name": lora,
            "strength_model": LS, "strength_clip": LS}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 1]}},
        "F": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["6", 0], "guidance": GUIDANCE}},
        "22": {"class_type": "BasicGuider", "inputs": {"model": ["2", 0], "conditioning": ["F", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["10", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": fn_prefix, "images": ["8", 0]}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": "flux-vae-bf16.safetensors"}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["25", 0], "guider": ["22", 0], "sampler": ["16", 0],
            "sigmas": ["17", 0], "latent_image": ["27", 0]}},
        "16": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "17": {"class_type": "BasicScheduler", "inputs": {
            "scheduler": "simple", "steps": STEPS, "denoise": 1.0, "model": ["2", 0]}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "27": {"class_type": "EmptySD3LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
    }

def main():
    client_id = str(uuid.uuid4())
    jobs = []
    for si, (scene, num, prompt) in enumerate(SCENES):
        for li, (tag, lora) in enumerate(LORAS):
            seed = SEED_BASE + si  # 同 scene 内所有 LoRA 同种子, 隔离变量只剩 LoRA
            fn = f"{BASE_PREFIX}/{scene}/{tag}"
            data = json.dumps({"prompt": wf(prompt, seed, lora, fn),
                               "client_id": str(client_id)}).encode()
            req = urllib.request.Request(HOST + "/prompt", data=data,
                                         headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=20).read())
            jobs.append((scene, tag, r["prompt_id"]))
            print(f"queued {scene}/{tag}", flush=True)
            time.sleep(0.3)
    print("submitted", len(jobs), "lora-diff jobs", flush=True)

    done = {p: False for _, _, p in jobs}
    failed = 0
    while not all(done.values()):
        try:
            hist = json.loads(urllib.request.urlopen(HOST + "/history", timeout=10).read())
        except Exception as e:
            time.sleep(5); continue
        for scene, tag, pid in jobs:
            if done[pid]:
                continue
            if pid in hist:
                done[pid] = True
                s = hist[pid].get("status", {})
                files = [i.get("filename") for n in hist[pid].get("outputs", {}).values()
                         for i in n.get("images", [])]
                if s.get("completed") and files:
                    print(f"OK {scene}/{tag} -> {files}", flush=True)
                else:
                    failed += 1
                    print(f"FAIL {scene}/{tag} status={s}", flush=True)
        time.sleep(5)
    print("=== DONE === total:", len(jobs), "failed:", failed, flush=True)

if __name__ == "__main__":
    main()