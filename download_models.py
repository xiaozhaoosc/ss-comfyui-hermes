import os, sys, urllib.request, time

token = open(os.path.expanduser('~/.cache/huggingface/token')).read().strip()
proxy = 'http://127.0.0.1:7897'
proxy_handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
opener = urllib.request.build_opener(proxy_handler)

models = [
    {
        'url': 'https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b.safetensors',
        'dest': 'D:/ai_projects/ComfyUI/models/text_encoders/qwen_3_8b.safetensors',
        'name': 'qwen_3_8b'
    },
    {
        'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
        'dest': 'D:/ai_projects/ComfyUI/models/vae/flux2-vae.safetensors',
        'name': 'flux2-vae'
    },
    {
        'url': 'https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF/resolve/main/flux-2-klein-9b-Q4_K_M.gguf',
        'dest': 'D:/ai_projects/ComfyUI/models/diffusion_models/flux-2-klein-9b-Q4_K_M.gguf',
        'name': 'Q4_K_M GGUF'
    },
]

for m in models:
    dest = m['dest']
    if os.path.exists(dest):
        sz = os.path.getsize(dest)
        if sz > 1000000:  # > 1MB means likely already downloaded
            print(f"SKIP {m['name']}: already exists ({sz/1e9:.1f}GB)")
            continue

    print(f"=== Downloading {m['name']} ===")
    start = time.time()
    req = urllib.request.Request(m['url'], headers={'Authorization': f'Bearer {token}'})
    try:
        resp = opener.open(req, timeout=3600)
        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        with open(dest + '.tmp', 'wb') as f:
            while True:
                chunk = resp.read(1024*1024)  # 1MB chunks
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded / total * 100
                    speed = downloaded / (time.time() - start + 0.1) / 1e6
                    print(f"\r  {downloaded/1e9:.1f}/{total/1e9:.1f}GB ({pct:.0f}%) {speed:.1f}MB/s", end='', flush=True)
                elif downloaded % (100*1024*1024) < 1024*1024:
                    print(f"\r  {downloaded/1e9:.1f}GB downloaded", end='', flush=True)
        os.replace(dest + '.tmp', dest)
        elapsed = time.time() - start
        print(f"\n  Done! {downloaded/1e9:.1f}GB in {elapsed:.0f}s")
    except Exception as e:
        print(f"\n  ERROR: {e}")
        if os.path.exists(dest + '.tmp'):
            os.remove(dest + '.tmp')

print("\n=== ALL DOWNLOADS COMPLETE ===")
