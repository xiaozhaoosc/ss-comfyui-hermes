# -*- coding: utf-8 -*-
"""下载门控 black-forest-labs/FLUX.1-dev（diffusers 结构，跳过根目录单文件大模型）供 ai-toolkit 训练。
用法: python download_flux_dev.py [endpoint]   # 默认 https://hf-mirror.com
"""
import os, sys, time

os.environ["HF_HOME"] = r"D:\AI_Cache\huggingface"
os.environ["HF_HUB_DISABLE_XET"] = "1"  # Windows 上 hf_xet 大文件 OSError(22) 已知问题, 强制标准 HTTP
if len(sys.argv) > 1:
    os.environ["HF_ENDPOINT"] = sys.argv[1]
else:
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

TOKEN_PATH = os.path.expanduser("~/.cache/huggingface/token")
with open(TOKEN_PATH, "r", encoding="utf-8") as f:
    TOKEN = f.read().strip()

REPO = "black-forest-labs/FLUX.1-dev"
# 只下 diffusers 目录结构; 排除根目录 23.8G 单文件 flux1-dev.safetensors
ALLOW = ["*.json", "*.txt", "*.md",
         "transformer/*", "text_encoder/*", "text_encoder_2/*",
         "vae/*", "tokenizer/*", "tokenizer_2/*", "scheduler/*"]

from huggingface_hub import snapshot_download

for attempt in range(1, 9):
    print(f"[{time.strftime('%H:%M:%S')}] attempt #{attempt} via {os.environ['HF_ENDPOINT']}", flush=True)
    try:
        path = snapshot_download(repo_id=REPO, token=TOKEN,
                                  allow_patterns=ALLOW, max_workers=2)
        print("SNAPSHOT_DONE ->", path, flush=True)
        # 简单校验关键文件
        import os.path as p
        for sub in ("transformer", "text_encoder", "vae"):
            d = p.join(path, sub)
            sz = sum(p.getsize(p.join(d, f)) for f in os.listdir(d)) if p.isdir(d) else 0
            print(f"  {sub}: {sz/1e9:.2f} GB", flush=True)
        print("ALL_OK", flush=True)
        sys.exit(0)
    except Exception as e:
        print("ERR:", repr(e)[:600], flush=True)
        time.sleep(30)
print("DOWNLOAD_FAILED", flush=True)
sys.exit(1)