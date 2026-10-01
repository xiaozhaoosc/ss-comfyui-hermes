#!/usr/bin/env python3
"""重试失败的视频"""
import subprocess, sys, os, time

SCRIPT = os.path.join(os.path.dirname(__file__), "demosaic_faceswap_v2.py")
INPUT_DIR = r"D:\ai_projects\ComfyUI\input\阮胺"
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\ruanmin_batch"
FACE = r"D:\ai_projects\ComfyUI\input\face_swap_source.png"

FAILED = [
    ("A", 13, "14917052844319901792.mp4"),
    ("A", 18, "14923563449829558336.mp4"),
    ("A", 26, "14934387144572602423.mp4"),
    ("A", 28, "14935875608479598669.mp4"),
    ("A", 29, "14938798796741478484.mp4"),
    ("B", 14, "我来啦.mp4"),
]

total = len(FAILED)
t0 = time.time()

for i, (typ, idx, fname) in enumerate(FAILED):
    inp = os.path.join(INPUT_DIR, fname)
    stem = os.path.splitext(fname)[0]
    out = os.path.join(OUTPUT_DIR, f"{idx:02d}_{typ}_{stem}_faceswap.mp4")

    # 清理旧work目录强制重处理
    work_dir = os.path.join(OUTPUT_DIR, f"_work_{stem}")
    for subdir in ["telea", "demosaiced", "final"]:
        d = os.path.join(work_dir, subdir)
        if os.path.exists(d):
            import shutil
            shutil.rmtree(d)

    print(f"\n{'='*60}")
    print(f"[{i+1}/{total}] #{idx:02d} [{typ}] {fname}")
    print(f"{'='*60}")

    t1 = time.time()
    proc = subprocess.run([
        sys.executable, SCRIPT,
        "--input", inp,
        "--face", FACE,
        "--output", out,
        "--keyframe-fps", "1",
        "--denoise", "0.75",
        "--seed", str(42 + idx * 10),
    ], capture_output=False, text=True)

    elapsed = time.time() - t1
    status = "ok" if proc.returncode == 0 else f"err({proc.returncode})"
    print(f"  → {status} ({elapsed:.0f}s)")

total_elapsed = time.time() - t0
print(f"\n重试完成，总耗时: {total_elapsed/60:.1f}min")
