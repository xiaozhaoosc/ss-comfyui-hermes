"""
去掉 WanAnimate 成片开头的「参考图锚点帧 + 鬼影过渡帧」，并同步裁剪音频保持音画对齐。

背景：实测所有产物开头都有固定伪影——
  帧 0 = reference_image 锚点（构图/光照与后文不同）
  帧 1 = 双影过渡帧（鬼影）
  帧 2 起才稳定
B 方案（831 直出）f0 与 f1 都坏 → 需丢 2 帧
C 方案（SDXL 全身重绘）f0 尚可、f1 是鬼影 → 丢 1 帧即可

用法：
  python tools/trim_opening.py --in <video_or_dir> --drop 2
  python tools/trim_opening.py --in <dir> --drop 2 --out-suffix _trim
  python tools/trim_opening.py --in <video> --drop 2 --dry-run   # 只报告不写
"""
import argparse, glob, json, os, subprocess, sys


def detect_drop(path, probe_n=16, k=1.8, need=3, cap=12):
    """
    自动检测开头应丢几帧：伪影特征是「锚点帧 + 鬼影帧」，其后差分回落到常态。
    做法：算前 probe_n 帧的相邻差分 d[i]=diff(f_i,f_{i+1})，取全片中位 med；
    找到最早的下标 s，使 d[s..s+need-1] 全部 < med*k（连续 need 帧稳定）；
    则首个干净帧 = s+1，应丢弃帧数 = s+1。
    返回 (drop, med, diffs)
    """
    import cv2
    import numpy as np
    import statistics
    c = cv2.VideoCapture(path)
    fr = []
    while True:
        ok, x = c.read()
        if not ok:
            break
        fr.append(cv2.resize(x, (120, 208)).astype(np.float32))
        if len(fr) > 400:      # 只看头部足够
            break
    c.release()
    if len(fr) < probe_n + 2:
        return 2, 0.0, []
    d = [float(np.abs(fr[i] - fr[i - 1]).mean()) for i in range(1, len(fr))]
    med = statistics.median(d) or 1.0
    head = d[:probe_n]
    for s in range(len(head) - need + 1):
        if all(head[s + j] < med * k for j in range(need)):
            return min(s + 1, cap), med, [round(v, 1) for v in head]
    return min(probe_n, cap), med, [round(v, 1) for v in head]


def probe(path):
    o = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
         "-of", "json", path], capture_output=True, text=True, timeout=60).stdout
    j = json.loads(o)
    s = [x for x in j["streams"]][0]
    num, den = s["r_frame_rate"].split("/")
    fps = int(num) / int(den) if int(den) else 30.0
    nf = int(s.get("nb_frames") or 0)
    has_audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
        capture_output=True, text=True).stdout.strip()
    return fps, nf, bool(has_audio)


def trim(src, dst, drop, fps):
    """丢前 drop 帧；音频同步丢掉 drop/fps 秒"""
    t = drop / fps
    vf = f"trim=start_frame={drop},setpts=PTS-STARTPTS"
    if t > 0:
        af = f"atrim=start={t:.6f},asetpts=PTS-STARTPTS"
    else:
        af = None
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", vf]
    if af:
        cmd += ["-af", af]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "16",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True, timeout=900)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="视频文件或目录")
    ap.add_argument("--drop", type=int, default=2, help="丢弃开头帧数（--auto 时作为上限参考）")
    ap.add_argument("--auto", action="store_true", help="按帧差自动检测每个视频应丢几帧")
    ap.add_argument("--out-suffix", default="_trim")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = a.inp
    if os.path.isdir(src):
        files = sorted(glob.glob(os.path.join(src, "*.mp4")))
        files = [f for f in files if not os.path.basename(f).startswith(("_", "."))]
    else:
        files = [src]

    print("待处理 %d 个文件，drop=%s" % (len(files), "auto" if a.auto else a.drop))
    for f in files:
        try:
            fps, nf, audio = probe(f)
        except Exception as e:
            print("  [SKIP] probe 失败", f, e); continue
        drop = a.drop
        extra = ""
        if a.auto:
            try:
                drop, med, head = detect_drop(f)
                extra = "  [auto] med=%.2f 头部差分=%s" % (med, head)
            except Exception as e:
                extra = "  [auto失败, 用默认%d] %s" % (drop, e)
        base = os.path.splitext(f)[0]
        dst = base + a.out_suffix + ".mp4"
        print("  %-42s %dfps %d帧 -> 丢%d帧%s" % (
            os.path.basename(f)[:42], round(fps), nf, drop, extra))
        if a.dry_run:
            continue
        try:
            trim(f, dst, drop, fps)
            _, n2, _ = probe(dst)
            print("     [OK] 新帧数=%d (丢 %d 帧), %.0f KB" % (n2, drop, os.path.getsize(dst) / 1024))
        except Exception as e:
            print("     [FAIL]", e)


if __name__ == "__main__":
    main()
