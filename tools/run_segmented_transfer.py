#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""白模动作迁移「分段跑 + 去重叠拼接」：把长片拆成显存够用的段，再逐帧精确接回整片。

为什么分段：16GB 卡上整段跑会把显存打满进 offload（实测 124 帧 18 分钟，
209 帧 74+ 分钟仍未完且近 OOM）。分段把每段压回 --seg 帧的显存安全区间。

帧级拼接（不重不漏，接缝误差 0 帧 = 41.7ms @24fps）：
  total=209, seg=124 → 段2 起点 = total - seg = 85，重叠 = seg - 85 = 39 帧。
  合并 = 段1 全部 124 帧 + 段2 的第 39 帧起(85 帧) = 209 帧，落在驱动第 124 帧。
段间连续性：两段吃的是同一段驱动(重叠 39 帧)、同一参考图、同一 seed，故动作连续。

用法:
  python tools/run_segmented_transfer.py --driver wm_202610 --ref 5 --variant strong \
      --prefix v6_wm_5 --total 209 --seg 124 --seconds 5 [--dry-run]
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
BASE = "http://127.0.0.1:8188"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHF = os.path.join(ROOT, "tools", "submit_h3_duozhi_fix.py")


def load_shf():
    spec = importlib.util.spec_from_file_location("shf", SHF)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def segments(total, seg):
    """返回 [(start, length)]；起点均匀分布，让每个接缝都有相同的重叠区。"""
    if total <= seg:
        return [(0, total)]
    n = (total + seg - 1) // seg
    if n < 2:
        return [(0, total)]
    step = (total - seg) / (n - 1)
    starts = sorted({round(i * step) for i in range(n - 1)} | {total - seg})
    return [(s, seg) for s in starts if s + seg <= total]


def wait_done(pid, timeout=7200):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(10)
        try:
            with OPENER.open("%s/history/%s" % (BASE, pid), timeout=30) as r:
                h = json.loads(r.read().decode("utf-8"))
        except Exception:
            continue
        if pid not in h:
            if int(time.time() - t0) % 120 < 10:
                print("   ...等待 %ds" % (time.time() - t0), flush=True)
            continue
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for mm in st.get("messages", []):
                if mm[0] == "execution_error":
                    print("   [报错]", json.dumps(mm[1], ensure_ascii=False)[:600])
            return None
        if st.get("completed"):
            return h[pid].get("outputs", {})
    print("   [超时]")
    return None


def out_video(outputs):
    """取最终成片节点 #115 的产物。

    #111/#112 是 save_output=false 的中间态（写 temp/），会把它们当成分片导致合并拿到
    不存在的路径，所以这里只认 #115。
    """
    for g in ((outputs or {}).get("115", {}).get("gifs") or []):
        if "-audio" in (g.get("filename") or ""):
            continue
        sub = (g.get("subfolder") or "").replace("/", os.sep)
        return os.path.join(ROOT, "output", sub, g["filename"])
    return None


def seg_file(prefix, i):
    """已生成的第 i 段成片（排除 -audio.mp4）。"""
    import glob
    fs = [f for f in sorted(glob.glob(os.path.join(ROOT, "output", "%s_s%d_*.mp4" % (prefix, i))))
          if "-audio" not in os.path.basename(f)]
    return fs[-1] if fs else None


def wait_stable(path, timeout=120):
    """等文件大小不再变化再读，避免成片刚落盘、ffmpeg 还没写完 moov 就被合并读到。"""
    t0, last = time.time(), -1
    while time.time() - t0 < timeout:
        try:
            sz = os.path.getsize(path)
        except OSError:
            sz = -1
        if sz > 0 and sz == last:
            return True
        last = sz
        time.sleep(5)
    return False


def last_frame(video, png):
    """抽视频末帧存成 PNG（首尾粘用）。"""
    import cv2
    cap = cv2.VideoCapture(video)
    fr = None
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr = f
    cap.release()
    if fr is None:
        return None
    ok, buf = cv2.imencode(".png", fr)
    buf.tofile(png)
    return png


def merge(outs, segs, driver, dst, fade=12):
    """逐帧合成：按驱动帧号取段，接缝前 fade 帧与下一段线性溶解；再并驱动音轨。

    段间用帧级溶解而不是硬切，消除背景/外观在接缝处的跳变。
    """
    import cv2
    import numpy as np
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    fps = 24.0
    total = segs[-1][0] + segs[-1][1]
    caps = [cv2.VideoCapture(p) for p in outs]
    cur = [None] * len(outs)
    live = [True] * len(outs)
    tmp = os.path.join(ROOT, "temp", "_seg_merged_noaudio.mp4")
    enc, n = None, 0
    for j in range(total):
        for i, (s, ln) in enumerate(segs):
            if live[i] and s <= j < s + ln:
                ok, f = caps[i].read()
                if ok:
                    cur[i] = f
                else:
                    live[i] = False
        owners = [i for i, (s, ln) in enumerate(segs) if s <= j < s + ln]
        if not owners:
            continue
        o = owners[0]
        base = cur[o]
        if base is None:
            continue
        if fade > 0:
            for i in owners[1:]:
                if cur[i] is None:
                    continue
                # 溶解窗固定在上一段末尾（段2 被首尾粘锚定在段1 末帧，越靠近末尾两版越一致）；
                # 窗长不得超过实际重叠，否则首帧会突然跳到中途 alpha 造成闪跳
                ov = segs[o][0] + segs[o][1] - segs[i][0]
                f = max(1, min(fade, ov))
                a = (j - (segs[o][0] + segs[o][1] - f)) / float(f)
                if a > 0:
                    a = min(1.0, a)
                    base = (base.astype(np.float32) * (1 - a)
                            + cur[i].astype(np.float32) * a).astype(np.uint8)
                break
        if enc is None:
            h, w = base.shape[:2]
            enc = subprocess.Popen(
                [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
                 "-s", "%dx%d" % (w, h), "-r", str(fps), "-i", "-", "-c:v", "h264_nvenc",
                 "-pix_fmt", "yuv420p", "-b:v", "10M", tmp], stdin=subprocess.PIPE)
        enc.stdin.write(base.tobytes())
        n += 1
    for c in caps:
        c.release()
    if enc is None:
        print("[合并] 未取到帧")
        return False
    enc.stdin.close()
    rc = enc.wait()
    if rc != 0 or n != total:
        print("[合并] 编码失败 rc=%s 帧数=%d/%d" % (rc, n, total))
        return False
    print("[合并] 溶解 %d 帧 · 输出 %d 帧" % (fade, n))
    drv = os.path.join(ROOT, "input", SHF_DRIVER[0])
    r2 = subprocess.run([exe, "-y", "-loglevel", "error", "-i", tmp, "-i", drv,
                         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                         dst], capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    os.remove(tmp)
    if r2.returncode != 0:
        print("[合并] 并音轨失败：", (r2.stderr or "")[-600:])
        return False
    return True


SHF_DRIVER = [""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--driver", default="wm_202610")
    ap.add_argument("--ref", default="5")
    ap.add_argument("--variant", default="strong")
    ap.add_argument("--prefix", default="v6_wm_5")
    ap.add_argument("--total", type=int, required=True, help="驱动总帧数")
    ap.add_argument("--seg", type=int, default=124, help="每段帧数（须等于 #42 公式取值）")
    ap.add_argument("--seconds", type=float, default=5.0, help="与 --seg 对应的 #41 秒数")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--merge-only", action="store_true",
                    help="不提交，等各段成片出现后直接去重叠合并（用于恢复）")
    ap.add_argument("--fade", type=int, default=6,
                    help="接缝溶解帧数（默认 6）；0=硬切（首尾粘生效后通常看不出切换）")
    args = ap.parse_args()

    shf = load_shf()
    got = shf.frames_for(args.seconds)
    if got != args.seg:
        raise SystemExit("--seg(%d) 与 --seconds(%s) 不匹配：frames_for= %d" % (
            args.seg, args.seconds, got))
    SHF_DRIVER[0] = shf.DRIVERS[args.driver]

    segs = segments(args.total, args.seg)
    cover = segs[-1][0] + segs[-1][1] if segs else 0
    print("[分段] 总帧=%d 每段=%d → %d 段 %s 覆盖 %d 帧" % (
        args.total, args.seg, len(segs), segs, cover))

    if args.merge_only:
        outs = []
        for i in range(1, len(segs) + 1):
            p, t0 = None, time.time()
            while time.time() - t0 < 7200:
                p = seg_file(args.prefix, i)
                if p:
                    break
                time.sleep(15)
            if not p:
                print("[合并] 段%d 成片未出现，终止" % i)
                return 1
            wait_stable(p)
            print("[合并] 段%d → %s" % (i, p), flush=True)
            outs.append(p)
        dst = os.path.join(ROOT, "output", "%s_full_%df.mp4" % (args.prefix, args.total))
        if not merge(outs, segs, args.driver, dst, fade=args.fade):
            return 1
        print("[完成] 整片 =", dst)
        return 0

    outs = []
    for i, (start, length) in enumerate(segs, 1):
        prompt, nodes, unknown = shf.build()
        prompt["29"]["inputs"]["image"] = shf.REFS[args.ref]
        prompt["117"]["inputs"]["video"] = shf.DRIVERS[args.driver]
        prompt["117"]["inputs"]["skip_first_frames"] = start
        pref = "%s_s%d" % (args.prefix, i)
        prompt["115"]["inputs"]["filename_prefix"] = pref
        prompt, notes = shf.apply_variant(prompt, args.variant)
        prompt = shf.sync_length(prompt, args.seconds)
        print("  段%d: 驱动帧 %d..%d | #117 skip=%d | 前缀 %s" % (
            i, start, start + length - 1, start, pref))
        print("       #117 frame_load_cap=%r | #163 batch=%r" % (
            prompt["117"]["inputs"]["frame_load_cap"],
            prompt["163"]["inputs"]["batch_size"]))
        print("       改动: %s" % ("; ".join(notes) or "(none)"))
        if args.dry_run:
            continue
        if i > 1:
            # 首尾粘：把上一段末帧作为第二张参考图喂给本段，接住外观/背景
            anchor = os.path.join(ROOT, "input", "_seg_anchor_s%d.png" % i)
            wait_stable(outs[i - 2])
            if last_frame(outs[i - 2], anchor):
                prompt["901"] = {"class_type": "LoadImage",
                                 "inputs": {"image": os.path.basename(anchor)}}
                prompt["12"]["inputs"]["ref_images.ref_image_1"] = ["901", 0]
                print("       首尾粘：段%d 末帧 → #12.ref_images.ref_image_1" % (i - 1))
        res = shf.submit(prompt, nodes)
        if not res:
            print("  [段%d 提交失败]" % i)
            return 1
        pid = res["prompt_id"]
        print("  段%d prompt_id=%s" % (i, pid), flush=True)
        o = wait_done(pid)
        if o is None:
            print("  [段%d 未完成，终止]" % i)
            return 1
        p = out_video(o)
        print("  段%d 产物 = %s" % (i, p), flush=True)
        outs.append(p)

    if args.dry_run:
        print("[dry-run] 未提交")
        return 0

    dst = os.path.join(ROOT, "output", "%s_full_%df.mp4" % (args.prefix, args.total))
    if not merge(outs, segs, args.seg, args.driver, dst):
        return 1
    print("[完成] 整片 =", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
