#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仅换装批量编排（不动人脸）- 2026-10-11
对 output/2026-10-11_wb 顶层视频（_trim 优先）逐个调用 pipeline_faceswap_outfit.py
的六段式管线（--skip-faceswap），实现：抽帧 → ATR 护脸遮罩 → IDM-VTON 换装关键帧
→ 光流插值 → ffmpeg 合成（保留原音频）。

用法:
  # 只看收集计划（不需要服装参数）
  python tools/outfit_only_batch.py --dry-run

  # 正式运行（需要服装图 + 英文描述）
  python tools/outfit_only_batch.py --garment path/to/garment.jpg --garment-desc "..."
"""
import argparse
import os
import re
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(SCRIPT_DIR, "pipeline_faceswap_outfit.py")
PY = sys.executable or r"C:\Users\kenzhao\anaconda3\python.exe"

TRIM_RE = re.compile(r"^(?P<base>.+)_00001__trim\.mp4$", re.IGNORECASE)
RAW_RE = re.compile(r"^(?P<base>.+)_00001_\.mp4$", re.IGNORECASE)


def collect_videos(src_dir):
    """收集顶层视频，同 base 下 _trim 优先，返回 [(video_path, base_name)]"""
    files = [f for f in os.listdir(src_dir) if f.lower().endswith(".mp4")]
    trims, raws = {}, {}
    for f in files:
        m = TRIM_RE.match(f)
        if m:
            trims[m.group("base")] = f
            continue
        m = RAW_RE.match(f)
        if m:
            raws.setdefault(m.group("base"), f)
    pairs = []
    for base, f in sorted(trims.items()):
        pairs.append((os.path.join(src_dir, f), base))
    for base, f in sorted(raws.items()):
        if base not in trims:  # 无 trim 才用原版
            pairs.append((os.path.join(src_dir, f), base))
    return pairs


def main():
    ap = argparse.ArgumentParser(description="仅换装批量编排")
    ap.add_argument("--dir", default=r"D:\ai_projects\ComfyUI\output\2026-10-11_wb",
                    help="源视频目录（只取顶层 mp4）")
    ap.add_argument("--garment", default=None, help="目标服装图片（正式运行必填）")
    ap.add_argument("--garment-desc", default=None, help="英文服装描述（正式运行必填）")
    ap.add_argument("--out", default=r"D:\ai_projects\ComfyUI\output\2026-10-11\outfit_only",
                    help="输出根目录")
    ap.add_argument("--keyframe-interval", type=float, default=2.0,
                    help="关键帧间隔秒数（默认 2.0，约 4-5 帧/视频）")
    ap.add_argument("--steps", type=int, default=15, help="IDM-VTON 步数（默认 15 加速档）")
    ap.add_argument("--protect-expand", type=int, default=5)
    ap.add_argument("--feather", type=int, default=3)
    ap.add_argument("--comfy-port", type=int, default=8188)
    ap.add_argument("--only", default=None, help="只处理 base 名包含该子串的视频")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    args = ap.parse_args()

    src_dir = os.path.abspath(args.dir)
    if not os.path.isdir(src_dir):
        print(f"❌ 源目录不存在: {src_dir}")
        sys.exit(1)
    if not args.dry_run and (not args.garment or not os.path.isfile(args.garment)):
        print(f"❌ 正式运行需要 --garment 指向存在的服装图")
        sys.exit(1)

    pairs = collect_videos(src_dir)
    if args.only:
        pairs = [(v, b) for v, b in pairs if args.only in b]
    out_root = os.path.abspath(args.out)
    os.makedirs(out_root, exist_ok=True)

    print("=" * 60)
    print(f"🎽 仅换装批量编排 | 源: {src_dir}")
    print(f"   视频: {len(pairs)} 个 | 关键帧间隔 {args.keyframe_interval}s | steps {args.steps}")
    if args.garment:
        print(f"   服装: {args.garment} ({args.garment_desc})")
    for i, (v, b) in enumerate(pairs, 1):
        print(f"   [{i:02d}] {os.path.basename(v)}")
    print("=" * 60)
    if args.dry_run:
        print("✅ dry-run 完成")
        return

    failed, t_all = [], time.time()
    for i, (video, base) in enumerate(pairs, 1):
        # 工作目录必须纯 ASCII：cv2.imread/imwrite 在 Windows 不支持非 ASCII 路径
        # base 形如 "wanB_00__中文标题"，取 __ 前编号（wanB_XX 全局唯一）作目录名
        safe = base.split("__")[0] if "__" in base else re.sub(r"[^0-9A-Za-z_\-]", "_", base)[:60]
        out_dir = os.path.join(out_root, safe)
        print(f"\n[{i}/{len(pairs)}] 🎬 {base}")
        cmd = [
            PY, "-u", PIPELINE, "run",
            "--video", video,
            "--skip-faceswap",
            "--garment", args.garment,
            "--garment-desc", args.garment_desc or "garment",
            "--output-dir", out_dir,
            "--output-name", f"{base}_outfit.mp4",
            "--keyframe-interval", str(args.keyframe_interval),
            "--steps", str(args.steps),
            "--protect-expand", str(args.protect_expand),
            "--feather", str(args.feather),
            "--comfy-port", str(args.comfy_port),
        ]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"[{i}/{len(pairs)}] ❌ 失败: {base}（断点已存，重跑续传）")
            failed.append(base)
        else:
            print(f"[{i}/{len(pairs)}] ✅ {base}")

    print("\n" + "=" * 60)
    print(f"🏁 全部完成 {time.time()-t_all:.0f}s | 失败 {len(failed)}/{len(pairs)}: {failed or '无'}")
    print(f"输出根目录: {out_root}")
    if failed:
        sys.exit(2)


if __name__ == "__main__":
    main()
