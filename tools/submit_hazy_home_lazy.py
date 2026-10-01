#!/usr/bin/env python3
"""提交「慵懒居家长裙」100 提示词 × 3 张 = 300 张写真

用法:
  python tools/submit_hazy_home_lazy.py              # 全部 300 张（每词3张，X=Y/Z）
  python tools/submit_hazy_home_lazy.py --only 1-20  # 只跑 1-20 号提示词
  python tools/submit_hazy_home_lazy.py --smoke      # 只提交 P01-P03 × 3 张（冒烟）

产物:
  output/fp8_hazy_lazy/batch01/P001_v1_00001_.png 等
档案:
  archive_hazy_home_lazy.jsonl  (JSON Lines: prompt_id, prompt_text, output_files, seed, submit_time, workflow)
  archive_hazy_home_lazy.md     (人类可读: 表格 提示词<->图片路径<->评分占位)
进度:
  tools/hazy_lazy_progress.json
"""
import json, urllib.request, uuid, time, os, sys, datetime

BASE = "http://127.0.0.1:8188"
PROMPT_DIR = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\en"
PROMPT_FILE = os.path.join(PROMPT_DIR, "hazy_home_lazy_100_en.json")
OUT_PREFIX = "fp8_hazy_lazy"
PROGRESS_LOG = r"D:\ai_projects\ComfyUI\tools\hazy_lazy_progress.json"
ARCHIVE_JSONL = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\archive_hazy_home_lazy.jsonl"
ARCHIVE_MD = r"D:\obsidian\obsidian\ComfyUI\50写真批次prompts\archive_hazy_home_lazy.md"
PICS_PER_PROMPT = 3  # 每提示词3张变体

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
    return json.load(open(PROGRESS_LOG, encoding='utf-8')) if os.path.exists(PROGRESS_LOG) else {"submitted": [], "failed": []}

def save_progress(prog):
    json.dump(prog, open(PROGRESS_LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def archive_md_write(records):
    lines = [
        "# 慵懒居家长裙 100×3 批次档案",
        f"- 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 模型: flux1-dev-fp8 @ 768×1280, 8 steps euler/simple, cfg=1.0",
        f"- 每提示词 {PICS_PER_PROMPT} 张（同 seed 前缀不同后缀）",
        f"- 提示词文件: {PROMPT_FILE}",
        "",
        "| ID | 提示词摘要 | 图片路径 | Seed | 评分 | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for r in records:
        pos_short = r['positive'][:80].replace('|','｜').replace('\n',' ') + "..."
        files = " | ".join(r['files'])
        lines.append(f"| P{r['id']:03d} | {pos_short} | {files} | {r['seed']} | __/10 | |")
    os.makedirs(os.path.dirname(ARCHIVE_MD), exist_ok=True)
    with open(ARCHIVE_MD, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

def main():
    args = sys.argv[1:]
    only = None
    if "--only" in args:
        rng = args[args.index("--only") + 1]
        lo, hi = rng.split("-")
        only = set(range(int(lo), int(hi) + 1))
    smoke = "--smoke" in args

    data = json.load(open(PROMPT_FILE, encoding='utf-8'))
    prog = load_progress()
    submitted_keys = set(prog["submitted"])
    base_seed = int(time.time()) % 1000000

    records = []
    submitted_count = 0
    for idx, p in enumerate(data, 1):
        if only and idx not in only:
            continue
        if smoke and idx > 3:
            break
        key_base = f"{OUT_PREFIX}_P{idx:03d}"
        # 跳过全部已提交的（防断点续提交）
        done_variants = [v for v in range(1, PICS_PER_PROMPT+1) if f"{key_base}_v{v}" in submitted_keys]
        if len(done_variants) == PICS_PER_PROMPT:
            continue
        files = []
        for v in range(1, PICS_PER_PROMPT+1):
            key = f"{key_base}_v{v}"
            if key in submitted_keys:
                continue
            seed = base_seed + idx * 10 + v
            prefix = f"{OUT_PREFIX}/P{idx:03d}_v{v}"
            wf = build(p["positive"], p["negative"], seed, prefix)
            try:
                r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
                pid = r.get("prompt_id", "unknown")
                prog["submitted"].append(key)
                submitted_count += 1
                files.append(f"{OUT_PREFIX}/P{idx:03d}_v{v}_00001_.png")
                print(f"✓ {key} seed={seed} pid={pid[:8]}", flush=True)
            except Exception as e:
                prog["failed"].append({"key": key, "err": str(e)})
                print(f"✗ {key} 失败: {e}", flush=True)
            time.sleep(0.2)
        # 记录档案
        records.append({"id": idx, "positive": p["positive"], "negative": p["negative"],
                        "seed": base_seed + idx * 10, "files": files,
                        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        if submitted_count % 50 == 0:
            save_progress(prog)
            print(f"--- 已提交 {submitted_count} 张 ---", flush=True)
    save_progress(prog)
    # 追加 jsonl 档案
    if records:
        os.makedirs(os.path.dirname(ARCHIVE_JSONL), exist_ok=True)
        with open(ARCHIVE_JSONL, 'a', encoding='utf-8') as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\n档案已追加 {len(records)} 条 → {ARCHIVE_JSONL}")
        # 生成 MD 汇总版（完整 reload 全部 jsonl 追加为表格）
        all_recs = []
        if os.path.exists(ARCHIVE_JSONL):
            with open(ARCHIVE_JSONL, encoding='utf-8') as f:
                for line in f:
                    try: all_recs.append(json.loads(line))
                    except: pass
        archive_md_write(all_recs)
        print(f"MD 汇总已更新 → {ARCHIVE_MD}")
    print(f"\n=== 完成，共提交 {submitted_count} 张（累计 {len(prog['submitted'])} 张） ===")

if __name__ == '__main__':
    main()
