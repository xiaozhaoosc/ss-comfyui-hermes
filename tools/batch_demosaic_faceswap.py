#!/usr/bin/env python3
"""批量处理阮胺 A+B 类视频（去马赛克+换脸）"""
import subprocess, sys, os, time, json

SCRIPT = os.path.join(os.path.dirname(__file__), "demosaic_faceswap_v2.py")
INPUT_DIR = r"D:\ai_projects\ComfyUI\input\阮胺"
OUTPUT_DIR = r"D:\ai_projects\ComfyUI\output\ruanmin_batch"
FACE = r"D:\ai_projects\ComfyUI\input\face_swap_source.png"

# A类 白色圆形马赛克 + B类 黑白棋盘格
VIDEOS = [
    # (类型, 编号, 文件名)
    ("A", 6,  "14906835356189132879.mp4"),
    ("A", 10, "14915653360106539093.mp4"),
    ("A", 13, "14917052844319901792.mp4"),
    ("A", 18, "14923563449829558336.mp4"),
    ("A", 21, "14930835546356582470.mp4"),
    ("A", 26, "14934387144572602423.mp4"),
    ("A", 27, "14933689063711901755.mp4"),
    ("A", 28, "14935875608479598669.mp4"),
    ("A", 29, "14938798796741478484.mp4"),
    ("A", 30, "14944577300840778354_quality_720x1280.mp4"),
    ("B", 3,  "14913486584040261711.mp4"),
    ("B", 4,  "14905410362605111375.mp4"),
    ("B", 5,  "14910554805801388082.mp4"),
    ("B", 7,  "14908302364029618229.mp4"),
    ("B", 8,  "14911234162501486689.mp4"),
    ("B", 9,  "14912638572466341957.mp4"),
    ("B", 14, "我来啦.mp4"),
    ("B", 15, "14919943218349803596.mp4"),
]

os.makedirs(OUTPUT_DIR, exist_ok=True)

total = len(VIDEOS)
t0 = time.time()
results = []

for i, (typ, idx, fname) in enumerate(VIDEOS):
    inp = os.path.join(INPUT_DIR, fname)
    stem = os.path.splitext(fname)[0]
    out = os.path.join(OUTPUT_DIR, f"{idx:02d}_{typ}_{stem}_faceswap.mp4")

    # 跳过已完成的
    if os.path.exists(out) and os.path.getsize(out) > 10000:
        print(f"\n[{i+1}/{total}] #{idx:02d} [{typ}] 已存在，跳过")
        results.append((idx, typ, "skip", 0))
        continue

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
    results.append((idx, typ, status, elapsed))
    print(f"  → {status} ({elapsed:.0f}s)")

    # 进度汇总
    done = i + 1
    total_elapsed = time.time() - t0
    avg = total_elapsed / done
    eta = avg * (total - done)
    print(f"  进度: {done}/{total}, 已用: {total_elapsed/60:.1f}min, ETA: {eta/60:.1f}min")

# 最终汇总
total_elapsed = time.time() - t0
ok = sum(1 for _, _, s, _ in results if s in ("ok", "skip"))
err = sum(1 for _, _, s, _ in results if s not in ("ok", "skip"))
print(f"\n{'='*60}")
print(f"批量处理完成: {ok}/{total} 成功, {err} 失败")
print(f"总耗时: {total_elapsed/60:.1f}min")
print(f"输出目录: {OUTPUT_DIR}")
print(f"{'='*60}")
