# 从 hf-mirror.com 手动下载 Ideogram 4 NF4 模型
# 绕过 huggingface_hub 库的 endpoint 问题
import os
import json
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from huggingface_hub import hf_hub_download

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

REPO = "ideogram-ai/ideogram-4-nf4"
BASE_URL = f"https://hf-mirror.com/{REPO}/resolve/main"
LOCAL_DIR = Path("D:/ai_projects/ComfyUI/models/ideogram4-nf4")
LOCAL_DIR.mkdir(parents=True, exist_ok=True)

HF_TOKEN = os.environ.get("HF_TOKEN", "")

# 忽略 SSL 证书验证（hf-mirror 镜像可能有问题）
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def _auth_headers():
    return {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {HF_TOKEN}",
    }

def list_repo_files():
    """通过 API 获取仓库文件列表"""
    api_url = f"https://hf-mirror.com/api/models/{REPO}"
    print(f"获取文件列表: {api_url}")
    try:
        req = urllib.request.Request(api_url, headers=_auth_headers())
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("siblings", [])
    except Exception as e:
        print(f"API 获取失败: {e}")
        return []

def download_file(filepath, filesize=None):
    """从 hf-mirror.com 下载单个文件"""
    url = f"{BASE_URL}/{filepath}"
    local_path = LOCAL_DIR / filepath
    local_path.parent.mkdir(parents=True, exist_ok=True)

    if local_path.exists():
        local_size = local_path.stat().st_size
        if filesize and local_size == filesize:
            print(f"  [SKIP] {filepath} (已存在, {local_size} bytes)")
            return True
        print(f"  [RESUME] {filepath} (本地 {local_size} bytes)")

    print(f"  [DOWNLOAD] {filepath}")
    try:
        req = urllib.request.Request(url, headers=_auth_headers())
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(local_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        print(f"\r    {downloaded}/{total} ({pct}%)", end="", flush=True)
            print()
        return True
    except urllib.error.HTTPError as e:
        print(f"  [ERROR] HTTP {e.code}: {filepath}")
        return False
    except Exception as e:
        print(f"  [ERROR] {filepath}: {e}")
        return False

print("=" * 60)
print("Ideogram 4 NF4 模型下载（hf-mirror.com 镜像）")
print(f"仓库: {REPO}")
print(f"本地路径: {LOCAL_DIR}")
print("=" * 60)

# 获取文件列表
files = list_repo_files()
if not files:
    print("无法获取文件列表，使用已知文件列表")
    # 手动列出已知文件
    known_files = [
        "transformer/diffusion_pytorch_model.safetensors.index.json",
        "unconditional_transformer/diffusion_pytorch_model.safetensors.index.json",
        "vae/diffusion_pytorch_model.safetensors",
    ]
    files = [{"rfilename": f} for f in known_files]

file_list = [f["rfilename"] for f in files]
print(f"\n共 {len(file_list)} 个文件:")
for f in file_list:
    print(f"  - {f}")

# 下载 index.json 文件以获取分片列表
print("\n--- 下载 index.json 文件 ---")
for f in file_list:
    if f.endswith(".json") or f.endswith(".txt") or f.endswith(".model") or f.endswith("config.json") or f.endswith("tokenizer.json") or f.endswith("tokenizer_config.json") or f.endswith("special_tokens_map.json") or f.endswith("vocab.json") or f.endswith("merges.txt") or f.endswith("added_tokens.json") or f.endswith("preprocessor_config.json") or f.endswith("chat_template.json"):
        download_file(f)

# 读取 index.json 获取分片文件
print("\n--- 读取 index.json 获取分片列表 ---")
all_safetensors = set()

# 直接下载所有 safetensors 文件
for f in file_list:
    if f.endswith(".safetensors"):
        all_safetensors.add(f)

# 也从 index.json 读取分片
for idx_file in ["transformer/diffusion_pytorch_model.safetensors.index.json",
                  "unconditional_transformer/diffusion_pytorch_model.safetensors.index.json"]:
    idx_path = LOCAL_DIR / idx_file
    if idx_path.exists():
        with open(idx_path) as fp:
            idx_data = json.load(fp)
        for shard in idx_data.get("weight_map", {}).values():
            all_safetensors.add(f"{shard.split('/')[0]}/{shard}" if "/" not in shard else shard)

print(f"\n共 {len(all_safetensors)} 个 safetensors 文件需要下载")

# 下载所有 safetensors 文件
print("\n--- 下载 safetensors 文件 ---")
success = 0
failed = []
for f in sorted(all_safetensors):
    if download_file(f):
        success += 1
    else:
        failed.append(f)

# 下载剩余文件（text_encoder, tokenizer 等目录）
print("\n--- 下载其他文件 ---")
other_exts = [".json", ".txt", ".model", ".safetensors"]
for f in file_list:
    if f not in all_safetensors and not f.endswith(".md"):
        download_file(f)

print("\n" + "=" * 60)
print(f"下载完成: {success}/{len(all_safetensors)} safetensors 成功")
if failed:
    print(f"失败文件:")
    for f in failed:
        print(f"  - {f}")
print(f"模型保存在: {LOCAL_DIR}")
print("=" * 60)
