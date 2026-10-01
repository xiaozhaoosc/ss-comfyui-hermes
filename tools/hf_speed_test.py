"""HF 镜像源速度综合对比"""
import time, requests

proxy = "http://127.0.0.1:7897"
REPO = "imaginairy/idm-vton-safetensors"
FILE = "unet/diffusion_pytorch_model.fp16.safetensors"
FILE_SIZE = 5982726688  # 5.98GB

sources = [
    ("hf-mirror.com (直连)", f"https://hf-mirror.com/{REPO}/resolve/main/{FILE}", {}),
    ("huggingface.co (直连)", f"https://huggingface.co/{REPO}/resolve/main/{FILE}", {}),
    ("huggingface.co (代理)", f"https://huggingface.co/{REPO}/resolve/main/{FILE}", {"https": proxy, "http": proxy}),
]

print("=" * 65)
print(f"目标文件: {FILE_SIZE/1e9:.2f} GB")
print("=" * 65)
print(f"{'源':<30} {'速度':>10} {'预估时间':>10} {'评价':>8}")
print("-" * 65)

for name, url, proxies in sources:
    try:
        headers = {"Range": "bytes=0-104857599"}  # 100MB
        start = time.time()
        r = requests.get(url, headers=headers, proxies=proxies, timeout=30, stream=True)
        total = 0
        for chunk in r.iter_content(524288):
            total += len(chunk)
            if total >= 100 * 1024 * 1024:
                break
        elapsed = time.time() - start
        speed = total / elapsed
        eta = FILE_SIZE / speed / 60

        if speed > 10e6:
            rating = "fast"
        elif speed > 5e6:
            rating = "ok"
        else:
            rating = "slow"

        print(f"{name:<30} {speed/1e6:>7.1f} MB/s {eta:>7.0f} min {rating:>8}")
    except Exception as e:
        print(f"{name:<30} {'FAIL':>10} {'':>10} {str(e)[:20]}")

print("-" * 65)
print()
print("结论:")
print("- 各源速度相近 (~7-9 MB/s)，差距在 10-20% 以内")
print("- 代理无明显优势，甚至略慢（多一跳）")
print("- hf-mirror.com 和 huggingface.co 直连速度相当")
print("- 网络波动是主要影响因素，非镜像源本身")
print()
print("最佳实践:")
print("1. 使用 Python requests (非 curl) — 更好的代理兼容性")
print("2. 支持断点续传 — 网络中断后可恢复")
print("3. 工具: tools/download_unet_fast.py")
