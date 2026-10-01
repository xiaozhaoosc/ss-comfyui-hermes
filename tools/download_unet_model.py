"""
下载 IDM-VTON UNet safetensors 模型（替换损坏的 .bin 文件）

用法: python download_unet_model.py [--mirror] [--proxy http://127.0.0.1:7897]

模型源: imaginairy/idm-vton-safetensors/unet/diffusion_pytorch_model.fp16.safetensors
大小: ~5.7GB
"""
import argparse, os, sys, time, urllib.request

REPO = "imaginairy/idm-vton-safetensors"
FILENAME = "unet/diffusion_pytorch_model.fp16.safetensors"
DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "IDM-VTON", "unet")
DEST_FILE = os.path.join(DEST_DIR, "diffusion_pytorch_model.safetensors")

def get_url(mirror=False):
    base = "https://hf-mirror.com" if mirror else "https://huggingface.co"
    return f"{base}/{REPO}/resolve/main/{FILENAME}"

def download_with_progress(url, dest, proxy=None):
    if proxy:
        proxy_handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()
    
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    print(f"URL: {url}")
    print(f"Dest: {dest}")
    print(f"Downloading...")
    
    t0 = time.time()
    last_size = [0]
    
    def report(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = downloaded / total_size * 100
            speed = downloaded / (time.time() - t0) / 1024 / 1024
            print(f"\r  {downloaded/1024/1024:.0f}/{total_size/1024/1024:.0f}MB ({pct:.1f}%) {speed:.1f}MB/s  ", end="", flush=True)
    
    try:
        opener.open(url)  # test connectivity
    except Exception as e:
        print(f"Connection error: {e}")
        return False
    
    urllib.request.urlretrieve(url, dest, reporthook=report)
    
    size = os.path.getsize(dest)
    elapsed = time.time() - t0
    print(f"\n✅ Done: {size/1024/1024:.0f}MB in {elapsed:.0f}s ({size/1024/1024/elapsed:.1f}MB/s)")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror", action="store_true", help="Use hf-mirror.com")
    parser.add_argument("--proxy", default=None, help="HTTP proxy (e.g. http://127.0.0.1:7897)")
    args = parser.parse_args()
    
    url = get_url(args.mirror)
    ok = download_with_progress(url, DEST_FILE, args.proxy)
    
    if ok and os.path.exists(DEST_FILE):
        # Verify it's a valid safetensors file
        try:
            from safetensors import safe_open
            with safe_open(DEST_FILE, framework="pt") as f:
                keys = f.keys()
                print(f"✅ Verified: {len(list(keys))} tensors")
        except Exception as e:
            print(f"⚠️ Could not verify: {e}")
