#!/usr/bin/env python3
"""优化重试6个失败视频：NS填充 + 高denoise + 重命名"""
import subprocess, sys, os, time, shutil

SCRIPT = os.path.join(os.path.dirname(__file__), "demosaic_faceswap_v2.py")
INPUT_DIR = r"D:\ai_projects\ComfyUI\input\阮胺"
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\ruanmin_batch"
FACE = r"D:\ai_projects\ComfyUI\input\face_swap_source.png"

# 优化策略：NS填充 + denoise=0.85 + 不同seed
RETRY = [
    # (类型, 编号, 文件名, denoise, inpaint_method)
    ("A", 13, "14917052844319901792.mp4", 0.85, "ns"),
    ("A", 18, "14923563449829558336.mp4", 0.85, "ns"),
    ("A", 26, "14934387144572602423.mp4", 0.85, "ns"),
    ("A", 28, "14935875608479598669.mp4", 0.85, "ns"),
    ("A", 29, "14938798796741478484.mp4", 0.85, "ns"),
    ("B", 14, "1491994321834980_wolai.mp4", 0.75, "telea"),  # 纯ASCII文件名
]

total = len(RETRY)
t0 = time.time()
results = []

for i, (typ, idx, fname, denoise, method) in enumerate(RETRY):
    inp = os.path.join(INPUT_DIR, fname)
    stem = os.path.splitext(fname)[0]
    out = os.path.join(OUTPUT_DIR, f"{idx:02d}_{typ}_{stem}_faceswap.mp4")

    # 清理旧中间结果
    work_dir = os.path.join(OUTPUT_DIR, f"_work_{stem}")
    for subdir in ["telea", "demosaiced", "final"]:
        d = os.path.join(work_dir, subdir)
        if os.path.exists(d):
            shutil.rmtree(d)

    print(f"\n{'='*60}")
    print(f"[{i+1}/{total}] #{idx:02d} [{typ}] denoise={denoise} method={method}")
    print(f"{'='*60}")

    t1 = time.time()
    proc = subprocess.run([
        sys.executable, SCRIPT,
        "--input", inp,
        "--face", FACE,
        "--output", out,
        "--keyframe-fps", "1",
        "--denoise", str(denoise),
        "--inpaint-method", method,
        "--seed", str(42 + idx * 10),
    ], capture_output=False, text=True)

    elapsed = time.time() - t1
    status = "ok" if proc.returncode == 0 else f"err({proc.returncode})"
    results.append((idx, typ, status, elapsed))
    print(f"  → {status} ({elapsed:.0f}s)")

total_elapsed = time.time() - t0
ok = sum(1 for _, _, s, _ in results if s == "ok")
print(f"\n{'='*60}")
print(f"优化重试完成: {ok}/{total} 成功, 总耗时: {total_elapsed/60:.1f}min")
print(f"{'='*60}")
