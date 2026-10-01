#!/usr/bin/env python3
"""6批次×50张=300张 写真批量提交器 - 使用真实 nuyoah skill 方法论

读取 D:/obsidian/obsidian/ComfyUI/50写真批次prompts/batchXX_*.json
用 front=true 插队提交，每张 ~55s（8步 euler_simple，768×1280）

用法:
  python3 tools/submit_batches_50xiezhen.py [batch_id] [--front]
    batch_id 1-6，默认全部 6 批
"""
import json, urllib.request, uuid, time, sys, os

COMFY = "http://127.0.0.1:8188"
PROMPT_DIR = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts"

BATCHES = [
    (1, "泳装", False),
    (2, "睡裙", False),
    (3, "内衣秀", False),
    (4, "泳装", True),
    (5, "睡裙", True),
    (6, "内衣秀", True),
]

def load_prompts(batch_id, outfit_key, use_skill):
    """加载 batch 提示词"""
    if use_skill:
        # batch 4-6: 优先 _skill_v2，fallback _skill
        for suffix in ["_skill_v2", "_skill"]:
            p = os.path.join(PROMPT_DIR, f"batch{batch_id:02d}_{outfit_key}{suffix}.json")
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
        raise FileNotFoundError(f"no skill file for batch {batch_id}")
    else:
        # batch 1-3: 直接命名
        p = os.path.join(PROMPT_DIR, f"batch{batch_id:02d}_{outfit_key}.json")
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)

def build_workflow(pos, neg, seed, filename_prefix):
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {
            "unet_name": "T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M.gguf"}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors",
            "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {
            "vae_name": "flux-vae-bf16.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 0], "text": pos}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 0], "text": neg}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {
            "width": 768, "height": 1280, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["6", 0],
            "seed": seed, "steps": 8, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {
            "samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {
            "images": ["8", 0], "filename_prefix": filename_prefix}},
    }

def post(path, payload):
    req = urllib.request.Request(
        f"{COMFY}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def submit_batch(batch_id, outfit_key, use_skill, use_front=False):
    prompts = load_prompts(batch_id, outfit_key, use_skill)
    suffix = "skill" if use_skill else "basic"
    folder = f"50xiezhen_batch{batch_id:02d}_{outfit_key}_{suffix}"

    # 防重复：输出目录已有 ≥50 PNG 则跳过
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", folder)
    if os.path.isdir(outdir):
        n = len([f for f in os.listdir(outdir) if f.lower().endswith(".png")])
        if n >= 50:
            print(f">>> Batch {batch_id:02d} ({folder}): 输出已有 {n} 张，SKIP 防重复")
            return []

    print(f"\n>>> Batch {batch_id:02d} ({outfit_key}, skill={use_skill}): {len(prompts)} prompts")
    submitted = []
    for p in prompts:
        seed = batch_id * 1000 + p["id"]  # 独立 seed 空间
        fp = f"{folder}/P{p['id']:02d}"
        wf = build_workflow(p["positive"], p["negative"], seed, fp)
        payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
        if use_front:
            payload["front"] = True
        r = post("/prompt", payload)
        pid = r.get("prompt_id")
        submitted.append({"batch": batch_id, "id": p["id"], "seed": seed, "pid": pid})
        if p["id"] % 10 == 0:
            print(f"  ✓ {p['id']}/{len(prompts)} (pid={pid[:8]}...)", flush=True)
        time.sleep(0.3)  # 防 aggressive
    return submitted

def main():
    args = sys.argv[1:]
    use_front = "--front" in args
    batch_ids = [int(a) for a in args if a.isdigit() and 1 <= int(a) <= 6]
    if not batch_ids:
        batch_ids = [1, 2, 3, 4, 5, 6]  # 默认全部

    all_submitted = []
    for bid in batch_ids:
        # 找到 batch 配置
        cfg = next((b for b in BATCHES if b[0] == bid), None)
        if not cfg:
            print(f"WARN: batch {bid} not configured, skip")
            continue
        _, outfit_key, use_skill = cfg
        try:
            sub = submit_batch(bid, outfit_key, use_skill, use_front)
            all_submitted.extend(sub)
        except Exception as e:
            print(f"ERROR batch {bid}: {e}")

    # 保存记录
    out_log = r"D:\ai_projects\ComfyUI\tools\batches_submitted.json"
    with open(out_log, "w", encoding="utf-8") as f:
        json.dump(all_submitted, f, ensure_ascii=False, indent=1)
    print(f"\n=== 共提交 {len(all_submitted)} 张，记录到 {out_log} ===")

if __name__ == "__main__":
    main()
