#!/usr/bin/env python3
"""
IDM-VTON 模型逐文件下载器 - 支持断点续传+自动重试
通过代理下载，文件逐个下载以便跟踪进度
"""
import os
import sys
import requests
import time

PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
BASE_URL = "https://huggingface.co/yisol/IDM-VTON/resolve/main"
OUTPUT_DIR = os.path.join("models", "IDM-VTON")
MAX_RETRIES = 3
RETRY_DELAY = 10  # 重试间隔秒数
CHUNK_SIZE = 1024 * 1024  # 1MB

# 需要下载的文件列表 (relative_path, expected_size_approx)
FILES = [
    ("unet/diffusion_pytorch_model.bin", "~11.7GB"),
    ("unet_encoder/diffusion_pytorch_model.safetensors", "~10.3GB"),
    ("image_encoder/model.safetensors", "~3.44GB"),
    ("vae/diffusion_pytorch_model.safetensors", "~320MB"),
    ("text_encoder/model.safetensors", "~494MB"),
    ("densepose/densepose_r50_fpn_dl.pt", "~340MB"),
    ("humanparsing/parsing_atr.onnx", "~268MB"),
    ("humanparsing/parsing_lip.onnx", "~162MB"),
    ("openpose/ckpts/body_pose_model.pth", "~200MB"),
]


def download_file(rel_path, expected_size):
    """下载单个文件，支持断点续传+自动重试"""
    url = f"{BASE_URL}/{rel_path}"
    out_path = os.path.join(OUTPUT_DIR, rel_path)
    tmp_path = out_path + ".tmp"
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    # 检查是否已下载
    if os.path.exists(out_path):
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"  ✓ 已存在: {rel_path} ({size_mb:.1f}MB)")
        return True
    
    for attempt in range(1, MAX_RETRIES + 1):
        # 每次重试新建 session 避免连接复用问题
        session = requests.Session()
        session.proxies = PROXY
        
        try:
            # 检查断点
            resume_from = 0
            if os.path.exists(tmp_path):
                resume_from = os.path.getsize(tmp_path)
                if attempt == 1:
                    print(f"  ↻ 续传: {rel_path} 从 {resume_from/1024/1024:.1f}MB")
            
            headers = {}
            if resume_from > 0:
                headers["Range"] = f"bytes={resume_from}-"
            
            if attempt > 1:
                print(f"  ↻ 重试 {attempt}/{MAX_RETRIES}: {rel_path}", flush=True)
            
            resp = session.get(url, headers=headers, stream=True, timeout=(30, 120))
            
            if resume_from > 0 and resp.status_code == 200:
                # 服务器不支持 Range，从头下载
                resume_from = 0
            
            total = int(resp.headers.get("content-length", 0))
            if resume_from > 0:
                total += resume_from
            
            mode = "ab" if resume_from > 0 else "wb"
            downloaded = resume_from
            last_print = time.time()
            last_chunk_time = time.time()
            
            with open(tmp_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        last_chunk_time = time.time()
                        now = time.time()
                        if now - last_print >= 5:  # 每5秒打印一次
                            pct = (downloaded / total * 100) if total else 0
                            speed = CHUNK_SIZE / 1024 / 1024 / max(now - last_print, 0.001) * (downloaded - resume_from) / max(downloaded - resume_from, 1) if downloaded > resume_from else 0
                            print(f"    {rel_path}: {downloaded/1024/1024:.0f}MB / {total/1024/1024:.0f}MB ({pct:.1f}%)", flush=True)
                            last_print = now
            
            # 验证文件大小
            final_size = os.path.getsize(tmp_path)
            if total > 0 and final_size < total * 0.99:
                raise IOError(f"文件不完整: {final_size/1024/1024:.0f}MB < {total/1024/1024:.0f}MB")
            
            # 下载完成，重命名
            if os.path.exists(out_path):
                os.remove(out_path)
            os.rename(tmp_path, out_path)
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"  ✓ 完成: {rel_path} ({size_mb:.1f}MB)")
            return True
            
        except Exception as e:
            print(f"  ✗ 尝试 {attempt}/{MAX_RETRIES} 失败: {rel_path} - {e}", flush=True)
            if attempt < MAX_RETRIES:
                print(f"    等待 {RETRY_DELAY}s 后重试...", flush=True)
                time.sleep(RETRY_DELAY)
        finally:
            session.close()
    
    print(f"  ✗ 最终失败: {rel_path} (已重试 {MAX_RETRIES} 次)")
    return False


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    comfyui_dir = os.path.dirname(script_dir)
    os.chdir(comfyui_dir)
    
    print("=" * 60)
    print("IDM-VTON 模型下载器 (逐文件, 断点续传, 自动重试)")
    print(f"输出目录: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)
    
    # 多轮下载直到全部完成
    for round_num in range(1, 4):  # 最多3轮
        existing = []
        missing = []
        for rel_path, size in FILES:
            out_path = os.path.join(OUTPUT_DIR, rel_path)
            if os.path.exists(out_path):
                existing.append(rel_path)
            else:
                missing.append((rel_path, size))
        
        if not missing:
            print(f"\n🎉 所有文件已就绪!")
            break
        
        print(f"\n--- 第 {round_num} 轮 ---")
        print(f"已有: {len(existing)} 文件, 待下载: {len(missing)} 文件")
        
        for rel_path, size in missing:
            print(f"\n下载: {rel_path} ({size})")
            download_file(rel_path, size)
            time.sleep(3)  # 文件间间隔，让代理恢复
    
    # 最终检查
    print("\n" + "=" * 60)
    print("下载结果:")
    all_ok = True
    for rel_path, size in FILES:
        out_path = os.path.join(OUTPUT_DIR, rel_path)
        if os.path.exists(out_path):
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            print(f"  ✓ {rel_path} ({size_mb:.1f}MB)")
        else:
            tmp_path = out_path + ".tmp"
            if os.path.exists(tmp_path):
                tmp_mb = os.path.getsize(tmp_path) / 1024 / 1024
                print(f"  ⏳ {rel_path} (部分: {tmp_mb:.1f}MB)")
            else:
                print(f"  ✗ {rel_path} (缺失)")
            all_ok = False
    
    if all_ok:
        print("\n🎉 所有 IDM-VTON 模型下载完成!")
    else:
        print("\n⚠️ 部分文件未完成，重新运行脚本可继续下载")


if __name__ == "__main__":
    main()
