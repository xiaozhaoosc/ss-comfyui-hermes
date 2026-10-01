# -*- coding: utf-8 -*-
"""补拍2: 全身正面(街景, 避免海边背影构图) 验证面容一致性 H2"""
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

FULL_STREET = ("A full-body front view of a gorgeous 21-year-old East Asian young woman standing in "
               "the middle of an empty city street at dusk, facing directly at the camera, both feet "
               "on the ground, her face and full body clearly visible. She wears a casual white blouse "
               "and high-waisted blue jeans, holding a small handbag. City lights bokeh in the "
               "background, cinematic, photorealistic.")

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
    fn = f"{BASE_PREFIX}/H2_full_street"
    data = json.dumps({"prompt": wf(TRIG + FULL_STREET, 11006, fn),
                       "client_id": str(client_id)}).encode()
    req = urllib.request.Request(HOST + "/prompt", data=data,
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=20).read())
    pid = r["prompt_id"]
    print(f"queued H2_full_street -> {pid}", flush=True)
    while True:
        hist = json.loads(urllib.request.urlopen(HOST + "/history", timeout=10).read())
        if pid in hist:
            s = hist[pid].get("status", {})
            files = [i.get("filename") for n in hist[pid].get("outputs", {}).values()
                     for i in n.get("images", [])]
            print("OK" if s.get("completed") and files else "FAIL", files or s, flush=True)
            break
        time.sleep(5)

if __name__ == "__main__":
    main()
