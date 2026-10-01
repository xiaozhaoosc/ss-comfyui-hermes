#!/usr/bin/env python3
"""LTX-2.3 i2v 质量验证版（16GB GGUF 优化，针对末段脸崩）

与 8 步冒烟版的差异：
  1. 补上遗漏的 distilled LoRA（LTX-2.3/ltx-2.3-22b-distilled-lora-384-1.1, strength 0.6）
  2. KSampler 8步 -> 40步（画质上限）
  3. 采样器 euler_ancestral_cfg_pp（GGUF 最佳，原工作流 KSamplerSelect 用同款）
  4. 原工作流用 LTX2_NAG 防负面引导崩脸 —— 冒烟版没有，补上（strength 0.25）
  5. 负提示词替换为原工作流同款（更专业）

输出: output/LTX23_smoke/LTX23_quality_40s_*.mp4
"""
import json, uuid, urllib.request, time, glob, os

COMFY = "http://127.0.0.1:8188"

def post(path, payload):
    req = urllib.request.Request(f"{COMFY}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"HTTP {e.code} 错误响应:")
        print(body[:3000])
        raise

# ---------- 健康检查 ----------
for ep in ["/queue", "/object_info/LTX2_NAG", "/object_info/LoraLoaderModelOnly"]:
    try:
        urllib.request.urlopen(f"{COMFY}{ep}", timeout=10)
        print(f"  OK {ep}")
    except Exception as e:
        print(f"  FAIL {ep}: {e}")
        raise SystemExit("ComfyUI 未就绪或节点缺失")

wf = {
    # 主模型 GGUF
    "1": {"class_type": "UnetLoaderGGUF", "inputs": {
        "unet_name": "PinkCherry_FineTune_Q5_K_M_v18_LTX23.gguf"}},
    # 文本编码器 Gemma GGUF + text projection
    "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
        "clip_name1": "gemma-3-12b-it-heretic-v2-Q5_K_M.gguf",
        "clip_name2": "ltx-2.3_text_projection_bf16.safetensors",
        "type": "ltxv"}},
    # VAE 视频
    "3": {"class_type": "VAELoader", "inputs": {
        "vae_name": "LTX23_video_vae_bf16.safetensors"}},
    # 首帧参考图
    "4": {"class_type": "LoadImage", "inputs": {
        "image": "Gemini_Generated_Image_1bh3ie1bh3ie1bh3.png"}},
    # LoRA（补上！）
    "5": {"class_type": "LoraLoaderModelOnly", "inputs": {
        "model": ["1", 0],
        "lora_name": "LTX-2.3\\ltx-2.3-22b-distilled-lora-384-1.1.safetensors",
        "strength_model": 0.6}},
    # 正向提示词
    "9": {"class_type": "CLIPTextEncode", "inputs": {
        "clip": ["2", 0],
        "text": "A young Asian woman standing on a stone balcony, smiling gently, long black hair flowing in a soft breeze, golden hour rim light, cinematic depth of field, photorealistic, high detail"}},
    # 负向提示词（原工作流同款）
    "10": {"class_type": "CLIPTextEncode", "inputs": {
        "clip": ["2", 0],
        "text": "blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, poor anatomy, deformed face, extra fingers"}},
    # LTX 条件化
    "6": {"class_type": "LTXVConditioning", "inputs": {
        "positive": ["9", 0], "negative": ["10", 0],
        "frame_rate": 24.0}},
    # i2v
    "11": {"class_type": "LTXVImgToVideo", "inputs": {
        "positive": ["6", 0], "negative": ["6", 1],
        "vae": ["3", 0],
        "image": ["4", 0],
        "width": 768, "height": 1280, "length": 121,
        "strength": 1.0, "batch_size": 1}},
    # NAG 专用负面条件（独立编码，原工作流 383 号同款思路）
    "14": {"class_type": "CLIPTextEncode", "inputs": {
        "clip": ["2", 0],
        "text": "poor anatomy, deformed face, low detail, artifacts"}},
    # LTX2_NAG 负面注意力引导（防脸崩关键，nag_scale=11/nag_alpha=0.25/nag_tau=2.5）
    "13": {"class_type": "LTX2_NAG", "inputs": {
        "model": ["5", 0],
        "nag_scale": 11.0,
        "nag_alpha": 0.25,
        "nag_tau": 2.5,
        "nag_cond_video": ["14", 0],
        "inplace": True}},
    # KSampler 40 步
    "7": {"class_type": "KSampler", "inputs": {
        "model": ["13", 0],
        "positive": ["11", 0],
        "negative": ["11", 1],
        "latent_image": ["11", 2],
        "seed": 42,
        "steps": 40,
        "cfg": 1.0,
        "sampler_name": "euler_ancestral_cfg_pp",
        "scheduler": "simple",
        "denoise": 1.0}},
    # VAE Decode
    "8": {"class_type": "VAEDecode", "inputs": {
        "samples": ["7", 0], "vae": ["3", 0]}},
    # 视频合并
    "12": {"class_type": "VHS_VideoCombine", "inputs": {
        "images": ["8", 0],
        "frame_rate": 24.0,
        "loop_count": 0,
        "filename_prefix": "LTX23_smoke/LTX23_quality_40s",
        "format": "video/h264-mp4",
        "pingpong": False,
        "save_output": True}},
}

print("\n提交质量验证测试 (LoRA 0.6 + 40步 + euler_ancestral_cfg_pp + NAG)...")
r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print(f"prompt_id: {pid}")

start = time.time()
while True:
    time.sleep(15)
    try:
        q = json.loads(urllib.request.urlopen(f"{COMFY}/queue", timeout=10).read())
        if len(q.get("queue_running", [])) == 0:
            h = json.loads(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=10).read())
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("completed"):
                    print(f"\nDONE status={st.get('status_str')} 耗时={int(time.time()-start)}s")
                    break
        elapsed = int(time.time() - start)
        if elapsed % 60 == 0:
            print(f"  运行中... {elapsed}s", flush=True)
        if elapsed > 2400:  # 40分钟上限（40步约3倍于8步的10分钟）
            print("\nTIMEOUT 40min")
            break
    except Exception as e:
        print(f"  查询异常: {e}")

outs = sorted(glob.glob(r"D:/ai_projects/ComfyUI/output/LTX23_smoke/LTX23_quality_40s*"))
print("\n输出文件:")
for o in outs:
    print(f"  {os.path.getsize(o)/1048576:8.1f} MB  {os.path.basename(o)}")
