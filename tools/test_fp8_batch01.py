#!/usr/bin/env python3
"""生成了D:\\obsidian\\obsidian\\ComfyUI\\50写真批次prompts 内 batch01_泳装.json 的前10个图片

固定工作流（已验证成功）：
 flux1-dev-fp8 (UNet, weight_dtype=fp8_e4m3fn) + t5xxl_fp8_e4m3fn + clip_l (DualCLIPLoaderGGUF) + flux-vae-bf16 → EmptyLatent 768×1280 → KSampler 8步/euler/simple → VAEDecode → SaveImage

输出到：D:\\ai_projects\\ComfyUI\\out\\Fp8_test_batch01/

用法:
  python3 tools/test_fp8_batch01.py  生成全部 10 张
  python3 tools/test_fp8_batch01.py 1 3   # 只生成第 1~3 张 (0-based)
"""
import json, urllib.request, uuid, os, sys, time
import re

BASE = "http://127.0.0.1:8188"
PROMPT_DIR = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts"
OUT_DIR = r"D:\ai_projects\ComfyUI\out\Fp8_test_batch01"
BATCH_JSON = "batch01_泳装.json"
SEED_BASE = 6001  # 和之前测试一样，保持同 seed 可对比

# 先确认模型落位，没写错再提交
def check_models():
    r = json.loads(urllib.request.urlopen(f"{BASE}/object_info", timeout=10).read())
    unet_list = r.get("UNETLoader", {}).get("input", {}).get("required", {}).get("unet_name", [[]])[0]
    if not any("flux1-dev-fp8" in n for n in unet_list):
        print("❌ flux1-dev-fp8.safetensors 不在 UNETLoader 可选列表")
        return False
    print(f"✓ 可用模型 {len(unet_list)} 个: {unet_list}")
    return True

def build(pos, neg, seed, tag):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux-vae-bf16.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": pos}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": neg}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1280, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0],
            "seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": f"p8_test_batch01/{tag}"}},
    }

def post(path, payload):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def main():
    if not check_models():
        sys.exit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    # 读 batch01_泳装 前 10 条
    with open(os.path.join(PROMPT_DIR, BATCH_JSON), encoding="utf-8") as f:
        prompts = json.load(f)
    n = 10
    print(f"从 {BATCH_JSON} 读 {len(prompts)} 条，只取前 {n} 条")

    ran = 0
    for i, p in enumerate(prompts[:n]):
        if len(sys.argv) > 2:
            lo, hi = int(sys.argv[1]), int(sys.argv[2]) + 1
            if i < lo or i >= hi: continue
        tag = f"p{i+1:02d}"  # p01, p02 ...
        fp = f"{OUT_DIR}/{tag}"
        if os.path.exists(fp + "_00001_.png"):
            print(f"  → {tag} 已存在，跳过")
            continue
        seed = SEED_BASE + p["id"]
        wf = build(p["positive"], p["negative"], seed, tag)
        try:
            r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
            pid = r.get("prompt_id")
            print(f"✓ {tag} seed={seed} pid={pid[:10]}...")
            ran += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"✗ {tag} 提交失败: {e}")
    print(f"\n已提交 {ran}/{n} 张到 {OUT_DIR}")

if __name__ == "__main__":
    main()
