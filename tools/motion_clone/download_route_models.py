#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
渲染路线 (Motion Clone) 缺失模型下载器
特性 (沿用 tools/download_wan22_animate.py 的成熟做法):
  - requests 下载
  - hf-mirror.com 优先, 失败自动回退 huggingface.co 原始域名
  - 多线程分段下载 (HTTP Range) + .partN 分片断点续传 (已存在的分片跳过, 不重下)
  - 网络异常自动重试, 不整体失败
  - 下载后按期望字节数严格校验
  - 小于 1MB 的文件走单线程直接下载 (对 JSON 分段没意义)
  - 已存在且字节数正确的文件直接跳过, 绝不覆盖
  - 已存在但字节数不符 => 警告并重新下载到 .part 后替换, 不用截断文件

用法:
  python tools/motion_clone/download_route_models.py --dry-run
  python tools/motion_clone/download_route_models.py
  python tools/motion_clone/download_route_models.py --threads 8
  python tools/motion_clone/download_route_models.py --only svd          # 只下路径含 "svd" 的
  python tools/motion_clone/download_route_models.py --only diffusers    # 只下路径含 "diffusers" 的
"""
import os
import sys
import time
import shutil
import argparse
import threading
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
MODELS_DIR = os.path.join(REPO_DIR, "models")

DEFAULT_THREADS = 8
MAX_RETRIES = 6
RETRY_DELAY = 8            # 分段重试等待秒数
CHUNK = 1024 * 1024        # 1MB
SMALL_FILE_LIMIT = 1024 * 1024   # 小于 1MB 的文件用单线程直接下载

SVD_PREFIX = "diffusers/stable-video-diffusion-img2vid-xt-1-1"
SVD_REPO = "https://hf-mirror.com/vdo/stable-video-diffusion-img2vid-xt-1-1/resolve/main"

# (相对 models/ 的路径, hf-mirror 源 URL, 期望字节数; None 表示运行时用 HEAD 动态获取)
FILES = [
    (
        "checkpoints/v1-5-pruned-emaonly.safetensors",
        "https://hf-mirror.com/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/"
        "v1-5-pruned-emaonly.safetensors",
        4265146304,
    ),
    (
        "animatediff_models/v3_sd15_mm.ckpt",
        "https://hf-mirror.com/guoyww/animatediff/resolve/main/v3_sd15_mm.ckpt",
        None,   # 运行时 HEAD 读取
    ),
    (
        "controlnet/control_v11p_sd15_openpose.pth",
        "https://hf-mirror.com/lllyasviel/ControlNet-v1-1/resolve/main/"
        "control_v11p_sd15_openpose.pth",
        1445235707,
    ),
    (
        "mimicmotion/MimicMotionMergedUnet_1-1-fp16.safetensors",
        "https://hf-mirror.com/Kijai/MimicMotion_pruned/resolve/main/"
        "MimicMotionMergedUnet_1-1-fp16.safetensors",
        3049435868,
    ),
    # ---- SVD XT 1.1 的 7 个文件 (源仓库非 gated, 无需 HF token) ----
    (f"{SVD_PREFIX}/model_index.json", f"{SVD_REPO}/model_index.json", None),
    (f"{SVD_PREFIX}/vae/config.json", f"{SVD_REPO}/vae/config.json", None),
    (f"{SVD_PREFIX}/vae/diffusion_pytorch_model.fp16.safetensors",
     f"{SVD_REPO}/vae/diffusion_pytorch_model.fp16.safetensors", None),
    (f"{SVD_PREFIX}/image_encoder/config.json", f"{SVD_REPO}/image_encoder/config.json", None),
    (f"{SVD_PREFIX}/image_encoder/model.fp16.safetensors",
     f"{SVD_REPO}/image_encoder/model.fp16.safetensors", None),
    (f"{SVD_PREFIX}/scheduler/scheduler_config.json",
     f"{SVD_REPO}/scheduler/scheduler_config.json", None),
    (f"{SVD_PREFIX}/feature_extractor/preprocessor_config.json",
     f"{SVD_REPO}/feature_extractor/preprocessor_config.json", None),
]


def gb(n):
    return n / 1024 / 1024 / 1024


def fmt_size(n):
    """人类可读的字节数"""
    if n is None:
        return "未知"
    if n >= 1024 * 1024 * 1024:
        return f"{gb(n):.2f} GB ({n} B)"
    if n >= 1024 * 1024:
        return f"{n/1024/1024:.2f} MB ({n} B)"
    if n >= 1024:
        return f"{n/1024:.1f} KB ({n} B)"
    return f"{n} B"


def candidate_urls(url):
    """返回 [镜像URL, 原始域名URL(如有)]"""
    urls = [url]
    if "hf-mirror.com" in url:
        urls.append(url.replace("hf-mirror.com", "huggingface.co"))
    return urls


def head_size(url):
    """
    用 HEAD (跟随重定向) 读取文件大小。
    优先 x-linked-size (hf-mirror 对 LFS 文件会带该头), 其次 Content-Length。
    取不到返回 None。
    """
    for u in candidate_urls(url):
        try:
            r = requests.head(u, timeout=(30, 60), allow_redirects=True)
            try:
                if r.status_code != 200:
                    continue
                for h in ("x-linked-size", "Content-Length", "content-length"):
                    v = r.headers.get(h)
                    if v and str(v).isdigit():
                        return int(v)
            finally:
                r.close()
        except Exception:
            continue
    return None


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
    """依次探测各候选 URL, 返回第一个可用的 (url, total, ranges)"""
    for u in urls:
        status, total, ranges = probe(u)
        if status in (200, 206) and total:
            print(f"    [probe] OK {u}  status={status} size={gb(total):.2f}GB ranges={ranges}", flush=True)
            return u, total, ranges
        print(f"    [probe] FAIL {u}  status={status} info={total}", flush=True)
    return None, None, False


def download_segment(url, seg_start, seg_end, part_path, idx, results):
    """下载闭区间 [seg_start, seg_end] 到 part_path, 支持断点续传 (已写够则跳过)"""
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


def monitor(stop_evt, total, part_paths, label):
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
        print(f"    [{label}] {gb(done):.2f}/{gb(total):.2f} GB ({pct:.1f}%)  "
              f"{speed/1024/1024:.1f} MB/s", flush=True)


def download_single(url, dest, seg_total, label):
    """单线程直接下载 (用于 <1MB 的小文件), 通过 .part 文件支持断点续传"""
    part_path = f"{dest}.part"
    have = os.path.getsize(part_path) if os.path.exists(part_path) else 0
    if seg_total is not None and have >= seg_total:
        if os.path.exists(dest):
            os.remove(dest)
        os.replace(part_path, dest)
        return True

    for attempt in range(1, MAX_RETRIES + 1):
        have = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        headers = {}
        if have > 0:
            headers["Range"] = f"bytes={have}-"
        try:
            r = requests.get(url, headers=headers, stream=True,
                             timeout=(30, 120), allow_redirects=True)
            if r.status_code not in (200, 206):
                r.close()
                raise IOError(f"HTTP {r.status_code}")
            mode = "ab" if have > 0 else "wb"
            with open(part_path, mode) as f:
                for chunk in r.iter_content(CHUNK):
                    if chunk:
                        f.write(chunk)
            r.close()
            got = os.path.getsize(part_path)
            if seg_total is not None and got != seg_total:
                raise IOError(f"大小不符 {got}/{seg_total}")
            if os.path.exists(dest):
                os.remove(dest)
            os.replace(part_path, dest)
            return True
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"    [single] 尝试 {attempt}/{MAX_RETRIES} 失败: {e}; "
                      f"{RETRY_DELAY}s 后重试", flush=True)
                time.sleep(RETRY_DELAY)
            else:
                print(f"    [single] 最终失败: {e}", flush=True)
                return False
    return False


def download_one(rel_path, url, expected, threads):
    """
    下载单个文件。
    返回 (ok: bool, actual_size: int|0, expected: int|None)
    """
    dest = os.path.join(MODELS_DIR, rel_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    label = os.path.basename(dest)

    # 1) 已存在校验: 字节数正确 => 跳过, 绝不覆盖
    if os.path.exists(dest):
        sz = os.path.getsize(dest)
        if expected is None:
            # 期望值未知时, 先尝试用 HEAD 补读期望大小以便真正校验 (取不到则记为未知)
            hs = head_size(url)
            if hs is None:
                print(f"  ✓ 已存在 (期望未知), 跳过: {rel_path}  ({fmt_size(sz)})", flush=True)
                return True, sz, expected
            expected = hs
        if sz == expected:
            print(f"  ✓ 已存在且大小正确, 跳过: {rel_path}  ({fmt_size(sz)})", flush=True)
            return True, sz, expected
        print(f"  ! 已存在但字节数不符 (实际={sz} 期望={expected}), 重新下载: {rel_path}", flush=True)

    # 2) 选择可用 URL (带回退)
    working, total, ranges = pick_working_url(candidate_urls(url))
    if not working:
        print(f"  ✗ 所有源不可用: {rel_path}", flush=True)
        return False, 0, expected

    # 若期望值未知, 用探测到的大小补齐
    if expected is None and total:
        expected = total

    # 3) 小文件走单线程
    if expected is not None and expected < SMALL_FILE_LIMIT:
        print(f"  → 小文件 ({fmt_size(expected)}), 单线程直接下载: {rel_path}", flush=True)
        ok = download_single(working, dest, expected, label)
        sz = os.path.getsize(dest) if os.path.exists(dest) else 0
        if ok:
            print(f"  ✓ 完成: {rel_path}  ({fmt_size(sz)})", flush=True)
        return ok, sz, expected

    # 4) 分配分段
    nparts = max(1, threads if ranges else 1)
    # 清理可能残留的旧分段 (分段数变化时)
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

    # 5) 并发下载 (已存在分片自动续传)
    print(f"  → 分段下载 ({nparts} 线程, {fmt_size(total)}): {rel_path}", flush=True)
    results = [False] * nparts
    stop_evt = threading.Event()
    mon = threading.Thread(target=monitor, args=(stop_evt, total, part_paths, label), daemon=True)
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

    # 6) 全部分段成功才合并, 否则保留 .partN 便于下次续传
    if not all(results):
        failed = [str(i) for i, ok in enumerate(results) if not ok]
        print(f"  ✗ {rel_path} 存在失败分段 {failed}, 保留 .partN 便于续传", flush=True)
        return False, 0, expected

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

    # 7) 校验大小
    sz = os.path.getsize(dest)
    if expected is not None and sz != expected:
        print(f"  ✗ 大小不一致: {rel_path} 实际={sz} 期望={expected}", flush=True)
        return False, sz, expected
    print(f"  ✓ 完成: {rel_path}  ({fmt_size(sz)})", flush=True)
    return True, sz, expected


def precheck(title):
    print("=" * 78)
    print(f"  {title}")
    print(f"  models 目录: {MODELS_DIR}")
    print("=" * 78)


def select_files(only):
    if not only:
        return FILES
    return [f for f in FILES if only in f[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印计划, 不下载")
    ap.add_argument("--only", default=None, help="只处理目标路径含该子串的文件")
    ap.add_argument("--threads", type=int, default=DEFAULT_THREADS, help="每个文件的分段线程数")
    args = ap.parse_args()

    files = select_files(args.only)
    if not files:
        print(f"没有匹配 --only={args.only!r} 的文件。")
        sys.exit(1)

    precheck("渲染路线 (Motion Clone) 缺失模型下载器")
    print(f"  分段线程数: {args.threads}")
    if args.only:
        print(f"  过滤条件  : --only {args.only!r} (命中 {len(files)}/{len(FILES)} 项)")
    else:
        print(f"  文件总数  : {len(files)}")
    print("=" * 78)

    # ---------------- dry-run: 只打印计划 ----------------
    if args.dry_run:
        total_expect = 0
        unknown = 0
        print(f"\n{'目标相对路径':<62} {'期望字节数':>14}  {'已存在':<6} {'实际字节数':>14}")
        print("-" * 110)
        for rel_path, url, expected in files:
            dest = os.path.join(MODELS_DIR, rel_path)
            exists = os.path.exists(dest)
            actual = os.path.getsize(dest) if exists else 0
            exp_disp = str(expected) if expected is not None else "HEAD 动态读取"
            if expected is not None:
                total_expect += expected
            else:
                unknown += 1
            short = rel_path if len(rel_path) <= 60 else "..." + rel_path[-57:]
            print(f"{short:<62} {exp_disp:>14}  {'是' if exists else '否':<6} {actual:>14}")
            print(f"    源: {url}")
        print("-" * 110)

        # 对未知大小做 HEAD 探测并汇总
        if unknown:
            print(f"\n  正在用 HEAD 探测 {unknown} 个未知大小的文件 ...", flush=True)
            for rel_path, url, expected in files:
                if expected is not None:
                    continue
                sz = head_size(url)
                dest = os.path.join(MODELS_DIR, rel_path)
                exists = os.path.exists(dest)
                actual = os.path.getsize(dest) if exists else 0
                if sz:
                    total_expect += sz
                    print(f"  [HEAD] {rel_path} -> {sz} B ({gb(sz):.3f} GB)")
                else:
                    print(f"  [HEAD] {rel_path} -> 取不到大小 (记为未知, 下载后只报实际值)")
                print(f"         已存在={'是' if exists else '否'} 实际={actual}")

        du = shutil.disk_usage(dest_root())
        print(f"\n  合计大小(已知部分) : {fmt_size(total_expect)}")
        print(f"  目标盘剩余空间     : {fmt_size(du.free)}")
        if total_expect > du.free:
            print("  ! 警告: 预估合计大小已超过目标盘剩余空间!")
        print("  (以上为 --dry-run 计划, 未执行任何下载)")
        return

    # ---------------- 真实下载 ----------------
    results = []
    for rel_path, url, expected in files:
        print(f"\n>>> {rel_path}", flush=True)
        ok, sz, exp = download_one(rel_path, url, expected, args.threads)
        results.append((rel_path, ok, sz, exp))

    # ---------------- 结束校验表 ----------------
    print("\n" + "=" * 78)
    print("  校验汇总 (文件 / 实际字节数 / 期望字节数 / 结论)")
    print("=" * 78)
    all_ok = True
    mismatched = []   # 期望已知但字节数不符 => 致命
    unknown = []      # 期望取不到 => 只提示, 不做严格校验, 不算失败
    for rel_path, ok, sz, exp in results:
        if exp is None:
            concl = "未知"
            unknown.append(rel_path)
        elif sz == exp:
            concl = "OK"
        else:
            concl = "不符"
            all_ok = False
            mismatched.append((rel_path, sz, exp))
        print(f"  [{concl}] {rel_path}\n           实际={sz}  期望={exp}")
    print("=" * 78)
    if not all_ok:
        print("  ! 存在字节数不符的文件:")
        for rel_path, sz, exp in mismatched:
            print(f"    - {rel_path}  实际={sz} 期望={exp}")
        print("  重新运行本脚本可断点续传 (已存在的分片/文件会被跳过)。")
        sys.exit(1)
    if unknown:
        print("  ! 以下文件期望大小未知, 仅报实际值, 未做严格校验:")
        for rel_path in unknown:
            print(f"    - {rel_path}")
    print("  全部文件就绪。")


def dest_root():
    """目标盘根目录 (models 实际落 D 盘 Junction, 这里取真实盘)"""
    return os.path.splitdrive(os.path.realpath(MODELS_DIR))[0] + os.sep


if __name__ == "__main__":
    main()