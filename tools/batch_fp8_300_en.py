#!/usr/bin/env python3
"""FP8 写真全量批量（英文提示词版）：6 批 × 50 张 = 300 张

模型: flux1-dev-fp8 + t5xxl_fp8 + clip_l + flux-vae-bf16
参数: 768×1280 × 8步 euler/simple, cfg=1.0, 新 seed
提示词: 50写真批次prompts/en/*_en.json（已修复中文残留）
输出:   output/fp8_50xiezhen_en/batch01_泳装/P01_00001_.png
实测: 每张 ~50-60s（含首次模型加载 ~3min），总计 ~5h

用法:
  python tools/batch_fp8_300_en.py              # 全部 300 张
  python tools/batch_fp8_300_en.py --only 1     # 只跑 batch01
  python tools/batch_fp8_300_en.py --skip 01,02 # 跳过已完成的批次
  python tools/batch_fp8_300_en.py --smoke      # 只提交 batch01 前 3 张（冒烟）
"""
import json, urllib.request, uuid, time, os, sys

BASE = "http://127.0.0.1:8188"
PROMPT_DIR = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\en"
OUT_PREFIX = "fp8_50xiezhen_en"  # output/fp8_50xiezhen_en/batch01_泳装/P01_00001_.png
LOG = r"D:\ai_projects\ComfyUI\tools\fp8_300_en_progress.json"

BATCHES = [
    ("batch01_泳装",        "batch01_泳装_en.json"),
    ("batch02_睡裙",        "batch02_睡裙_en.json"),
    ("batch03_内衣秀",      "batch03_内衣秀_en.json"),
    ("batch04_泳装_skill",  "batch04_泳装_skill_en.json"),
    ("batch05_睡裙_skill",  "batch05_睡裙_skill_en.json"),
    ("batch06_内衣秀_skill","batch06_内衣秀_skill_en.json"),
]

def post(path, payload):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())

def build(pos, neg, seed, prefix):
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
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": prefix}},
    }

def load_progress():
    if os.path.exists(LOG):
        return json.load(open(LOG, encoding='utf-8'))
    return {"submitted": [], "failed": []}

def save_progress(prog):
    json.dump(prog, open(LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def main():
    args = sys.argv[1:]
    only = None
    skip = []
    smoke = "--smoke" in args
    if "--only" in args:
        only = int(args[args.index("--only") + 1])
    if "--skip" in args:
        skip = args[args.index("--skip") + 1].split(",")

    prog = load_progress()
    done_keys = set(prog["submitted"])
    base_seed = int(time.time()) % 1000000  # 新 seed 基准（每次运行不同，避免和旧图撞 seed）

    total_submitted = 0
    for b_idx, (bname, fn) in enumerate(BATCHES, 1):
        if only and b_idx != only: continue
        if f"{b_idx:02d}" in skip: continue
        data = json.load(open(os.path.join(PROMPT_DIR, fn), encoding='utf-8'))
        limit = 3 if smoke else len(data)
        for p in data[:limit]:
            key = f"{bname}_P{p['id']:02d}"
            if key in done_keys:
                continue
            seed = base_seed + b_idx * 1000 + p['id']  # 新 seed
            prefix = f"{OUT_PREFIX}/{bname}/P{p['id']:02d}"
            wf = build(p["positive"], p["negative"], seed, prefix)
            try:
                r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
                prog["submitted"].append(key)
                total_submitted += 1
                print(f"✓ {key} seed={seed}", flush=True)
            except Exception as e:
                prog["failed"].append({"key": key, "err": str(e)})
                print(f"✗ {key} 失败: {e}", flush=True)
            time.sleep(0.2)
            if total_submitted % 50 == 0:
                save_progress(prog)
                print(f"--- 已提交 {total_submitted} 张，写入进度 ---", flush=True)
    save_progress(prog)
    print(f"\n=== 完成，共提交 {total_submitted} 张（累计 {len(prog['submitted'])} 张） ===")

if __name__ == '__main__':
    main()
