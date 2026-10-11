# -*- coding: utf-8 -*-
"""自炼 LoRA 验收验证图: my_flux_lora_v1
维度:
  A/B/C/D  face 场景同种子 -> 触发词有效性 (LoRA± × 触发词±)
  E/F      half/full 场景 + LoRA + 触发词 -> 面容一致性
输出: output/2026-09-10/lora_verify/<tag>/
"""
import json, time, urllib.request, uuid

HOST = "http://127.0.0.1:8188"
UNET = "flux1-dev-fp8.safetensors"
UNET_NODE = "UNETLoader"
STEPS = 24
GUIDANCE = 3.5
W, H = 1024, 1024
BASE_PREFIX = "2026-09-10/lora_verify"
LORA = "my_flux_lora_v1.safetensors"
LS = 1.0

FACE = ("A close-up beauty portrait of a gorgeous 21-year-old East Asian young woman, "
        "natural double eyelids, gentle almond-shaped dark brown eyes, soft high bridge nose, "
        "delicate jawline, healthy radiant skin with subtle natural texture. Soft neutral daylight "
        "illuminating her face from a nearby window, gentle catchlights in her eyes, calm expression, "
        "straight dark hair. 85mm f/1.8, sharp focus, creamy bokeh, photorealistic.")
HALF = ("A medium shot of a gorgeous 21-year-old East Asian young woman sitting at a rustic wooden "
        "cafe table, wearing an oversized beige cashmere knit sweater. Holding a warm ceramic coffee "
        "mug, gazing out a rain-streaked window. Warm cafe lights, cinematic bokeh, 50mm f/1.4, photorealistic.")
FULL = ("A full-body long shot of a gorgeous 21-year-old East Asian woman walking barefoot along the "
        "wet shoreline at twilight. Holding sandals in one hand, wearing a flowing terracotta maxi "
        "dress in the ocean breeze. Wet sand reflecting the orange and purple twilight sky, cinematic, photorealistic.")
TRIG = "ohwx woman, "

# (tag, scene_prompt, use_lora, use_trig, seed)
JOBS = [
    ("A_lora_trig",  FACE, True,  True,  5000),   # 自炼LoRA + 触发词
    ("B_lora_notrig",FACE, True,  False, 5000),   # 自炼LoRA 无触发词 -> 触发词有效性
    ("C_nolora_trig",FACE, False, True,  5000),   # 底模 + 触发词 -> 触发词在底模是否天然有效
    ("D_nolora_base",FACE, False, False, 5000),   # 底模基线
    ("E_half_consis", HALF, True,  True,  6001),  # 半身 -> 面容一致性
    ("F_full_consis", FULL, True,  True,  7002),  # 全身 -> 面容一致性
]

def wf(prompt, seed, use_lora, fn_prefix):
    nodes = {
        "2": {"class_type": UNET_NODE, "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "4": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux"}},
    }
    model_ref, clip_ref = ("2", 0), ("4", 0)
    if use_lora:
        nodes["3"] = {"class_type": "LoraLoader", "inputs": {
            "model": ["2", 0], "clip": ["4", 0], "lora_name": LORA,
            "strength_model": LS, "strength_clip": LS}}
        model_ref, clip_ref = ("3", 0), ("3", 1)
    nodes["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_ref}}
    nodes["F"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["6", 0], "guidance": GUIDANCE}}
    nodes["22"] = {"class_type": "BasicGuider", "inputs": {"model": model_ref, "conditioning": ["F", 0]}}
    nodes["8"] = {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["10", 0]}}
    nodes["9"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": fn_prefix, "images": ["8", 0]}}
    nodes["10"] = {"class_type": "VAELoader", "inputs": {"vae_name": "flux-vae-bf16.safetensors"}}
    nodes["13"] = {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": ["25", 0], "guider": ["22", 0], "sampler": ["16", 0],
        "sigmas": ["17", 0], "latent_image": ["27", 0]}}
    nodes["16"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
    nodes["17"] = {"class_type": "BasicScheduler", "inputs": {
        "scheduler": "simple", "steps": STEPS, "denoise": 1.0, "model": ["2", 0]}}
    nodes["25"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}}
    nodes["27"] = {"class_type": "EmptySD3LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}}
    return nodes

def main():
    client_id = str(uuid.uuid4())
    jobs = []
    for tag, scene, use_lora, use_trig, seed in JOBS:
        prompt = (TRIG + scene) if use_trig else scene
        fn = f"{BASE_PREFIX}/{tag}"
        data = json.dumps({"prompt": wf(prompt, seed, use_lora, fn),
                           "client_id": str(client_id)}).encode()
        req = urllib.request.Request(HOST + "/prompt", data=data,
                                     headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
        jobs.append((tag, r["prompt_id"]))
        print(f"queued {tag} lora={use_lora} trig={use_trig} seed={seed}", flush=True)
        time.sleep(0.3)
    print("submitted", len(jobs), "verify jobs", flush=True)

    done = {p: False for _, p in jobs}
    failed = 0
    while not all(done.values()):
        try:
            hist = json.loads(urllib.request.urlopen(HOST + "/history", timeout=10).read())
        except Exception:
            time.sleep(5); continue
        for tag, pid in jobs:
            if done[pid]:
                continue
            if pid in hist:
                done[pid] = True
                s = hist[pid].get("status", {})
                files = [i.get("filename") for n in hist[pid].get("outputs", {}).values()
                         for i in n.get("images", [])]
                if s.get("completed") and files:
                    print(f"OK {tag} -> {files}", flush=True)
                else:
                    failed += 1
                    print(f"FAIL {tag} status={s}", flush=True)
        time.sleep(5)
    print("=== DONE === total:", len(jobs), "failed:", failed, flush=True)

if __name__ == "__main__":
    main()
