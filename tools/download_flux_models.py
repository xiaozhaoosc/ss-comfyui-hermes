#!/usr/bin/env python3
"""FLUX 模型稳健下载器：串行 + 断点续传 + 无限重试 + 校验大小

策略：一次只下 1 个文件（避免并发触发 HF 限流/GFW 干扰），
curl -C - 断点续传，失败后等待 30s 重试，直到达到目标大小。
"""
import subprocess, sys, time, os

FILES = [
    ("text_encoders/t5xxl_fp8_e4m3fn.safetensors",
     "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
     4894626816),
    ("unet/T8-flux.1-dev-abliterated-V2-GGUF-Q8_0.gguf",
     "https://huggingface.co/t8star/flux.1-dev-abliterated-V2-GGUF/resolve/main/T8-flux.1-dev-abliterated-V2-GGUF-Q8_0.gguf",
     12720000000),
    ("unet/T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M.gguf",
     "https://huggingface.co/t8star/flux.1-dev-abliterated-V2-GGUF/resolve/main/T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M.gguf",
     6940000000),
]

BASE = r"D:/ai_projects/ComfyUI/models"

def download(path, url, target_size):
    full = os.path.join(BASE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    attempt = 0
    while True:
        attempt += 1
        cur = os.path.getsize(full) if os.path.exists(full) else 0
        print(f"[{time.strftime('%H:%M:%S')}] {os.path.basename(path)} 尝试#{attempt} 已有 {cur/1e9:.2f}G/{target_size/1e9:.2f}G", flush=True)
        if cur >= target_size * 0.99:
            print(f"  ✅ {os.path.basename(path)} 完成", flush=True)
            return True
        cmd = ["curl", "-sL", "-C", "-", "--max-time", "5400",
               "-o", full, url]
        # 长命令直接放 --write-out 最后
        cmd += ["-w", f"\nDL_DONE size=%{{size_download}} http=%{{http_code}} speed=%{{speed_download}}\n"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5500)
            out = r.stdout + r.stderr
            if r.returncode == 0:
                new_cur = os.path.getsize(full) if os.path.exists(full) else 0
                print(f"  rc=0 现在 {new_cur/1e9:.2f}G", flush=True)
                if new_cur >= target_size * 0.99:
                    print(f"  ✅ {os.path.basename(path)} 完成", flush=True)
                    return True
            else:
                print(f"  rc={r.returncode} {out.strip()[-200:]}", flush=True)
        except Exception as e:
            print(f"  EXC {e}", flush=True)
        time.sleep(30)

def main():
    # 可选参数：起始索引
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    for i, (path, url, size) in enumerate(FILES):
        if i < start:
            continue
        print(f"\n===== [{i+1}/{len(FILES)}] {path} =====", flush=True)
        ok = download(path, url, size)
        if not ok:
            print("  连续失败，退出", flush=True)
            sys.exit(1)
    print("\n🎉 全部下载完成", flush=True)

if __name__ == "__main__":
    main()
