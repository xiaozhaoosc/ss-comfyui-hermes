# -*- coding: utf-8 -*-
"""可复用 LoRA 数据集抽帧脚本

功能(按输入视频顺序处理):
  1. sampling: 按目标时长/帧率从视频抽候选帧
  2. blur_filter: 拉普拉斯方差阈值, 剔除模糊/运动糊帧
  3. dedup: 逐帧感知相似度(下采样灰图 SSIM 近似/均值差), 跳过雷同帧
  4. face_filter(可选): 是否至少存在一个合理大小的前景人脸(靠 cv2 人脸级联, 弱但免费)
  5. caption: 每段视频对应一套服装, 按 (服装, 场景) 模板批量生成 .txt, 与 .png 配对
  6. 默认触发词 ohwx 由调用方注入(与 ai-toolkit 约定相同)

用法:
  python frame_extractor.py --input A.mp4 B.mp4 ... --out output/2026-09-14/wearmix/frames \
      --outfits "白色衬衫,街头" "风衣,咖啡馆" --fps 1 --min-blur 60 --diff-thresh 0.05 \
      --keep 30 --trigger "ohwx woman"

说明:
  --outfits 数量需与 --input 一一对应(每段视频=一套服装); 每项格式 "服装,场景"
  --keep N   平均每段视频最多保留 N 张合格帧
  --trigger  前缀注入触发词(默认 "ohwx woman")
"""
import argparse, os, sys, time, math
import cv2
import numpy as np

FACE_CASCADE = None

def load_face_cascade():
    global FACE_CASCADE
    if FACE_CASCADE is None:
        p = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        FACE_CASCADE = cv2.CascadeClassifier(p)
    return FACE_CASCADE

def blur_score(gray):
    """拉普拉斯方差, 越大越清晰"""
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def downsample_gray(frame, size=128):
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (size, size), interpolation=cv2.INTER_AREA)

def diff_ratio(prev, cur, size=64):
    """两帧均值差占位空间的比值, ~0 表示几乎相同"""
    a = cv2.resize(prev, (size, size)).astype(np.float32)
    b = cv2.resize(cur, (size, size)).astype(np.float32)
    return float(np.mean(np.abs(a - b)) / 255.0)

def has_face(frame, min_size=0.05):
    cash = load_face_cascade()
    if cash.empty():
        return None  # 级联不可用则不做该过滤
    h, w = frame.shape[:2]
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cash.detectMultiScale(g, 1.1, 3, minSize=(max(40, int(w*min_size) if True else 32),
                                                     max(40, int(h*min_size) if True else 32)))
    return len(faces) > 0

def extract_video(path, cfg):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError("cannot open " + path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps / cfg.fps)))
    frames = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            frames.append((idx, frame))
        idx += 1
    cap.release()
    return frames, fps, total

def run(video, outfit, scene, cfg, out_dir, prefix):
    frames, fps, total = extract_video(video, cfg)
    print(f"[{video}] fps={fps:.1f} total={total} sampled={len(frames)}", flush=True)
    kept = []
    prev_gray = None
    for fi, frame in frames:
        # 尺寸过大先降采样算清晰度(节省时间)
        gray_small = cv2.cvtColor(cv2.resize(frame, (480, max(1, int(480*frame.shape[0]/frame.shape[1]))),
                                             interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        bscore = cv2.Laplacian(gray_small, cv2.CV_64F).var()
        if bscore < cfg.min_blur:
            continue  # 模糊帧
        if cfg.face_check:
            fh = has_face(frame)
            if fh is False:
                continue  # 无脸帧
        cur_gray = downsample_gray(frame)
        if prev_gray is not None:
            d = diff_ratio(prev_gray, cur_gray)
            if d < cfg.diff_thresh:
                # 与上一张太像, 若清晰度更高则替换, 否则跳过(去重)
                if kept and bscore > kept[-1][1]:
                    kept[-1] = (frame, bscore)
                continue
        kept.append((frame, bscore))
        prev_gray = cur_gray

    # 按清晰度保留均值上限 keep 张, 同时摊开在时间上
    if len(kept) > cfg.keep:
        kept.sort(key=lambda x: x[1], reverse=True)
        kept = kept[:cfg.keep]
        kept.sort(key=lambda x: id(x))  # 稳定序即可
    kept = kept[:cfg.keep]

    os.makedirs(out_dir, exist_ok=True)
    if not kept:
        print(f"[{video}] WARNING: 0 frames kept", flush=True)
        return 0
    for k, (frame, bscore) in enumerate(kept, start=1):
        num = f"{prefix}_{k:03d}"
        cv2.imwrite(os.path.join(out_dir, num + ".png"), frame)
        with open(os.path.join(out_dir, num + ".txt"), "w", encoding="utf-8") as f:
            f.write(f"A photo of {cfg.trigger}, {outfit}, {scene}\n")
    print(f"[{video}] kept {len(kept)}/{len(frames)} frames -> {out_dir}", flush=True)
    return len(kept)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--outfits", nargs="+", required=True,
                    help='每段视频一套 "服装,场景", 需与 --input 等长')
    ap.add_argument("--fps", type=float, default=1.0, help="采样帧率(默认1)")
    ap.add_argument("--min-blur", type=float, default=60.0, help="拉普拉斯方差下限, 低于则视为糊")
    ap.add_argument("--diff-thresh", type=float, default=0.05, help="帧差去重阈值(0-1)")
    ap.add_argument("--keep", type=int, default=30, help="每段最多保留张数")
    ap.add_argument("--face-check", action="store_true", help="启用弱人脸存在性过滤")
    ap.add_argument("--trigger", default="ohwx woman")
    cfg = ap.parse_args()

    if len(cfg.input) != len(cfg.outfits):
        sys.exit("[错误] --input 与 --outfits 数量必须一致(每段视频=一套服装)")
    os.makedirs(cfg.out, exist_ok=True)
    total_kept = 0
    for i, (video, outf) in enumerate(zip(cfg.input, cfg.outfits), start=1):
        if "," in outf:
            outfit, scene = outf.split(",", 1)
        else:
            outfit, scene = outf, "wide scene"
        prefix = f"wear_{i:02d}_{slug(video)}"
        total_kept += run(video, outfit.strip(), scene.strip(), cfg,
                          os.path.join(cfg.out, f"seg{i:02d}"), prefix)
    print(f"=== DONE === total frames kept: {total_kept}", flush=True)

def slug(path):
    b = os.path.splitext(os.path.basename(path))[0]
    return "".join(c if c.isalnum() else "_" for c in b)[:24]

if __name__ == "__main__":
    main()