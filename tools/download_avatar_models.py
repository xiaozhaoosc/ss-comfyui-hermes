# 换头/换脸/换衣/动作迁移/H3 整合管线模型下载
# 用法: python tools/download_avatar_models.py
# 默认走 hf-mirror 镜像; 直连 HF 可设 HF_ENDPOINT=https://huggingface.co
import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from huggingface_hub import snapshot_download

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(BASE, "models")

H3_REPO = "Comfy-Org/MiniMax-H3"
H3_FILES = [
    "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",  # 19.5GB R2V
    "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",          # 14.6GB
    "vae/minimax_h3_video_vae_fp16.safetensors",                           # 4.9GB
    "vae/minimax_h3_audio_vae_fp32.safetensors",                           # 0.6GB
]


def done(rel):
    return os.path.exists(os.path.join(MODELS, rel))


def main():
    failed = []

    # 1. MimicMotion 主体 (节点运行时也会自动下载, 这里预下载保证离线就绪)
    mm_dir = os.path.join(MODELS, "mimicmotion")
    mm_file = os.path.join(mm_dir, "MimicMotionMergedUnet_1-0-fp16.safetensors")
    if os.path.exists(mm_file):
        print("[skip] MimicMotionMergedUnet_1-0-fp16 已存在")
    else:
        print("[down] MimicMotion pruned fp16 (~4.2GB)")
        try:
            snapshot_download("Kijai/MimicMotion_pruned",
                              allow_patterns=["*MimicMotionMergedUnet_1-0-fp16*"],
                              local_dir=mm_dir)
            print("[ok]   MimicMotion")
        except Exception as e:
            failed.append(("MimicMotion", e))
            print(f"[fail] MimicMotion: {e}")

    # 2. MimicMotion 的 SVD 依赖 (json + fp16 非 unet)
    svd_dir = os.path.join(MODELS, "diffusers", "stable-video-diffusion-img2vid-xt-1-1")
    if os.path.exists(os.path.join(svd_dir, "scheduler", "scheduler_config.json")):
        print("[skip] SVD 依赖已存在")
    else:
        print("[down] SVD img2vid-xt-1-1 依赖 (~2GB)")
        try:
            snapshot_download("vdo/stable-video-diffusion-img2vid-xt-1-1",
                              allow_patterns=["*.json", "*fp16*"],
                              ignore_patterns=["*unet*"],
                              local_dir=svd_dir)
            print("[ok]   SVD 依赖")
        except Exception as e:
            failed.append(("SVD", e))
            print(f"[fail] SVD: {e}")

    # 3. MiniMax H3 R2V 套件 (~40GB, 逐个下载便于断点排查)
    for f in H3_FILES:
        if done(f):
            print(f"[skip] {f} 已存在")
            continue
        print(f"[down] {f}")
        try:
            snapshot_download(H3_REPO, allow_patterns=[f], local_dir=MODELS)
            print(f"[ok]   {f}" if done(f) else f"[warn] {f} 下载完成但文件未落位")
        except Exception as e:
            failed.append((f, e))
            print(f"[fail] {f}: {e}")

    print("=" * 50)
    if failed:
        print(f"完成但有 {len(failed)} 项失败:")
        for name, e in failed:
            print(f"  - {name}: {e}")
        sys.exit(1)
    print("全部模型就绪")


if __name__ == "__main__":
    main()
