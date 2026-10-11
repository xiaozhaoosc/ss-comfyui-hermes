#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OOTD 成片字幕 + 水印烧录（独立工具）

对已生成的成片（如 french_dress_series_merged.mp4）烧录按段切分的中文字幕，
并可选叠加右下角水印。字幕时间区间由 --seg-dur（单段时长）与 --xfade（转场时长）
推算，与成片实际切点一致（段 i 的可见区间：
  start = (i-1)*(seg_dur - xfade) + xfade；end = (i-1)*(seg_dur - xfade) + seg_dur - xfade
即去掉每段首尾各一个转场时长，避免字幕叠在黑场/转场上）。

实现要点：
  - 优先 ffmpeg drawtext（fontfile 显式指定中文字体，enable='between(t,a,b)'，
    alpha 表达式做淡入淡出）；可选 overlay 叠加 PNG 水印；
  - 滤镜图写入临时文件，用 -filter_complex_script 传入（参数用数组，不拼 shell 字符串，
    避免中文/引号/反斜杠问题）；
  - --soft：只输出 .srt（不外挂烧录）；--ass <file>：直接烧 ASS 字幕。

仅新建本文件；不修改 ootd_outfit_swap.py 或其它既有工具。

用法:
  python tools/ootd_study/ootd_subtitle.py \
      --video output/2026-10-02/french_dress_series/french_dress_series_merged.mp4 \
      --out   output/2026-10-03/french_dress_series/subtitled/french_dress_series_merged_4color_sub.mp4 \
      --segments "奶油米白|奶油米白|经典黑|经典黑|酒红|酒红|雾霾蓝|雾霾蓝" \
      --seg-dur 3.0417 --xfade 0.3

  # 直接烧 ASS
  python tools/ootd_study/ootd_subtitle.py --video in.mp4 --out out.mp4 --ass sub.ass

  # 仅输出 srt
  python tools/ootd_study/ootd_subtitle.py --video in.mp4 --out out.mp4 \
      --segments "a|b" --soft
"""
import argparse
import os
import subprocess
import sys
import tempfile

FFMPEG_CANDIDATES = [r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe"]
FFPROBE_CANDIDATES = [r"C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffprobe.exe"]
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


# ----------------------------- 工具 -----------------------------

def resolve_ffmpeg():
    for p in FFMPEG_CANDIDATES:
        if os.path.exists(p):
            return p
    from shutil import which
    return which("ffmpeg")


def resolve_ffprobe():
    for p in FFPROBE_CANDIDATES:
        if os.path.exists(p):
            return p
    from shutil import which
    return which("ffprobe")


def resolve_font(explicit):
    """返回可用字体绝对路径；explicit 指定且不存在 -> 抛错。"""
    if explicit:
        if os.path.exists(explicit):
            return explicit
        raise FileNotFoundError(
            f"指定的字体不存在: {explicit}\n"
            f"可用回退候选: {', '.join(FONT_CANDIDATES)}")
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "未找到任何可用中文字体（尝试过的候选: "
        + ", ".join(FONT_CANDIDATES) + "）；请用 --font 显式指定一个含中文字形的 ttf/ttc。")


def probe_duration(mp4):
    ff = resolve_ffprobe()
    if not ff:
        return 0.0
    r = subprocess.run([ff, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", mp4],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def probe_streams(mp4):
    """返回 (video_codec, audio_codec, width, height, fps)。"""
    ff = resolve_ffprobe()
    if not ff:
        return (None,) * 5
    r = subprocess.run([ff, "-v", "error", "-show_streams",
                        "-of", "json", mp4], capture_output=True, text=True)
    import json
    try:
        streams = json.loads(r.stdout).get("streams", [])
    except Exception:
        return (None,) * 5
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fps = 0.0
    fr = v.get("r_frame_rate", "0/0")
    try:
        num, den = fr.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except Exception:
        fps = 0.0
    return (v.get("codec_name"), a.get("codec_name"),
            v.get("width"), v.get("height"), fps)


def _fg_quote(s):
    """把文本安全放进滤镜图的单引号内（'...'）。"""
    # 单引号在滤镜图内会终止引用；用右单引号替换以保持可读且不破坏语法。
    return s.replace("'", "\u2019")


def _fg_path(p):
    """滤镜图内的文件路径：统一正斜杠，并把冒号做两级转义（C\\:/...）。

    ffmpeg 滤镜图内 ':' 是选项分隔符，即便用引号包裹也无法保护盘符冒号，
    必须写成转义形式（经验证 fontfile=C\\\\:/Windows/Fonts/msyh.ttc 可用）。
    """
    return p.replace("\\", "/").replace(":", "\\\\:")


def seg_windows(n, seg_dur, xfade):
    """按段推算可见时间区间（去掉首尾各 xfade，与成片切点一致）。"""
    wins = []
    for i in range(n):
        base = i * (seg_dur - xfade)
        wins.append((base + xfade, base + seg_dur - xfade))
    return wins


def build_drawtext_chain(texts, windows, font, fontsize, position, y_margin, fade):
    """返回 drawtext 滤镜链（逗号连接），每段一个 drawtext。"""
    font_fg = _fg_path(font)
    parts = []
    for text, (s, e) in zip(texts, windows):
        s = max(0.0, s)
        e = max(s + 0.05, e)
        txt = _fg_quote(text)
        alpha = (f"if(lt(t,{s:.3f}+{fade}),max(0,(t-{s:.3f})/{fade}),"
                 f"if(gt(t,{e:.3f}-{fade}),max(0,({e:.3f}-t)/{fade}),1))")
        if position == "center":
            y = "(h-text_h)/2"
        else:
            y = f"h-text_h-{y_margin}"
        dt = (f"drawtext=fontfile={font_fg}:text='{txt}':fontsize={fontsize}"
              f":fontcolor=white:borderw=3:bordercolor=black@0.6"
              f":shadowcolor=black@0.45:shadowx=2:shadowy=2"
              f":x=(w-text_w)/2:y={y}"
              f":enable='between(t,{s:.3f},{e:.3f})'"
              f":alpha='{alpha}'")
        parts.append(dt)
    return ",".join(parts)


def build_filtergraph(texts, windows, font, fontsize, position, y_margin, fade,
                      watermark, wm_scale, wm_opacity, wm_margin, ass_file):
    """构造完整 filter_complex；返回 (filtergraph, last_video_label, need_wm_input)。"""
    if ass_file:
        chain = f"[0:v]subtitles={_fg_path(os.path.abspath(ass_file))}[vsub]"
    else:
        chain = "[0:v]" + build_drawtext_chain(
            texts, windows, font, fontsize, position, y_margin, fade) + "[vsub]"

    if not watermark:
        return chain.replace("[vsub]", "[vout]"), "vout", False

    m = int(wm_margin)
    fg = (f"{chain};"
          f"[1:v]scale=iw*{wm_scale:.4f}:-1,format=rgba,"
          f"colorchannelmixer=aa={wm_opacity:.4f}[wm];"
          f"[vsub][wm]overlay=x=W-w-{m}:y=H-h-{m}[vout]")
    return fg, "vout", True


def write_srt(texts, windows, out_srt):
    def ts(t):
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    for i, (text, (s, e)) in enumerate(zip(texts, windows), 1):
        lines.append(str(i))
        lines.append(f"{ts(max(0.0, s))} --> {ts(e)}")
        lines.append(text)
        lines.append("")
    with open(out_srt, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))
    return out_srt


# ----------------------------- main -----------------------------

def main():
    ap = argparse.ArgumentParser(description="OOTD 成片字幕 + 水印烧录")
    ap.add_argument("--video", required=True, help="输入成片 mp4")
    ap.add_argument("--out", required=True, help="输出 mp4（--soft 时输出 srt 基名）")
    ap.add_argument("--segments", default=None,
                    help="字幕文本，按段/镜头时间切分，用 | 分隔（如 a|b|c）")
    ap.add_argument("--seg-dur", type=float, default=3.0417, help="单段时长（秒）")
    ap.add_argument("--xfade", type=float, default=0.3, help="转场时长（秒）")
    ap.add_argument("--ass", default=None, help="直接烧 ASS 字幕文件（忽略 --segments）")
    ap.add_argument("--watermark", default=None, help="右下角水印 PNG（可选）")
    ap.add_argument("--wm-scale", type=float, default=0.12, help="水印宽度占比")
    ap.add_argument("--wm-opacity", type=float, default=0.75, help="水印不透明度")
    ap.add_argument("--wm-margin", type=int, default=24, help="水印边距（像素）")
    ap.add_argument("--font", default=None,
                    help="字体文件（默认自动选 msyh.ttc -> msyhbd.ttc -> simhei.ttf）")
    ap.add_argument("--fontsize", type=int, default=44, help="字号（竖屏 736 宽默认 44）")
    ap.add_argument("--position", choices=["bottom", "center"], default="bottom")
    ap.add_argument("--y-margin", type=int, default=160, help="bottom 时距底边像素")
    ap.add_argument("--fade", type=float, default=0.15, help="字幕淡入淡出时长（秒）")
    ap.add_argument("--burn", action="store_true", help="烧录进视频（默认行为）")
    ap.add_argument("--soft", action="store_true", help="仅输出 .srt 文件，不烧录")
    args = ap.parse_args()

    video = os.path.abspath(args.video)
    if not os.path.exists(video):
        print(f"[失败] 输入视频不存在: {video}")
        return 1

    # ---- 解析文本 / 时间区间 ----
    if args.ass:
        texts, windows = [], []
    else:
        if not args.segments:
            print("[失败] 需提供 --segments 或 --ass")
            return 1
        texts = [t for t in args.segments.split("|")]
        if not texts:
            print("[失败] --segments 为空")
            return 1
        windows = seg_windows(len(texts), args.seg_dur, args.xfade)
        print(f"[字幕] {len(texts)} 段；seg_dur={args.seg_dur} xfade={args.xfade}")
        for i, (t, (s, e)) in enumerate(zip(texts, windows), 1):
            print(f"  段{i}: '{t}'  t=[{s:.3f}, {e:.3f}]")

    # ---- soft：仅输出 srt ----
    if args.soft:
        if args.ass:
            print("[失败] --soft 与 --ass 不能同时使用")
            return 1
        srt = os.path.splitext(os.path.abspath(args.out))[0] + ".srt"
        os.makedirs(os.path.dirname(srt), exist_ok=True)
        write_srt(texts, windows, srt)
        print(f"[完成] 仅输出字幕文件: {srt}（未烧录）")
        return 0

    # ---- 字体 ----
    try:
        font = resolve_font(args.font)
    except FileNotFoundError as e:
        print(f"[失败] {e}")
        return 1

    if args.watermark and not os.path.exists(os.path.abspath(args.watermark)):
        print(f"[失败] 水印不存在: {args.watermark}")
        return 1

    ff = resolve_ffmpeg()
    if not ff:
        print("[失败] 未找到 ffmpeg")
        return 1

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    in_v, in_a, w, h, fps = probe_streams(video)
    in_dur = probe_duration(video)
    print(f"[输入] {video}")
    print(f"       {w}x{h} @ {fps:.3f}fps  时长={in_dur:.3f}s  "
          f"video={in_v} audio={in_a}")

    ass_file = os.path.abspath(args.ass) if args.ass else None
    if ass_file and not os.path.exists(ass_file):
        print(f"[失败] ASS 不存在: {ass_file}")
        return 1

    fg, vlast, need_wm = build_filtergraph(
        texts, windows, font, args.fontsize, args.position, args.y_margin, args.fade,
        args.watermark, args.wm_scale, args.wm_opacity, args.wm_margin, ass_file)

    tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                      encoding="utf-8")
    try:
        tmp.write(fg)
        tmp.close()
        cmd = [ff, "-y", "-i", video]
        if need_wm:
            cmd += ["-i", os.path.abspath(args.watermark)]
        cmd += ["-filter_complex_script", tmp.name,
                "-map", f"[{vlast}]"]
        if in_a:
            cmd += ["-map", "0:a", "-c:a", "copy"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
        print(f"[字体] {font}  fontsize={args.fontsize}  position={args.position}"
              + (f"  y_margin={args.y_margin}" if args.position == "bottom" else ""))
        if args.watermark:
            print(f"[水印] {args.watermark}  scale={args.wm_scale}  "
                  f"opacity={args.wm_opacity}  margin={args.wm_margin}")
        print(f"[滤镜] (filter_complex_script) 长度={len(fg)} 字符")
        r = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if r.returncode != 0 or not os.path.exists(out):
        print("[失败] ffmpeg 执行失败:")
        print((r.stderr or "")[-2500:])
        return 1

    out_v, out_a, ow, oh, ofps = probe_streams(out)
    out_dur = probe_duration(out)
    print(f"[完成] 输出: {out}")
    print(f"       {ow}x{oh} @ {ofps:.3f}fps  时长={out_dur:.3f}s  "
          f"video={out_v} audio={out_a}")
    ok_dur = abs(out_dur - in_dur) <= 0.15
    ok_a = (out_a == in_a) if in_a else (out_a is None)
    print(f"       时长保持={ok_dur}（in {in_dur:.3f} -> out {out_dur:.3f}）  "
          f"音轨 codec 保持={ok_a}（{in_a} -> {out_a}）")
    return 0 if (ok_dur and ok_a) else 1


if __name__ == "__main__":
    sys.exit(main())
