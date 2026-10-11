# -*- coding: utf-8 -*-
"""补拍: 正面半身/全身, 验证跨角度面容一致性 (G/H)"""
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
TRIG = "ohwx woman, "

HALF_FRONT = ("A medium shot of a gorgeous 21-year-old East Asian young woman facing the camera "
              "at a rustic wooden cafe table, wearing an oversized beige cashmere knit sweater. "
              "She looks directly at the viewer, holding a warm ceramic coffee mug with both hands. "
              "Warm cafe lights, cinematic bokeh, 50mm f/1.4, photorealistic.")
FULL_FRONT = ("A full-body long shot of a gorgeous 21-year-old East Asian woman standing facing the "
              "camera on the wet shoreline at twilight, her face clearly visible. She holds sandals "
              "in one hand, wearing a flowing terracotta maxi dress in the ocean breeze. Wet sand "
              "reflecting the orange and purple twilight sky, cinematic, photorealistic.")

JOBS = [
    ("G_half_front", HALF_FRONT, 8003),
    ("H_full_front", FULL_FRONT, 9004),
]

def wf(prompt, seed, fn_prefix):
    return {
        "2": {"class_type": UNET_NODE, "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "4": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3": {"class_type": "LoraLoader", "inputs": {
            "model": ["2", 0], "clip": ["4", 0], "lora_name": LORA,
            "strength_model": LS, "strength_clip": LS}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 1]}},
        "F": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["6", 0], "guidance": GUIDANCE}},
        "22": {"class_type": "BasicGuider", "inputs": {"model": ["3", 0], "conditioning": ["F", 0]}},
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
    for tag, scene, seed in JOBS:
        fn = f"{BASE_PREFIX}/{tag}"
        data = json.dumps({"prompt": wf(TRIG + scene, seed, fn),
                           "client_id": str(client_id)}).encode()
        req = urllib.request.Request(HOST + "/prompt", data=data,
                                     headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
        jobs.append((tag, r["prompt_id"]))
        print(f"queued {tag} seed={seed}", flush=True)
        time.sleep(0.3)
    print("submitted", len(jobs), "verify2 jobs", flush=True)

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
