"""多线程下载 IDM-VTON UNet safetensors"""
import os, sys, time, threading, requests

URL = "https://huggingface.co/imaginairy/idm-vton-safetensors/resolve/main/unet/diffusion_pytorch_model.fp16.safetensors"
OUT = r"D:\ai_projects\ComfyUI\models\IDM-VTON\unet\diffusion_pytorch_model.safetensors"
PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
CHUNKS = 8  # 并行下载块数

def get_size():
    r = requests.head(URL, proxies=PROXY, timeout=30, allow_redirects=True)
    return int(r.headers.get('content-length', 0))

def download_chunk(url, start, end, idx, buf):
    headers = {'Range': f'bytes={start}-{end}'}
    r = requests.get(url, headers=headers, proxies=PROXY, timeout=120, stream=True)
    data = r.content
    buf[idx] = data
    print(f'  Chunk {idx}: {len(data)/1024/1024:.1f}MB done', flush=True)

def main():
    size = get_size()
    print(f'File size: {size/1024/1024:.0f}MB')
    
    chunk_size = size // CHUNKS
    chunks = [None] * CHUNKS
    threads = []
    
    t0 = time.time()
    for i in range(CHUNKS):
        start = i * chunk_size
        end = (i + 1) * chunk_size - 1 if i < CHUNKS - 1 else size - 1
        t = threading.Thread(target=download_chunk, args=(URL, start, end, i, chunks))
        t.start()
        threads.append(t)
        time.sleep(0.5)  # stagger starts
    
    for t in threads:
        t.join()
    
    elapsed = time.time() - t0
    print(f'\nAll chunks downloaded in {elapsed:.0f}s ({size/1024/1024/elapsed:.1f}MB/s)')
    
    # Assemble
    with open(OUT, 'wb') as f:
        for i, chunk in enumerate(chunks):
            if chunk is None:
                print(f'ERROR: chunk {i} is None!')
                return
            f.write(chunk)
    
    actual = os.path.getsize(OUT)
    print(f'Written: {actual/1024/1024:.0f}MB (expected {size/1024/1024:.0f}MB)')
    if actual == size:
        print('✅ Download complete!')
    else:
        print('❌ Size mismatch!')

if __name__ == '__main__':
    main()
