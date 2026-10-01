#!/usr/bin/env python3
"""LTX-2.3 5s 测速对比：2 配置，同 seed 同 prompt，逐段计时

A: 640×1080, 8步,  NAG=6, LoRA 0.6, 121帧
B: 512×896,  12步, NAG=6, LoRA 0.6, 121帧
目标：5s 视频总耗时 ≤ 10 分钟（含模型加载/VAE/合成）
输出: output/LTX23_speedtest/A_*.mp4, B_*.mp4 + 耗时记录 speedtest_times.json
"""
import json, urllib.request, uuid, time, sys, os

COMFY = "http://127.0.0.1:8188"
REF_B = "Gemini_Generated_Image_1bh3ie1bh3ie1bh3.png"
SEED = 20260830
OUT_DIR = r"D:\ai_projects\ComfyUI\output\LTX23_speedtest"
LOG = r"D:\ai_projects\ComfyUI\tools\speedtest_times.json"

PROMPT = (
    "She stands at a white carved wooden door on light wooden flooring. "
    "She wears a black floral sleeveless dress and turns gracefully, "
    "then changes into a white off-shoulder long dress and smiles with one hand on her hip, "
    "looking at the camera with a warm confident expression. "
    + "Style: realistic, cinematic. A young Asian woman with an oval face, large eyes, "
    "high nose bridge, fair skin, slim figure, straight black hair worn down to the shoulders. "
    "Full-body vertical shot, warm lighting, smooth natural movements, photorealistic skin detail, high quality."
)
NEG = ("blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, "
       "compression artifacts, jpeg artifacts, glitches, watermark, text, logo, "
       "poor anatomy, deformed face, extra fingers, extra limbs, cartoon style, "
       "sudden clothing change, identity change, scene jump, camera shake")
NAG_NEG = "poor anatomy, deformed face, extra fingers, low detail, artifacts"

def post(path, payload):
    req = urllib.request.Request(f"{COMFY}{path}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:2000]}")
        raise

def build(name, w, h, steps, nag_scale=6.0):
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "PinkCherry_FineTune_Q5_K_M_v18_LTX23.gguf"}},
        "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
            "clip_name1": "gemma-3-12b-it-heretic-v2-Q5_K_M.gguf",
            "clip_name2": "ltx-2.3_text_projection_bf16.safetensors", "type": "ltxv"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "LTX23_video_vae_bf16.safetensors"}},
        "4": {"class_type": "LoadImage", "inputs": {"image": REF_B}},
        "5": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["1", 0],
            "lora_name": "LTX-2.3\\ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
            "strength_model": 0.6}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": PROMPT}},
        "10": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": NEG}},
        "14": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": NAG_NEG}},
        "6": {"class_type": "LTXVConditioning", "inputs": {"positive": ["9", 0], "negative": ["10", 0], "frame_rate": 24.0}},
        "11": {"class_type": "LTXVImgToVideo", "inputs": {
            "positive": ["6", 0], "negative": ["6", 1], "vae": ["3", 0], "image": ["4", 0],
            "width": w, "height": h, "length": 121, "strength": 1.0, "batch_size": 1}},
        "13": {"class_type": "LTX2_NAG", "inputs": {
            "model": ["5", 0], "nag_scale": nag_scale, "nag_alpha": 0.25, "nag_tau": 2.5,
            "nag_cond_video": ["14", 0], "inplace": True}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["13", 0], "positive": ["11", 0], "negative": ["11", 1],
            "latent_image": ["11", 2], "seed": SEED, "steps": steps, "cfg": 1.0,
            "sampler_name": "euler_ancestral_cfg_pp", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "12": {"class_type": "VHS_VideoCombine", "inputs": {
            "images": ["8", 0], "frame_rate": 24.0, "loop_count": 0,
            "filename_prefix": f"LTX23_speedtest/{name}",
            "format": "video/h264-mp4", "pingpong": False, "save_output": True}},
    }

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    jobs = [
        ("A_640x1088_s8", 640, 1088, 8),
        ("B_512x896_s12", 512, 896, 12),
    ]
    track = {}
    for name, w, h, steps in jobs:
        wf = build(name, w, h, steps)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        track[pid] = {"name": name, "cfg": f"{w}x{h}x{steps}步", "submitted": time.time(),
                      "started": None, "done": None}
        print(f"已提交 {name} ({w}x{h}, {steps}步) pid={pid[:13]}...", flush=True)
        time.sleep(0.5)

    print("\n监控中（每20s轮询，等 2 段都跑完）...", flush=True)
    while True:
        time.sleep(20)
        try:
            q = json.loads(urllib.request.urlopen(f"{COMFY}/queue", timeout=10).read())
            running_pids = {r[1] for r in q.get("queue_running", [])}
            h = json.loads(urllib.request.urlopen(f"{COMFY}/history", timeout=10).read())
            for pid, t in track.items():
                if t["started"] is None and pid in running_pids:
                    t["started"] = time.time()
                    print(f"▶ {t['name']} 开始采样 {time.strftime('%H:%M:%S')}", flush=True)
                if t["done"] is None and pid in h and h[pid].get("status", {}).get("completed"):
                    t["done"] = time.time()
                    elapsed = t["done"] - (t["started"] or t["submitted"])
                    print(f"✅ {t['name']} 完成，总耗时 {elapsed/60:.1f} 分钟", flush=True)
            if all(t["done"] for t in track.values()):
                break
        except Exception as e:
            print(f"查询异常: {e}", flush=True)
            time.sleep(10)

    # 汇总
    results = []
    for pid, t in track.items():
        elapsed = (t["done"] - (t["started"] or t["submitted"])) if t["done"] else None
        results.append({"name": t["name"], "cfg": t["cfg"], "elapsed_min": round(elapsed/60, 2) if elapsed else None,
                        "pid": pid, "started": time.strftime('%H:%M:%S', time.localtime(t["started"])) if t["started"] else None})
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("\n=== 测速结果 ===")
    for r_ in results:
        print(f"{r_['name']}: {r_['cfg']} → {r_['elapsed_min']} 分钟")
    print(f"详细记录 → {LOG}")

if __name__ == "__main__":
    main()
