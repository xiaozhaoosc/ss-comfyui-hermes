import os, sys, time, signal

def handler(sig, frame):
    print("\n[!] Interrupted")
    sys.exit(1)
signal.signal(signal.SIGINT, handler)

os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'

import requests

URL = "https://huggingface.co/imaginairy/idm-vton-safetensors/resolve/main/unet/diffusion_pytorch_model.fp16.safetensors"
DEST = "models/IDM-VTON/unet/diffusion_pytorch_model.safetensors"
TOTAL = 5982726688  # 5.98GB
CHUNK = 262144  # 256KB

os.makedirs(os.path.dirname(DEST), exist_ok=True)

# Check resume
temp = DEST + ".downloading"
resume_at = os.path.getsize(temp) if os.path.exists(temp) else 0
if resume_at > 0:
    print(f"[*] Resuming from {resume_at/1e6:.1f} MB ({resume_at*100/TOTAL:.1f}%)")

headers = {}
if resume_at > 0:
    headers['Range'] = f'bytes={resume_at}-'

print(f"[*] Downloading UNet fp16 ({TOTAL/1e6:.0f} MB)")
print(f"[*] Destination: {DEST}")
print(f"[*] Using proxy: {os.environ['HTTPS_PROXY']}")
print()

mode = 'ab' if resume_at > 0 else 'wb'
start = time.time()
downloaded = resume_at

try:
    r = requests.get(URL, stream=True, timeout=60, headers=headers)
    if resume_at > 0 and r.status_code == 206:
        pass  # Resume OK
    elif r.status_code == 200:
        if resume_at > 0:
            print("[!] Server doesn't support resume, restarting")
            mode = 'wb'
            downloaded = 0
    else:
        print(f"[ERR] HTTP {r.status_code}")
        sys.exit(1)

    last_print = 0
    with open(temp, mode) as f:
        for chunk in r.iter_content(CHUNK):
            f.write(chunk)
            downloaded += len(chunk)
            now = time.time()
            if now - last_print >= 5:
                elapsed = now - start
                speed = (downloaded - resume_at) / elapsed if elapsed > 0 else 0
                pct = downloaded * 100 / TOTAL
                eta = (TOTAL - downloaded) / speed if speed > 0 else 0
                print(f"[{pct:5.1f}%] {downloaded/1e6:.0f}/{TOTAL/1e6:.0f} MB | {speed/1e6:.1f} MB/s | ETA {eta/60:.0f}min")
                last_print = now

    elapsed = time.time() - start
    print(f"\n[OK] Downloaded in {elapsed/60:.1f} min")
    
    # Rename
    if os.path.exists(DEST):
        os.remove(DEST)
    os.rename(temp, DEST)
    print(f"[OK] Saved to: {DEST}")
    print(f"[OK] Size: {os.path.getsize(DEST)/1e9:.2f} GB")
    print("[DONE] Ready for IDM-VTON inference!")

except Exception as e:
    print(f"\n[ERR] {e}")
    print(f"[*] Partial file saved at {temp}, rerun to resume")
    sys.exit(1)
