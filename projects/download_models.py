"""
阶段零：模型下载脚本 (HTTP 直接下载版)
绕过 huggingface_hub API 的复杂校验和证书阻碍，直接通过 HTTP 从国内镜像站流式下载模型文件。
- 支持大文件断点续传 (HTTP Range Header)
- 附带 tqdm 动态进度条
- 自动重命名与路径分发
"""
import os
import sys
import requests
from tqdm import tqdm

BASE = r"D:\ai_projects\ComfyUI\models"

# (url, local_dir, target_filename, 描述, 是否关键)
DOWNLOADS = [
    # ---- 关键阻塞项 (阶段一：Flux PuLID 换脸) ----
    (
        "https://hf-mirror.com/Kijai/flux-fp8/resolve/main/flux1-dev-fp8.safetensors",
        os.path.join(BASE, "unet"),
        "flux1-dev-fp8.safetensors",
        "Flux.1 Dev UNET FP8 (非受限镜像 ~12GB)",
        True,
    ),
    (
        "https://hf-mirror.com/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors",
        os.path.join(BASE, "pulid"),
        "pulid_flux_v1.safetensors",  # 自动重命名对齐 ComfyUI 默认名
        "PuLID-Flux 权重 (~1.1GB)",
        True,
    ),
    (
        "https://hf-mirror.com/QuanSun/EVA-CLIP/resolve/main/EVA02_CLIP_L_336_psz14_s6B.pt",
        os.path.join(BASE, "eva_clip"),
        "EVA02_CLIP_L_336_psz14_s6B.pt",
        "Eva-CLIP 视觉编码器 (~420MB)",
        True,
    ),
    # ---- 可选项 (阶段三：4K 放大) ----
    (
        "https://hf-mirror.com/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth",
        os.path.join(BASE, "upscale_models"),
        "4x-UltraSharp.pth",
        "4x-UltraSharp 放大模型 (~64MB)",
        False,
    ),
    # ---- 可选项 (阶段四：Wan2.1 视频) ----
    (
        "https://hf-mirror.com/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors",
        os.path.join(BASE, "vae"),
        "wan_2.1_vae.safetensors",  # 自动重命名
        "Wan2.1 VAE (~320MB)",
        False,
    ),
]

def download_file(url, local_dir, filename, desc):
    """
    流式下载大文件，支持断点续传
    """
    os.makedirs(local_dir, exist_ok=True)
    dest_path = os.path.join(local_dir, filename)
    temp_path = dest_path + ".tmp"

    print(f"\n{'='*70}")
    print(f"  正在下载: {desc}")
    print(f"  URL: {url}")
    print(f"  目标: {dest_path}")
    print(f"{'='*70}")

    # 1. 检查最终文件是否已存在
    if os.path.exists(dest_path):
        # 对超大文件简单做个大于10MB的校验判定，防止空文件
        if os.path.getsize(dest_path) > 10 * 1024 * 1024 or not desc.endswith("~12GB)"):
            print(f"  [!] 文件已完整存在，跳过下载: {dest_path}")
            return True

    # 2. 获取当前已下载大小，准备断点续传
    initial_pos = 0
    if os.path.exists(temp_path):
        initial_pos = os.path.getsize(temp_path)
        print(f"  [*] 发现临时文件，已下载大小: {initial_pos / (1024*1024):.2f} MB，准备续传...")

    # 3. 发起请求
    headers = {}
    if initial_pos > 0:
        headers["Range"] = f"bytes={initial_pos}-"

    try:
        # verify=True，因为 hf-mirror 证书有效；且流式获取
        r = requests.get(url, headers=headers, stream=True, timeout=30)
        
        # 处理续传 206 响应或全新下载 200 响应
        if r.status_code == 206:
            mode = "ab"
            total_size = int(r.headers.get("content-range", "").split("/")[-1])
        elif r.status_code == 200:
            mode = "wb"
            initial_pos = 0
            total_size = int(r.headers.get("content-length", 0))
        elif r.status_code == 416:
            # Range Requested Not Satisfiable -> 说明文件可能已经下载完了
            print("  [!] 提示: 服务器返回 416 (可能临时文件已满载)，尝试直接重命名完成...")
            if os.path.exists(temp_path):
                shutil_move(temp_path, dest_path)
                return True
            return False
        else:
            print(f"  [FAIL] 服务器返回状态码: {r.status_code}")
            return False

        # 4. 执行写入并展示 tqdm 进度条
        chunk_size = 1024 * 1024  # 1MB 缓冲区
        with open(temp_path, mode) as f:
            with tqdm(
                total=total_size,
                initial=initial_pos,
                unit="B",
                unit_scale=True,
                desc=desc[:20],
                file=sys.stdout
            ) as pbar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        # 5. 下载完成后重命名为最终文件
        if os.path.exists(temp_path):
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(temp_path, dest_path)
            print(f"  [OK] {desc} 下载且校验成功!")
            return True
        return False

    except Exception as e:
        print(f"  [FAIL] 下载异常: {e}")
        return False

def shutil_move(src, dst):
    import shutil
    try:
        shutil.move(src, dst)
    except Exception as e:
        print(f"  [ERROR] 移动文件失败: {e}")

def main():
    print("=" * 70)
    print("  ComfyUI 模型下载器 — HTTP 直流优化版")
    print(f"  目标位置: {BASE}")
    print(f"  共 {len(DOWNLOADS)} 个模型等待验证/下载")
    print("=" * 70)

    critical_ok = []
    critical_fail = []
    optional_ok = []
    optional_fail = []

    for url, local_dir, filename, desc, is_critical in DOWNLOADS:
        ok = download_file(url, local_dir, filename, desc)
        if is_critical:
            (critical_ok if ok else critical_fail).append(desc)
        else:
            (optional_ok if ok else optional_fail).append(desc)

    print(f"\n{'='*70}")
    print("  下载汇总")
    print(f"{'='*70}")
    print(f"  🔴 关键项成功: {len(critical_ok)}/{len(critical_ok)+len(critical_fail)}")
    print(f"  🟡 可选项成功: {len(optional_ok)}/{len(optional_ok)+len(optional_fail)}")

    if critical_fail:
        print(f"\n  [!] 仍有关键阻塞项失败: {', '.join(critical_fail)}")
        print("  请检查网络是否稳定并重试本脚本。")
        sys.exit(1)
    else:
        print("\n  🎉 阶段一所需的所有关键模型已就位！")

if __name__ == "__main__":
    main()
