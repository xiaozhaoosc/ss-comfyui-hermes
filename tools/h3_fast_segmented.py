#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H3 4 步快线 · 多段短段生成 + 首尾帧衔接 + 拼接（本地串联作业）

默认：3 段 × 73 帧（3.04s）@ 544×960，段间"上段末帧 → 下段首帧"衔接，
全部走 4 步快线工作流；最后拼成整片（视频 + 音频同步处理）。

拼接模式（--transition）：
  cut       硬切 concat：无交叉叠影；段已由首尾帧衔接，接缝最干净（默认，推荐）
  crossfade xfade 交叉溶解 + 音频 acrossfade：注意两段画面未严格对齐时会有双重曝光鬼影

本脚本内部轮询 ComfyUI（纯本地进程，不依赖外部等待/通知）。
用法:
  python tools/h3_fast_segmented.py --dry-run          # 只校验不跑
  python tools/h3_fast_segmented.py                     # 3 段 ≈9s
  python tools/h3_fast_segmented.py --segments 5 --seg-len 73 --width 736 --height 1088
  python tools/h3_fast_segmented.py --merge-only        # 跳过生成，重拼已存在的分段
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h3_fast_submit as base

FFMPEG_ABS = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"
FFPROBE_ABS = r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"
TMP_FRAMES_DIR = os.path.join(base.INPUT_ROOT, "xinniang_v3_frames")


def ffmpeg_exe():
    return FFMPEG_ABS if os.path.exists(FFMPEG_ABS) else "ffmpeg"


def ffprobe_exe():
    return FFPROBE_ABS if os.path.exists(FFPROBE_ABS) else "ffprobe"


def probe_duration(mp4):
    r = subprocess.run([ffprobe_exe(), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", mp4],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def probe_nb_frames(mp4):
    """取视频流帧数（nb_frames）；缺失时退回解码计数。"""
    r = subprocess.run([ffprobe_exe(), "-v", "error", "-select_streams", "v",
                        "-show_entries", "stream=nb_frames",
                        "-of", "default=noprint_wrappers=1:nokey=1", mp4],
                       capture_output=True, text=True)
    try:
        n = int(r.stdout.strip())
        if n > 0:
            return n
    except Exception:
        pass
    return len(read_frames(mp4))


def probe_fps(mp4):
    """取视频流帧率（如 24）。"""
    r = subprocess.run([ffprobe_exe(), "-v", "error", "-select_streams", "v",
                        "-show_entries", "stream=r_frame_rate",
                        "-of", "default=noprint_wrappers=1:nokey=1", mp4],
                       capture_output=True, text=True)
    try:
        num, den = r.stdout.strip().split("/")
        v = float(num) / float(den)
        return v if v > 0 else 24.0
    except Exception:
        return 24.0


def read_frames(mp4):
    """用 OpenCV 解码整段为 BGR 帧列表（分段很短，全解码最稳）。"""
    import cv2
    cap = cv2.VideoCapture(mp4)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
    cap.release()
    return frames


def mean_abs_diff(a, b):
    """两帧平均像素差（对所有像素、通道取 |差| 的均值）。"""
    import numpy as np
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def extract_last_frame(mp4, out_png):
    """抽真末帧（第 N-1 帧）并返回 input 目录下的相对路径（供 LoadImage 使用）。

    旧实现用 -sseof -0.3 抽到的其实是倒数第 7 帧（偏移 6 帧 / 0.25s），
    造成每段新片从"上段结束前 0.25s"开始生成 -> 接缝跳变。
    改为先 ffprobe 取帧数 N，再按帧序号精确抽第 N-1 帧。
    """
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    n = probe_nb_frames(mp4)
    idx = max(0, n - 1)
    r = subprocess.run([ffmpeg_exe(), "-y", "-i", mp4,
                        "-vf", "select=eq(n\\,%d)" % idx,
                        "-frames:v", "1", "-update", "1", out_png],
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(out_png):
        raise RuntimeError("抽末帧失败: " + r.stderr.decode(errors="replace")[-300:])
    return os.path.relpath(out_png, base.INPUT_ROOT).replace("\\", "/")


def has_audio(mp4):
    r = subprocess.run([ffprobe_exe(), "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of", "csv=p=0", mp4],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def _seam_fallback(prev_frames, next_first, window):
    """在 prev 末帧往前 0..window 帧窗口内，找与 next 首帧像素差最小者作为切点。

    返回 (回退帧数 k, 对齐前差 diff_before, 对齐后差 diff_after, 段内自然帧差 natural)。
    k=0 表示末帧本身最优（此时该段不得裁剪）。
    """
    n = len(prev_frames)
    last = prev_frames[n - 1]
    diff_before = mean_abs_diff(last, next_first)
    best_k, best_d = 0, diff_before
    for k in range(1, window + 1):
        idx = n - 1 - k
        if idx < 0:
            break
        d = mean_abs_diff(prev_frames[idx], next_first)
        if d < best_d:
            best_d, best_k = d, k
    natural = mean_abs_diff(prev_frames[n - 2], prev_frames[n - 1]) if n >= 2 else float("nan")
    return best_k, diff_before, best_d, natural


def merge_segments(seg_files, out_path, cd, mode="crossfade",
                   align="auto", align_window=12, match_exposure=False):
    """拼接多段成片。

    mode="crossfade": 视频 xfade 交叉溶解；音频 acrossfade（同步，不丢音）。
    mode="cut":      视频/音频均 concat 硬切；无交叉叠影（推荐用于首尾帧已衔接的段）。
    align="auto":    逐接缝以上段末帧往前 0..window 帧搜索"与下段首帧差最小者"作为切点，
                     裁掉多余尾帧后再拼接；音频按保留帧数等量裁剪，保证音画同步。
                     align="off" 则不裁。
    match_exposure:  对第 2..N 段施加整段统一全局增益，使其平均亮度对齐第 1 段
                     （段内恒定，不在接缝处制造新突变）。
    返回 (ok, err)。
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n = len(seg_files)
    fps = probe_fps(seg_files[0])
    durs = [probe_duration(p) for p in seg_files]
    all_have_audio = all(has_audio(p) for p in seg_files)

    # 逐段解码（分段很短，全解码最稳，用于接缝搜索/曝光统计）。
    frames = [read_frames(p) for p in seg_files]
    keep = [None] * n          # None=整段保留；否则为该段保留帧数
    gains = [1.0] * n

    # ---- 接缝自动对齐 ----
    if align == "auto" and n >= 2:
        for i in range(n - 1):
            k, db, da, nat = _seam_fallback(frames[i], frames[i + 1][0], align_window)
            print("[对齐] 接缝%d->%d: 回退 %d 帧 | 对齐前 %.2f -> 对齐后 %.2f | 段内自然帧差 %.2f"
                  % (i + 1, i + 2, k, db, da, nat), flush=True)
            if k > 0:
                keep[i] = len(frames[i]) - k

    # ---- 段间曝光匹配（默认关闭）----
    # 以第 1 段亮度为基准，对第 2..N 段各施加"整段统一"的全局增益：使该段首帧亮度等于
    # 上一段保留末帧（已校正）的亮度。增益在段内恒定，故段内平滑、接缝处不产生新的亮度
    # 突变；同时把各段亮度整体拉到第 1 段的水平上。
    # 说明：若直接按"各段整段均值对齐第1段均值"做，会因第1段开头偏亮（均值被拉高）
    # 而把后续偏暗段落整体过度提亮，反而在接缝处制造新突变，故改为锚定接缝亮度。
    if match_exposure and n >= 2:
        # lutyuv 作用在 YUV 的 Y 存储值上；源为 limited-range(16..235) 时，以 0 为枢轴的
        # 乘性增益会产生约 0.5% 过冲。这里按黑电平 16 做枢轴换算，使整段亮度精确对齐。
        B = 219.0 / 255.0

        def bright(f):
            return float(f.mean())   # 与验收一致的平均亮度口径

        means = [sum(bright(f) for f in fs) / len(fs) for fs in frames]
        print("[曝光] 段平均亮度 %s（基准=第1段 %.2f）"
              % (["%.2f" % m for m in means], means[0]), flush=True)
        k1 = keep[0] if keep[0] is not None else len(frames[0])
        prev = bright(frames[0][k1 - 1])   # 第1段保留末帧亮度（基准）
        for i in range(1, n):
            cur = bright(frames[i][0])
            denom = cur * B + 16.0
            gains[i] = (prev * B + 16.0) / denom if denom > 1e-6 else 1.0
            kl = keep[i] if keep[i] is not None else len(frames[i])
            last = bright(frames[i][kl - 1])
            prev = (gains[i] * (last * B + 16.0) - 16.0) / B   # 校正后本段末帧 -> 下段目标
            print("[曝光] 段%d 全局增益 x%.4f（段均值 %.2f -> %.2f；接缝亮度对齐 %.2f）"
                  % (i + 1, gains[i], means[i], means[i] * gains[i], prev), flush=True)

    # ---- 逐段输入滤镜（裁剪 / 增益）----
    vfilters, vlabels = [], []
    for i in range(n):
        chain = []
        if keep[i] is not None:
            chain += ["trim=start_frame=0:end_frame=%d" % keep[i], "setpts=PTS-STARTPTS"]
        if abs(gains[i] - 1.0) > 1e-6:
            g = gains[i]
            # 在 YUV 域对亮度做整段统一增益：避免 RGB 往返叠加 range 转换导致的增益损耗，
            # 且只改亮度不引入色偏（色度不变）。
            chain.append("lutyuv=y='clip(val*%.6f,0,255)':u=val:v=val" % g)
        if chain:
            vfilters.append("[%d:v]%s[v%d]" % (i, ",".join(chain), i))
            vlabels.append("v%d" % i)
        else:
            vlabels.append("%d:v" % i)

    afilters, alabels = [], []
    if all_have_audio:
        for i in range(n):
            if keep[i] is not None:
                # 音频按保留帧数等量裁剪（Ki/fps），与视频严格同步，避免音画错位。
                afilters.append("[%d:a]atrim=end=%.6f,asetpts=PTS-STARTPTS[a%d]"
                                % (i, keep[i] / fps, i))
                alabels.append("a%d" % i)
            else:
                alabels.append("%d:a" % i)

    # ---- 拼接（cut=concat 硬切 / crossfade=xfade）----
    tdur = [keep[i] / fps if keep[i] is not None else durs[i] for i in range(n)]
    if mode == "cut" or n == 1:
        vin = "".join("[%s]" % l for l in vlabels)
        vchain, vlast = vin + "concat=n=%d:v=1:a=0[vc]" % n, "vc"
    else:
        parts, prev, acc = [], vlabels[0], tdur[0]
        for i in range(1, n):
            off = max(0.0, acc - cd)
            out = "vx%d" % i
            parts.append("[%s][%s]xfade=transition=fade:duration=%s:offset=%.3f[%s]"
                         % (prev, vlabels[i], cd, off, out))
            prev, acc = out, acc + tdur[i] - cd
        vchain, vlast = ";".join(parts), prev

    achain, alast = None, None
    if all_have_audio:
        if mode == "cut" or n == 1:
            ain = "".join("[%s]" % l for l in alabels)
            achain, alast = ain + "concat=n=%d:v=0:a=1[ac]" % n, "ac"
        else:
            parts, prev = [], alabels[0]
            for i in range(1, n):
                out = "ax%d" % i
                parts.append("[%s][%s]acrossfade=d=%s:c1=tri:c2=tri[%s]"
                             % (prev, alabels[i], cd, out))
                prev = out
            achain, alast = ";".join(parts), prev

    fc = ";".join(vfilters + afilters + [vchain])
    fc += ";[" + vlast + "]format=yuv420p[vout]"
    if achain:
        fc += ";" + achain
    maps = ["-map", "[vout]"] + (["-map", "[%s]" % alast] if achain else [])

    cmd = [ffmpeg_exe(), "-y"]
    for p in seg_files:
        cmd += ["-i", p]
    cmd += ["-filter_complex", fc] + maps + [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "%g" % fps]
    if achain:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", out_path]

    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out_path)
    return ok, (r.stderr or "")[-800:]


def discover_segments(prefix):
    """枚举 output/<prefix>/s{N}_*.mp4，按 N 升序返回。"""
    import glob as _glob
    import re as _re
    seg_dir = os.path.join(base.OUTPUT_ROOT, prefix)
    found = []
    for p in _glob.glob(os.path.join(seg_dir, "s*_*.mp4")):
        m = _re.match(r"s(\d+)_", os.path.basename(p))
        if m:
            found.append((int(m.group(1)), p))
    return [p for _, p in sorted(found)]


def resolve_out_path(args):
    """解析输出路径：--out 缺省时保持原行为 {prefix}_merged.mp4。

    --out 支持绝对路径 / 相对 OUTPUT_ROOT 的路径 / 纯文件名（与分段同目录）。
    """
    o = getattr(args, "out", None)
    if not o:
        return os.path.join(base.OUTPUT_ROOT, args.prefix + "_merged.mp4")
    if os.path.isabs(o):
        return o
    if ("/" in o) or ("\\" in o):
        return os.path.join(base.OUTPUT_ROOT, o.replace("/", os.sep))
    return os.path.join(base.OUTPUT_ROOT,
                        os.path.dirname(args.prefix).replace("/", os.sep), o)


def merge_only(args):
    """跳过生成，直接用已存在的分段重拼（改 --transition / --xfade 时免重跑）。"""
    seg_files = discover_segments(args.prefix)
    if not seg_files:
        print(f"[失败] 未找到分段: {os.path.join(base.OUTPUT_ROOT, args.prefix)}\\s*_*.mp4")
        return 1
    print(f"[重拼] 分段 {len(seg_files)} 个（mode={args.transition}, xfade={args.xfade}s, "
          f"align={args.align}, window={args.align_window}, "
          f"match_exposure={args.match_exposure}）：")
    for p in seg_files:
        print(f"  - {os.path.basename(p)}  {probe_duration(p):.3f}s  audio={has_audio(p)}")
    out_path = resolve_out_path(args)
    ok, err = merge_segments(seg_files, out_path, args.xfade, mode=args.transition,
                             align=args.align, align_window=args.align_window,
                             match_exposure=args.match_exposure)
    if not ok:
        print("[重拼] 失败:\n" + err)
        return 1
    total = probe_duration(out_path)
    print(f"[完成] 成片: {out_path}")
    print(f"       总时长 {total:.3f}s  audio={has_audio(out_path)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="H3 快线多段短段生成 + 衔接 + 拼接")
    ap.add_argument("--workflow", default=base.DEFAULT_WORKFLOW)
    ap.add_argument("--segments", type=int, default=3)
    ap.add_argument("--seg-len", type=int, default=73, help="每段帧数（17k+5 网格，73≈3.04s）")
    ap.add_argument("--width", type=int, default=544)
    ap.add_argument("--height", type=int, default=960)
    ap.add_argument("--seed", type=int, default=20260906)
    ap.add_argument("--first-frame", default="Gemini_Generated_Image_8tttsy8tttsy8ttt (1).jpg")
    ap.add_argument("--prompt-file",
                    default=r"D:\ai_projects\ComfyUI\output\2026-10-01\xinniang_cosplay_v1\ab_prompt.txt")
    ap.add_argument("--prefix", default="2026-10-01/xinniang_cosplay_v1/seg3")
    ap.add_argument("--xfade", type=float, default=0.3)
    ap.add_argument("--transition", choices=["crossfade", "cut"], default="cut",
                    help="cut=硬切(无叠影，推荐)；crossfade=xfade 交叉溶解(有叠影风险)")
    ap.add_argument("--align", choices=["auto", "off"], default="auto",
                    help="接缝自动对齐：auto=逐接缝回退上段末帧到与下段首帧最匹配处；off=不裁")
    ap.add_argument("--align-window", type=int, default=12,
                    help="接缝回退搜索窗口（帧，默认 12）")
    ap.add_argument("--match-exposure", action="store_true",
                    help="段间曝光匹配（默认关闭）：第2..N段整段全局增益对齐第1段平均亮度")
    ap.add_argument("--out", default=None,
                    help="输出文件（绝对路径/相对 OUTPUT_ROOT 路径/纯文件名；"
                         "缺省 {prefix}_merged.mp4）")
    ap.add_argument("--merge-only", action="store_true",
                    help="跳过生成，直接拼接已存在的 {prefix}/s1..sN_*.mp4（改交接参数时免重跑）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.merge_only:
        return merge_only(args)

    length = base.align_length(args.seg_len)
    if length != args.seg_len:
        print(f"[对齐] seg-len {args.seg_len} -> {length}（17k+5）")
        args.seg_len = length
    with open(args.workflow, "r", encoding="utf-8") as f:
        base_wf = json.load(f)
    with open(args.prompt_file, "r", encoding="utf-8-sig") as f:
        prompt = f.read().strip()

    if args.dry_run:
        wf = base.inject_placeholders(base_wf, {
            "first_frame": args.first_frame, "prompt": prompt,
            "width": args.width, "height": args.height, "length": args.seg_len,
            "seed": args.seed + 1, "filename_prefix": f"{args.prefix}/s1"})
        errors, lines = base.validate_workflow(wf)
        for ln in lines:
            print(ln)
        if errors:
            print(f"[失败] {len(errors)} 个问题")
            for e in errors:
                print("  - " + e)
            return 1
        print("[通过] dry-run 校验通过（未提交）")
        return 0

    ok, msg = base.check_single_instance()
    if not ok:
        print(f"[失败] {msg}")
        return 1
    ok, msg = base.check_sla_deps()
    if not ok:
        print(f"[失败] {msg}")
        return 1
    okm, msgm = base.check_memory(6.0)
    print(f"[资源] {msgm}" + ("" if okm else "（偏低，仍继续）"), flush=True)

    seg_files = []
    first = args.first_frame
    t_all = time.time()
    for i in range(1, args.segments + 1):
        t0 = time.time()
        wf = base.inject_placeholders(base_wf, {
            "first_frame": first, "prompt": prompt,
            "width": args.width, "height": args.height, "length": args.seg_len,
            "seed": args.seed + i, "filename_prefix": f"{args.prefix}/s{i}"})
        r = base._post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        if (r.get("node_errors") or {}):
            print(f"[段{i}] node_errors: {json.dumps(r['node_errors'], ensure_ascii=False)[:600]}")
            return 1
        print(f"[段{i}/{args.segments}] 已提交 pid={pid}（首帧={first}）", flush=True)
        rec = base.wait_done(pid)
        if not rec:
            print(f"[段{i}] 执行失败/超时，中止")
            return 1
        files = base.find_output_files(rec)
        if not files:
            print(f"[段{i}] 未定位到输出文件，中止")
            return 1
        mp4 = files[-1]
        seg_files.append(mp4)
        dur = base.exec_seconds(rec.get("status", {}))
        print(f"[段{i}] 完成 {os.path.basename(mp4)}  执行 {dur:.0f}s  本段 {time.time()-t0:.0f}s", flush=True)
        okb = base.acceptance(mp4, args.seg_len, 24.0)
        if okb is False:
            print(f"[段{i}] 抽帧验收未通过，中止")
            return 1
        if i < args.segments:
            png = os.path.join(TMP_FRAMES_DIR, f"seg{i}_last.png")
            first = extract_last_frame(mp4, png)
            print(f"[段{i}] 末帧已抽出 -> input/{first}", flush=True)

    out_path = resolve_out_path(args)
    okm, err = merge_segments(seg_files, out_path, args.xfade, mode=args.transition,
                              align=args.align, align_window=args.align_window,
                              match_exposure=args.match_exposure)
    if not okm:
        print("[拼接] 失败:\n" + err)
        return 1
    total = probe_duration(out_path)
    print(f"\n[完成] 成片: {out_path}")
    print(f"       分段 {len(seg_files)} × {args.seg_len} 帧，mode={args.transition}，"
          f"总时长 {total:.2f}s  audio={has_audio(out_path)}，"
          f"作业总耗时 {(time.time()-t_all)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())