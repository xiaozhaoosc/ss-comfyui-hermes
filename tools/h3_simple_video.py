#!/usr/bin/env python3
"""H3 古风新娘 小白版 —— 只需改几个数字即可生成视频。

自动完成：分段 → 首尾帧衔接 → xfade 拼合，并可选 720P/60fps 增强。

【小白配置区】直接改下面这三个数即可：
  DURATION = 10    # 目标视频时长（秒）
  RES      = "480p" # "480p"(快) 或 "720p"(清晰，需 20G+ 显存，4060Ti 建议 480p+增强)
  ASPECT   = "9:16" # "9:16"(手机竖屏) 或 "16:9"(横屏)

也可用命令行：python tools/h3_simple_video.py --seconds 10 --res 480p --aspect 9:16
"""
import sys, os, math, subprocess, json, uuid, time, argparse

from h3_xinniang_v1 import (
    BASE, FFMPEG, FFPROBE, INPUT_ROOT, TMP_DIR, REF_IMG,
    BASE_PROMT, SEG2_SUFFIX, post, wait_done, build_segment,
    extract_last_frame, probe_duration,
)

# ===== 小白配置区 =====
DURATION = 10
RES = "480p"          # 480p | 720p
ASPECT = "9:16"       # 9:16 | 16:9
SEG_TARGET_SEC = 3.0  # 期望每段秒数(H3 下限≈5.2s，会自动向上取整)，改大则每段更长/段数更少
# =====================

OUT_DIR = r"D:\ai_projects\ComfyUI\output\xinniang_simple"

# H3 length 合法格点 17k+5（训练范围 124~362）
def grid_len(sec):
    f = max(124, int(round(sec * 24)))
    k = (f - 5) // 17
    while 17 * k + 5 < f:
        k += 1
    return 17 * k + 5

def res_to_wh(res, aspect):
    m = {("480p", "9:16"): (544, 960), ("480p", "16:9"): (960, 544),
         ("720p", "9:16"): (736, 1280), ("720p", "16:9"): (1280, 720)}
    return m[(res, aspect)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=DURATION)
    ap.add_argument("--res", choices=["480p", "720p"], default=RES)
    ap.add_argument("--aspect", choices=["9:16", "16:9"], default=ASPECT)
    ap.add_argument("--seg_sec", type=float, default=SEG_TARGET_SEC)
    ap.add_argument("--enhance", action="store_true", help="结尾额外增强到720P/60fps")
    args = ap.parse_args()

    length = grid_len(args.seg_sec)            # 每段帧数（合法格点）
    seg_dur = length / 24.0                    # 每段秒数
    segs = max(1, math.ceil(args.seconds / seg_dur))
    W, H = res_to_wh(args.res, args.aspect)
    steps = 28 if args.res == "480p" else 20   # 720p 自动降步数控制显存

    print("=" * 56)
    print("H3 小白版 生成设置")
    print(f"  时长目标   : {args.seconds}s → 拆 {segs} 段 × 实际{seg_dur:.1f}s")
    print(f"  分辨率/画幅: {W}×{H}  (res={args.res}, aspect={args.aspect})")
    print(f"  采样步骤   : {steps}")
    if args.seg_sec < seg_dur:
        print(f"  提示: 你希望每段{args.seg_sec}s，但 H3 最少约5.2s，已取 {seg_dur:.1f}s")
    if args.res == "720p":
        print("  ⚠️  720p 需要约 20G+ 显存，若爆显存请改用 480p")
    print("=" * 56)

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    seg_files = []
    prev_last = None
    for i in range(1, segs + 1):
        prefix = f"xinniang_simple/s{i:02d}"
        prompt = BASE_PROMT if i == 1 else ("the same woman with exactly the same face, hairstyle and "
                                            "red brocade costume continuing her elegant pose" + SEG2_SUFFIX)
        seed = 20260905 + i
        wf = build_segment(prompt, prev_last, seed, prefix, W, H, length, REF_IMG)
        r = post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        pid = r.get("prompt_id")
        print(f"[{i}/{segs}] 段 s{i:02d} 提交 pid={pid}")
        if not wait_done(pid):
            print("  该段失败，中止"); sys.exit(1)
        cand = sorted(os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
                      if f.startswith(f"s{i:02d}") and f.endswith(".mp4"))
        seg_files.append(cand[-1])
        print(f"  ✓ {os.path.basename(cand[-1])}")
        # 末帧存 input 下供下段衔接
        png = extract_last_frame(cand[-1], os.path.join(TMP_DIR, f"simple_s{i:02d}_last.png"))
        prev_last = os.path.relpath(png, INPUT_ROOT).replace("\\", "/")

    # 拼合（多段 xfade 交叉淡化）
    out_name = os.path.join(OUT_DIR, f"xinniang_{args.aspect.replace(':','x')}_{args.res}_{segs}seg.mp4")
    if segs > 1:
        inputs = []
        for p in seg_files:
            inputs += ["-i", p]
        durs = [probe_duration(p) for p in seg_files]
        chain, prev, acc = [], "0:v", durs[0]
        for i in range(1, segs):
            off = max(0.0, acc - 0.3)
            chain.append(f"[{prev}][{i}:v]xfade=transition=fade:duration=0.3:offset={off:.3f}[vx{i}];")
            prev, acc = f"vx{i}", acc + durs[i] - 0.3
        vf = "".join(chain) + f"[{prev}]format=yuv420p[vout]"
        cmd = [FFMPEG, "-y"] + inputs + ["-filter_complex", vf, "-map", "[vout]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "24",
               "-movflags", "+faststart", out_name]
    else:
        cmd = [FFMPEG, "-y", "-i", seg_files[0], "-c", "copy", out_name]
    subprocess.run(cmd, capture_output=True, text=True)

    print(f"\n✅ 成片: {out_name}  ({round(os.path.getsize(out_name)/1024/1024,1)}MB)")

    if args.enhance:
        print(">> 增强到 720P/60fps ...")
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "enhance_h3_video.py"), out_name])

if __name__ == "__main__":
    main()