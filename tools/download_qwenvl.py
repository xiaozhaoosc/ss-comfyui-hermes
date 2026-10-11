#!/usr/bin/env python3
"""Download Qwen3-VL-8B-Instruct-FP8 from ModelScope to ComfyUI LLM directory."""
import os
import sys
import time
import requests

PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
BASE_URL = "https://modelscope.cn/models/Qwen/Qwen3-VL-8B-Instruct-FP8/resolve/master"
TARGET_DIR = "D:/ai_projects/ComfyUI/models/LLM/Qwen-VL/Qwen3-VL-8B-Instruct-FP8"

FILES = [
    "config.json",
    "generation_config.json",
    "preprocessor_config.json",
    "video_preprocessor_config.json",
    "chat_template.json",
    "configuration.json",
    "tokenizer_config.json",
    "model.safetensors.index.json",
    "vocab.json",
    "tokenizer.json",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
]

os.makedirs(TARGET_DIR, exist_ok=True)

for fname in FILES:
    url = f"{BASE_URL}/{fname}"
    out_path = os.path.join(TARGET_DIR, fname)
    tmp_path = out_path + ".tmp"

    # Skip if already downloaded and size > 0
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"[SKIP] {fname} already exists ({size_mb:.1f} MB)", flush=True)
        continue

    # Resume support
    resume_from = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
    headers = {"Range": f"bytes={resume_from}-"} if resume_from > 0 else {}

    print(f"[DL] {fname} (resuming from {resume_from/1024/1024:.1f} MB)...", flush=True)

    for attempt in range(3):
        try:
            session = requests.Session()
            session.proxies = PROXY
            resp = session.get(url, headers=headers, stream=True, timeout=(30, 300))
            
            if resume_from > 0 and resp.status_code == 206:
                mode = "ab"
            elif resp.status_code == 200:
                mode = "wb"
                resume_from = 0  # server doesn't support range, restart
            else:
                print(f"  HTTP {resp.status_code}, retrying...", flush=True)
                time.sleep(5)
                continue

            total = int(resp.headers.get("content-length", 0))
            downloaded = resume_from
            start_time = time.time()

            with open(tmp_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            speed = (downloaded - resume_from) / elapsed / 1024 / 1024
                            pct = (downloaded / (total + resume_from) * 100) if total else 0
                            print(f"\r  {downloaded/1024/1024:.0f} MB @ {speed:.1f} MB/s ({pct:.0f}%)", end="", flush=True)
            
            print()  # newline after progress
            os.rename(tmp_path, out_path)
            final_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"  ✅ Done: {final_mb:.1f} MB", flush=True)
            break
        except Exception as e:
            print(f"\n  Error: {e}", flush=True)
            if attempt < 2:
                print(f"  Retrying in 5s... (attempt {attempt+2}/3)", flush=True)
                time.sleep(5)
            else:
                print(f"  ❌ FAILED after 3 attempts", flush=True)
                sys.exit(1)
        finally:
            session.close()

    time.sleep(1)  # brief pause between files

print("\n🎉 All files downloaded!", flush=True)

# Verify
print("\n=== Verification ===")
for fname in FILES:
    path = os.path.join(TARGET_DIR, fname)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"  ✅ {fname}: {size/1024/1024:.1f} MB")
    else:
        print(f"  ❌ {fname}: MISSING")
