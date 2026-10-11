#!/usr/bin/env python3
"""50张写真批量提交器 - FLUX 流水线（用 front=true 插队）

读取 D:/obsidian/obsidian/ComfyUI/50张写真准备/50shooting_plan.md 中的 positive/negative prompts，
逐张提交到 ComfyUI /prompt（插队模式 front=true），输出到 output/50xiezhen/

用法:
  python3 tools/submit_50xiezhen.py [start_idx] [end_idx] [--front]
    默认全部 50 张，--front=True 插队到 LTX 当前队列最前
"""
import json, urllib.request, uuid, time, sys, re, os

COMFY = "http://127.0.0.1:8188"
PLAN_MD = r"D:\obsidian\obsidian\ComfyUI\50张写真准备\50shooting_plan.md"

# 加载 50 段提示词
def load_prompts(md_path):
    """从 markdown 提取每张写真的 positive 和 negative"""
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()
    # P01..P50 分段，每张包含 ``` (positive) ``` (negative) ```
    # 锚定 ### Pxx 条目
    samples = []
    # 匹配 `### P(数字)` 到下一个 `###` 或文末
    blocks = re.split(r'\n### P(\d+)', text)
    # blocks[0] = header, 后接 (num, content) 交替
    for i in range(1, len(blocks) - 1, 2):
        pid = int(blocks[i])
        body = blocks[i + 1]
        # 提取 positive
        pos_match = re.search(r'\*\*Positive Prompt\*\*：\s*```\s*\n(.*?)\n```', body, re.DOTALL)
        neg_match = re.search(r'\*\*Negative Prompt\*\*：\s*```\s*\n(.*?)\n```', body, re.DOTALL)
        if pos_match and neg_match:
            samples.append({
                "id": pid,
                "positive": pos_match.group(1).strip(),
                "negative": neg_match.group(1).strip(),
            })
    return samples[:50]  # 限制50

def build_workflow(sample, seed):
    """基于 flux_smoke_workflow 模板构造一个完整 prompt dict"""
    # 输出 filename 用 sample id
    fid = f"50xiezhen/P{sample['id']:02d}"
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
            "clip": ["2", 0],
            "text": sample["positive"]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {
            "clip": ["2", 0],
            "text": sample["negative"]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {
            "width": 768, "height": 1280, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0],
            "positive": ["4", 0],
            "negative": ["5", 0],
            "latent_image": ["6", 0],
            "seed": seed,
            "steps": 8,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {
            "samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {
            "images": ["8", 0], "filename_prefix": fid}},
    }

def post(path, payload):
    req = urllib.request.Request(
        f"{COMFY}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

def main():
    args = sys.argv[1:]
    use_front = "--front" in args
    lo = 0; hi = 50
    # 过滤非 flag 数字参数
    nums = [a for a in args if not a.startswith("--")]
    if len(nums) >= 2:
        lo, hi = int(nums[0]), int(nums[1])
    elif len(nums) == 1:
        lo = int(nums[0]); hi = lo + 1

    samples = load_prompts(PLAN_MD)
    print(f"加载到 {len(samples)} 个样本 prompt")

    # 限制范围
    samples = samples[lo:hi]
    print(f"提交范围 [{lo}:{hi}) = {len(samples)} 张, front={use_front}")

    submitted = []
    for s in samples:
        seed = 1000 + s["id"]  # 50 写真独立 seed 区间
        wf = build_workflow(s, seed)
        payload = {
            "prompt": wf,
            "client_id": str(uuid.uuid4()),
        }
        if use_front:
            payload["front"] = True
        r = post("/prompt", payload)
        pid = r.get("prompt_id")
        submitted.append({"id": s["id"], "seed": seed, "pid": pid, "front": use_front})
        print(f"  ✓ P{s['id']:02d} seed={seed} pid={pid[:13]}... front={use_front}", flush=True)
        time.sleep(0.5)  # 防 aggressive

    out_file = r"D:\ai_projects\ComfyUI\tools\50xiezhen_pids.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(submitted, f, ensure_ascii=False, indent=1)
    print(f"\n共提交 {len(submitted)} 张 -> {out_file}")

if __name__ == "__main__":
    main()
