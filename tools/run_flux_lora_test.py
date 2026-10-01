# -*- coding: utf-8 -*-
"""FLUX LoRA 测试任务执行器
顺序提交并监控生成状态
"""
import os
import json
import time
import urllib.request
import uuid

HOST = "http://127.0.0.1:8188"
OUT_BASE = "d:/ai_projects/ComfyUI/output/2026-09-08/flux_lora_test"
os.makedirs(OUT_BASE, exist_ok=True)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.test_flux_lora import build_workflow, PROMPT_ZH, PROMPT_EN

def enqueue(wf):
    client_id = str(uuid.uuid4())
    data = json.dumps({"prompt": wf, "client_id": client_id}).encode('utf-8')
    req = urllib.request.Request(f"{HOST}/prompt", data=data, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return resp["prompt_id"]

def wait_for_prompt(prompt_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        req = urllib.request.Request(f"{HOST}/history/{prompt_id}")
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if prompt_id in resp:
            hist = resp[prompt_id]
            outputs = hist.get("outputs", {})
            images = []
            for node_id, out in outputs.items():
                if "images" in out:
                    for img in out["images"]:
                        images.append(img["filename"])
            return True, images
        time.sleep(3)
    return False, []

def run_job(tag, lora_name, lora_strength, prompt_text, seed=42, steps=25):
    prefix = f"2026-09-08/flux_lora_test/{tag}"
    wf = build_workflow(
        lora_name=lora_name,
        lora_strength=lora_strength,
        prompt_text=prompt_text,
        prefix=prefix,
        seed=seed,
        steps=steps
    )
    print(f"[{tag}] Submitting job (LoRA: {lora_name}, seed: {seed}, steps: {steps})...", flush=True)
    t0 = time.time()
    pid = enqueue(wf)
    print(f"[{tag}] Queued with prompt_id: {pid}", flush=True)
    success, images = wait_for_prompt(pid, timeout=300)
    dur = time.time() - t0
    if success:
        print(f"[{tag}] SUCCESS in {dur:.1f}s! Generated: {images}", flush=True)
        return {"tag": tag, "lora": lora_name, "images": images, "duration": dur, "success": True}
    else:
        print(f"[{tag}] TIMEOUT or FAILED after {dur:.1f}s", flush=True)
        return {"tag": tag, "lora": lora_name, "images": [], "duration": dur, "success": False}

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "batch1"
    
    if mode == "batch1":
        # 第一批：基线(无LoRA) vs 旗舰东亚LoRA(hinaFluxDevAsianMix_v12)
        jobs = [
            ("01_baseline_no_lora", None, 0.0, PROMPT_ZH),
            ("02_hina_dev_asianmix_v12_s09", "hinaFluxDevAsianMix_v12.safetensors", 0.9, PROMPT_ZH),
        ]
    elif mode == "batch2":
        # 第二批：Krea AsianMix 与 英文对照
        jobs = [
            ("03_hina_krea_asianmix_v195_s09", "hinaFluxKreaAsianMix_v195.safetensors", 0.9, PROMPT_ZH),
            ("04_flux_ppango_s085", "flux-ppango.safetensors", 0.85, "ppango, " + PROMPT_ZH),
            ("05_hina_dev_asianmix_v12_en_s09", "hinaFluxDevAsianMix_v12.safetensors", 0.9, PROMPT_EN),
        ]
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    results = []
    for tag, lora, strength, prompt in jobs:
        res = run_job(tag, lora, strength, prompt)
        results.append(res)
    
    print("\n=== Batch Summary ===")
    for r in results:
        print(json.dumps(r, ensure_ascii=False))
