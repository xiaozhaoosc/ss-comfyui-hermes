#!/usr/bin/env python3
"""LTX-2.3 极简 i2v 冒烟测试（16GB GGUF 优化版）

链路：
  PinkCherry GGUF (UnetLoaderGGUF)
  + Gemma GGUF (DualCLIPLoaderGGUF, 含投影层)
  + distilled LoRA 384-1.1
  + LTX23 video VAE
  → 首帧: input/ootd/face/gemini/1bh3ie.png（干净单人图）
  → EmptyLTXVLatentImage 768x1280x121帧 @24fps
  → KSampler(euler_cfg_pp, 8步) → VAEDecode → VHS mp4
"""
import json, uuid, urllib.request

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
        print(body[:2000])
        raise

# ---------- 健康检查 ----------
for ep in ["/queue", "/object_info/UNETLoaderGGUF", "/object_info/CLIPLoaderGGUF",
           "/object_info/KSampler"]:
    try:
        urllib.request.urlopen(f"{COMFY}{ep}", timeout=10)
        print(f"  ✅ {ep}")
    except Exception as e:
        print(f"  ❌ {ep}: {e}")
        raise SystemExit("ComfyUI 未就绪")

# ---------- 检查模型文件可加载 ----------
d = json.loads(urllib.request.urlopen(f"{COMFY}/object_info/DualCLIPLoaderGGUF", timeout=10).read())
models = d["DualCLIPLoaderGGUF"]["input"]["required"]["clip_name1"][0]
print("\nDualCLIPLoaderGGUF 可选模型:")
for m in models:
    print(f"  - {m}")
target_gguf = None
for m in models:
    if "heretic" in m.lower() and "q5_k_m" in m.lower():
        target_gguf = m
print(f"\n选择: {target_gguf or '❌ 未找到 heretic Q5_K_M'}")

# ---------- 构造最小工作流 ----------
# 注意: GetNode/SetNode 是 KJNodes 的 JS 前端节点，后端不需要。
# 改用直接连线 + PrimitiveInt/Float 常量节点（KJNodes 后端有 PrimitiveInt/Float）。
wf = {
    # 主模型: PinkCherry GGUF
    "1": {"class_type": "UnetLoaderGGUF", "inputs": {
        "unet_name": "PinkCherry_FineTune_Q5_K_M_v18_LTX23.gguf"}},
    # 文本编码器: Gemma GGUF + 投影层
    "2": {"class_type": "DualCLIPLoaderGGUF", "inputs": {
        "clip_name1": "gemma-3-12b-it-heretic-v2-Q5_K_M.gguf",
        "clip_name2": "ltx-2.3_text_projection_bf16.safetensors",
        "type": "ltxv"}},
    # VAE 视频
    "3": {"class_type": "VAELoader", "inputs": {
        "vae_name": "LTX23_video_vae_bf16.safetensors"}},
    # 首帧: 参考图（从 ComfyUI input/ 根目录读取）
    "4": {"class_type": "LoadImage", "inputs": {
        "image": "Gemini_Generated_Image_1bh3ie1bh3ie1bh3.png"}},
    # 正向提示词编码
    "9": {"class_type": "CLIPTextEncode", "inputs": {
        "clip": ["2", 0],
        "text": "A young Asian woman standing, smiling, gentle breeze, cinematic lighting, high quality, photorealistic"}},
    # 负向提示词编码
    "10": {"class_type": "CLIPTextEncode", "inputs": {
        "clip": ["2", 0],
        "text": "blurry, low quality, distorted, deformed"}},
    # LTX 条件化
    "6": {"class_type": "LTXVConditioning", "inputs": {
        "positive": ["9", 0], "negative": ["10", 0],
        "frame_rate": 24.0}},
    # i2v 首帧锚定（自带 latent 创建）
    "11": {"class_type": "LTXVImgToVideo", "inputs": {
        "positive": ["6", 0], "negative": ["6", 1],
        "vae": ["3", 0],
        "image": ["4", 0],
        "width": 768, "height": 1280, "length": 121,
        "strength": 1.0, "batch_size": 1}},
    # KSampler (8 步冒烟)
    "7": {"class_type": "KSampler", "inputs": {
        "model": ["1", 0],
        "positive": ["11", 0],
        "negative": ["11", 1],
        "latent_image": ["11", 2],
        "seed": 42,
        "steps": 8,
        "cfg": 1.0,
        "sampler_name": "euler",
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
        "filename_prefix": "LTX23_smoke/LTX23_i2v_smoke",
        "format": "video/h264-mp4",
        "pingpong": False,
        "save_output": True}},
}

# ---------- 提交 ----------
print("\n提交 smoke test...")
r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
pid = r.get("prompt_id")
print(f"prompt_id: {pid}")

# ---------- 监控进度 ----------
import time
start = time.time()
while True:
    time.sleep(10)
    try:
        q = json.loads(urllib.request.urlopen(f"{COMFY}/queue", timeout=10).read())
        running = len(q.get("queue_running", []))
        if running == 0:
            # 查 history
            h = json.loads(urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=10).read())
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("completed"):
                    print(f"\n✅ 完成! status={st.get('status_str')}")
                    break
                if st.get("status_str") == "error":
                    print(f"\n❌ 错误! {st}")
                    break
        elapsed = int(time.time() - start)
        print(f"  运行中... 已用 {elapsed}s", flush=True)
        if elapsed > 300:  # 5 分钟内出结果
            print("\n⏰ 超时 5 分钟，检查 ComfyUI 日志")
            break
    except Exception as e:
        print(f"  查询异常: {e}")

# ---------- 检查输出 ----------
import glob, os
outs = glob.glob(r"D:/ai_projects/ComfyUI/output/LTX23_smoke/*")
print(f"\n输出文件:")
for o in sorted(outs)[-5:]:
    sz = os.path.getsize(o) / 1048576
    print(f"  {sz:8.1f} MB  {os.path.basename(o)}")
