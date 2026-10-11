"""
阶段零：模型资产验证脚本
检查执行计划中列出的所有必需模型文件是否已就位。
"""
import os

BASE = r"D:\ai_projects\ComfyUI"

# (相对路径, 最小字节数, 描述, 是否必须阻塞)
REQUIRED_ASSETS = [
    # ---- 已有（验证存在性） ----
    ("models/clip/t5xxl_fp8_e4m3fn.safetensors",  4_000_000_000, "CLIP T5-XXL FP8", True),
    ("models/clip/clip_l.safetensors",             200_000_000,   "CLIP-L",          True),
    ("models/vae/ae.safetensors",                  300_000_000,   "VAE (Flux)",      True),
    ("models/upscale_models/RealESRGAN_x4plus.pth", 60_000_000,  "RealESRGAN x4+",  True),
    ("models/insightface/models/buffalo_l/det_10g.onnx", 10_000_000, "InsightFace det", True),

    # ---- 需要下载 ----
    ("models/unet/flux1-dev-fp8.safetensors",      10_000_000_000, "Flux.1 Dev UNET FP8 (标准版)", True),
    ("models/pulid/pulid_flux_v1.safetensors",     900_000_000,    "PuLID-Flux 权重",              True),
    ("models/eva_clip/EVA02_CLIP_L_336_psz14_s6B.pt", 300_000_000, "Eva-CLIP 视觉编码器",         True),
    ("models/upscale_models/4x-UltraSharp.pth",    50_000_000,    "4x-UltraSharp 放大权重",       False),
    ("models/diffusion_models/wan2.1-14b-t2v-Q4_K_M.gguf", 5_000_000_000, "Wan2.1 14B GGUF", False),
    ("models/vae/wan_2.1_vae.safetensors",         100_000_000,   "Wan2.1 VAE",                    False),
]

def check():
    print("=" * 70)
    print("  ComfyUI 模型资产盘点 — 阶段零验证")
    print("=" * 70)

    ready = []
    missing_critical = []
    missing_optional = []

    for rel_path, min_bytes, desc, critical in REQUIRED_ASSETS:
        full = os.path.join(BASE, rel_path)
        exists = os.path.exists(full)
        size_ok = exists and os.path.getsize(full) >= min_bytes

        if size_ok:
            size_mb = os.path.getsize(full) / (1024 * 1024)
            print(f"  ✅  {desc:40s}  {size_mb:>10.1f} MB  {rel_path}")
            ready.append(desc)
        else:
            tag = "🔴 CRITICAL" if critical else "🟡 OPTIONAL"
            reason = "文件不存在" if not exists else f"文件过小 ({os.path.getsize(full)} bytes)"
            print(f"  {tag}  {desc:40s}  {reason:>20s}  {rel_path}")
            if critical:
                missing_critical.append((desc, rel_path))
            else:
                missing_optional.append((desc, rel_path))

    print()
    print("-" * 70)
    print(f"  ✅ 已就位: {len(ready)} 项")
    print(f"  🔴 关键缺失: {len(missing_critical)} 项")
    print(f"  🟡 可选缺失: {len(missing_optional)} 项")
    print("-" * 70)

    if missing_critical:
        print("\n  ⚠️  以下关键模型缺失将阻塞阶段一 (Flux PuLID 换脸):")
        for desc, path in missing_critical:
            print(f"      → {desc}: {path}")
        print()

    if missing_optional:
        print("\n  ℹ️  以下可选模型缺失将影响阶段三/四 (放大 / 视频):")
        for desc, path in missing_optional:
            print(f"      → {desc}: {path}")

    return len(missing_critical) == 0

if __name__ == "__main__":
    all_clear = check()
    if all_clear:
        print("\n  🎉 所有关键资产已就位！可以进入阶段一。")
    else:
        print("\n  ❌ 存在关键缺失，请先完成模型下载。")
