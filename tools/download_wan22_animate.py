#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wan2.2 Animate 14B (FP8) 模型下载器
特性:
  - 多线程分段下载 (HTTP Range)
  - 断点续传 (每个分段独立续传, 生成 .partN 临时文件)
  - 自动重试
  - hf-mirror.com 失败后自动回退 huggingface.co 原始域名
  - 已下载完成则跳过, 并按期望大小做完整性校验

用法:
  python tools/download_wan22_animate.py
  python tools/download_wan22_animate.py --threads 8
"""
import os
import sys
import time
import argparse
import threading
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
MODELS_DIR = os.path.join(REPO_DIR, "models")

DEFAULT_THREADS = 8
MAX_RETRIES = 6
RETRY_DELAY = 8          # 分段重试等待秒数
CHUNK = 1024 * 1024      # 1MB
SIZE_TOLERANCE = 0.90    # 已存在文件的完整性下限(相对期望大小)

# (相对 models/ 的路径, hf-mirror 源 URL, 期望字节数)
FILES = [
    (
        "diffusion_models/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
        "https://hf-mirror.com/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/"
        "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
        14_300_000_000,
    ),
    (
        "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "https://hf-mirror.com/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/"
        "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        6_700_000_000,
    ),
    (
        "clip_vision/clip_vision_h.safetensors",
        "https://hf-mirror.com/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/"
        "clip_vision/clip_vision_h.safetensors",
        1_300_000_000,
    ),
    (
        "vae/wan_2.1_vae.safetensors",
        "https://hf-mirror.com/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/"
        "vae/wan_2.1_vae.safetensors",
        240_000_000,
    ),
    (
        "loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        "https://hf-mirror.com/Kijai/WanVideo_comfy/resolve/main/Lightx2v/"
        "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        1_100_000_000,
    ),
    # 官方模板的 LoraLoaderModelOnly(id=99) 还引用了该 relight LoRA, 缺它模板无法加载
    (
        "loras/WanAnimate_relight_lora_fp16.safetensors",
        "https://hf-mirror.com/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/"
        "WanAnimate_relight_lora_fp16.safetensors",
        1_340_000_000,
    ),
]


def gb(n):
    return n / 1024 / 1024 / 1024


def candidate_urls(url):
    """返回 [镜像URL, 原始域名URL(如有)]"""
    urls = [url]
    if "hf-mirror.com" in url:
        urls.append(url.replace("hf-mirror.com", "huggingface.co"))
    return urls


def probe(url):
    """返回 (status, total_size, accept_ranges)"""
    try:
        r = requests.get(url, headers={"Range": "bytes=0-0"}, stream=True,
                         timeout=(30, 60), allow_redirects=True)
        try:
            if r.status_code == 206:
                cr = r.headers.get("Content-Range", "")
                total = int(cr.split("/")[-1])
                return r.status_code, total, True
            if r.status_code == 200:
                return r.status_code, int(r.headers.get("Content-Length", 0)), False
            return r.status_code, None, False
        finally:
            r.close()
    except Exception as e:
        return None, str(e), False


def pick_working_url(urls):
    for u in urls:
        status, total, ranges = probe(u)
        if status in (200, 206) and total:
            print(f"    [probe] OK {u}  status={status} size={gb(total):.2f}GB ranges={ranges}", flush=True)
            return u, total, ranges
        print(f"    [probe] FAIL {u}  status={status} info={total}", flush=True)
    return None, None, False


def download_segment(url, seg_start, seg_end, part_path, idx, results):
    """下载闭区间 [seg_start, seg_end] 到 part_path, 支持断点续传"""
    seg_len = seg_end - seg_start + 1
    for attempt in range(1, MAX_RETRIES + 1):
        have = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        if have >= seg_len:
            results[idx] = True
            return
        cur = seg_start + have
        headers = {"Range": f"bytes={cur}-{seg_end}"}
        try:
            r = requests.get(url, headers=headers, stream=True,
                             timeout=(30, 120), allow_redirects=True)
            if r.status_code not in (200, 206):
                r.close()
                raise IOError(f"HTTP {r.status_code}")
            mode = "ab" if have > 0 else "wb"
            written = have
            with open(part_path, mode) as f:
                for chunk in r.iter_content(CHUNK):
                    if not chunk:
                        continue
                    remaining = seg_len - written
                    if len(chunk) > remaining:
                        chunk = chunk[:remaining]
                    f.write(chunk)
                    written += len(chunk)
                    if written >= seg_len:
                        break
            r.close()
            if os.path.getsize(part_path) >= seg_len:
                results[idx] = True
                return
            raise IOError(f"分段不完整 {os.path.getsize(part_path)}/{seg_len}")
        except Exception as e:
            results[idx] = False
            if attempt < MAX_RETRIES:
                print(f"    [seg{idx}] 尝试 {attempt}/{MAX_RETRIES} 失败: {e}; {RETRY_DELAY}s 后重试", flush=True)
                time.sleep(RETRY_DELAY)
            else:
                print(f"    [seg{idx}] 最终失败: {e}", flush=True)


def monitor(stop_evt, dest, total, nparts, part_paths, label):
    """进度打印线程"""
    last = 0
    last_t = time.time()
    while not stop_evt.is_set():
        time.sleep(5)
        try:
            done = sum(os.path.getsize(p) for p in part_paths if os.path.exists(p))
        except OSError:
            done = 0
        now = time.time()
        speed = (done - last) / max(now - last_t, 0.001)
        last, last_t = done, now
        pct = done / total * 100 if total else 0
        print(f"    [{label}] {gb(done):.2f}/{gb(total):.2f} GB ({pct:.1f}%)  {speed/1024/1024:.1f} MB/s", flush=True)


def download_one(rel_path, url, approx_bytes, threads):
    dest = os.path.join(MODELS_DIR, rel_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    label = os.path.basename(dest)

    # 1) 已存在校验
    if os.path.exists(dest):
        sz = os.path.getsize(dest)
        if sz >= approx_bytes * SIZE_TOLERANCE:
            print(f"  ✓ 已存在, 跳过: {rel_path}  ({gb(sz):.2f} GB)", flush=True)
            return True, sz
        print(f"  ! 已存在但偏小({gb(sz):.2f}GB < {gb(approx_bytes):.2f}GB), 重新下载: {rel_path}", flush=True)

    # 2) 选择可用 URL
    working, total, ranges = pick_working_url(candidate_urls(url))
    if not working:
        print(f"  ✗ 所有源不可用: {rel_path}", flush=True)
        return False, 0

    # 3) 分配分段
    nparts = max(1, threads if ranges else 1)
    # 清理可能残留的旧分段(分段数变化时)
    for i in range(nparts, nparts + 16):
        p = f"{dest}.part{i}"
        if os.path.exists(p):
            os.remove(p)
    part_paths = [f"{dest}.part{i}" for i in range(nparts)]
    seg = total // nparts
    bounds = []
    for i in range(nparts):
        s = i * seg
        e = (total - 1) if i == nparts - 1 else (s + seg - 1)
        bounds.append((s, e))

    # 4) 并发下载
    results = [False] * nparts
    stop_evt = threading.Event()
    mon = threading.Thread(target=monitor, args=(stop_evt, dest, total, nparts, part_paths, label), daemon=True)
    mon.start()
    workers = []
    for i in range(nparts):
        t = threading.Thread(target=download_segment,
                             args=(working, bounds[i][0], bounds[i][1], part_paths[i], i, results))
        t.start()
        workers.append(t)
    for t in workers:
        t.join()
    stop_evt.set()
    time.sleep(0.1)

    # 5) 分段合并
    if not all(results):
        failed = [str(i) for i, ok in enumerate(results) if not ok]
        print(f"  ✗ {rel_path} 存在失败分段 {failed}, 保留 .partN 便于续传", flush=True)
        return False, 0

    with open(dest, "wb") as out:
        for p in part_paths:
            with open(p, "rb") as f:
                while True:
                    buf = f.read(8 * 1024 * 1024)
                    if not buf:
                        break
                    out.write(buf)
    for p in part_paths:
        try:
            os.remove(p)
        except OSError:
            pass

    # 6) 校验大小
    sz = os.path.getsize(dest)
    if total and sz != total:
        print(f"  ✗ 大小不一致: {rel_path} 实际={sz} 期望={total}", flush=True)
        return False, sz
    print(f"  ✓ 完成: {rel_path}  ({gb(sz):.2f} GB)", flush=True)
    return True, sz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=DEFAULT_THREADS, help="每个文件的分段线程数")
    args = ap.parse_args()

    print("=" * 70)
    print("  Wan2.2 Animate 14B (FP8) 模型下载器")
    print(f"  models 目录: {MODELS_DIR}")
    print(f"  分段线程数: {args.threads}")
    print("=" * 70)

    # 确保 clip_vision 目录存在
    os.makedirs(os.path.join(MODELS_DIR, "clip_vision"), exist_ok=True)

    results = []
    for rel_path, url, approx in FILES:
        print(f"\n>>> {rel_path}", flush=True)
        ok, sz = download_one(rel_path, url, approx, args.threads)
        results.append((rel_path, ok, sz))

    print("\n" + "=" * 70)
    print("  下载汇总")
    print("=" * 70)
    all_ok = True
    for rel_path, ok, sz in results:
        status = "OK " if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status}] {rel_path}  {gb(sz):.2f} GB")
    print("=" * 70)
    if not all_ok:
        print("  部分文件失败, 重新运行本脚本可断点续传。")
        sys.exit(1)
    print("  全部文件就绪。")


if __name__ == "__main__":
    main()
