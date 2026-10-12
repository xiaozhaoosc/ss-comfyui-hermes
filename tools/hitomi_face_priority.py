"""
Hitomi 批量换脸 — 正脸优先选片打分（§8.5）。

对每个视频抽 3 帧（10%/50%/90% 处），用与 ReActor 同源的 RetinaFace
（det_10g.onnx，复用 tools/h3_rope_common.py 的 _face_detector，E 区纪律：
不调 FaceAnalysis.get()、本进程不 import torch）取最大人脸，按
「人脸面积占比 + 正脸度」打分，输出子目录内降序清单，供
batch_faceswap_overlay.py --order-file 使用。

  占比分 = min(1, 人脸面积/帧面积 / 0.25)      # 占画面 1/4 即满分
  正脸度 = 1 - min(1, |鼻侧偏移|/0.5 + 眼线倾角/0.5)
  综合分 = 0.6*占比分 + 0.4*正脸度*检出率

用法：
  python tools/hitomi_face_priority.py --input <视频根目录> [--out-dir <目录>] [--frames 3]

输出（--out-dir，缺省 output/2026-10-12/hitomi_batch）：
  _face_priority.json      全量打分明细（含 NO_FACE / READ_ERROR 清单）
  <子目录名>_order.txt     提交顺序清单（一行一个文件名，供 --order-file）

无人脸视频记 NO_FACE（换脸无效，放量时人工确认跳过或保留），不自动剔除。
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hitomi_precheck import collect_files, probe  # noqa: E402
from h3_rope_common import _face_detector  # noqa: E402

DEFAULT_OUT_DIR = os.path.join("output", "2026-10-12", "hitomi_batch")
DEFAULT_WORKERS = 4

# 多 worker 时每个 ORT 会话限线程，防止 4×28 超订（须在创建 session 前设置）
if os.cpu_count() and os.cpu_count() > 8:
    os.environ.setdefault("OMP_NUM_THREADS", str(max(4, os.cpu_count() // DEFAULT_WORKERS)))


def frontal_score(kps):
    """由 5 点关键点（左眼/右眼/鼻/左嘴角/右嘴角）估正脸程度：0~1"""
    kp = np.asarray(kps, dtype=np.float32).reshape(-1, 2)
    le, re_, nose = kp[0], kp[1], kp[2]
    eye_vec = re_ - le
    eye_dist = float(np.hypot(eye_vec[0], eye_vec[1]))
    if eye_dist < 1e-3:
        return 0.0
    mid_x = (le[0] + re_[0]) / 2.0
    offset = abs(nose[0] - mid_x) / eye_dist          # 0=正，越大越发侧
    roll = float(np.arctan2(abs(eye_vec[1]), abs(eye_vec[0])))  # 眼线倾角
    return max(0.0, 1.0 - min(1.0, offset / 0.5 + roll / 0.5))


def sample_frames(path, n, max_side):
    """取 n 帧（BGR），最长边降采样到 max_side。

    单次 ffmpeg 解码：fps=1 每秒 1 帧 + 同步缩放，落临时 PNG 后按
    10%/50%/90% 位置取。比逐时间点 -ss seek 快数倍（vp9 关键帧稀疏，
    3 次 seek 实测 28s vs 单次解码个位数秒）。
    """
    import cv2
    import glob
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="fp_")
    try:
        vf = "fps=1,scale=-2:%d" % max_side
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-vf", vf,
             os.path.join(tmp, "%03d.png")],
            check=True, capture_output=True, timeout=300)
        pngs = sorted(glob.glob(os.path.join(tmp, "*.png")))
        if not pngs:
            return []
        idxs = [int((len(pngs) - 1) * (k + 0.5) / n) for k in range(n)]
        frames = [cv2.imread(pngs[i]) for i in idxs]
        return [f for f in frames if f is not None]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def score_video(path, det, frames_n, max_side):
    """单条打分：返回 (score, face_ratio, frontal, detect_rate, flags)"""
    flags = []
    try:
        info = probe(path)
    except Exception as e:
        return -1.0, 0.0, 0.0, 0.0, ["READ_ERROR:%s" % e]
    frames = sample_frames(path, frames_n, max_side)
    if not frames:
        return -1.0, 0.0, 0.0, 0.0, ["READ_ERROR:cv2 打不开"]

    ratios, frontals, hits = [], [], 0
    for frame in frames:
        faces = det(frame)
        if not faces:
            continue
        hits += 1
        bbox = np.asarray(faces[0]["bbox"], dtype=np.float32).reshape(-1)[:4]
        fh, fw = frame.shape[:2]
        area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
        ratios.append(area / float(fw * fh))
        kps = faces[0].get("kps")
        frontals.append(frontal_score(kps) if kps is not None else 0.0)

    detect_rate = hits / float(len(frames))
    if detect_rate == 0:
        flags.append("NO_FACE")
    face_ratio = float(np.mean(ratios)) if ratios else 0.0
    frontal = float(np.mean(frontals)) if frontals else 0.0
    score = 0.6 * min(1.0, face_ratio / 0.25) + 0.4 * frontal * detect_rate
    return round(score, 4), round(face_ratio, 4), round(frontal, 4), round(detect_rate, 3), flags


_W_DET = None


def _init_worker():
    """每个 worker 进程初始化自己的检测器（ORT session 非进程共享）"""
    global _W_DET
    _W_DET = _face_detector()[1]


def _detector_name():
    return _face_detector()[0]


def _score_one(job):
    path, rel, subdir, frames_n, max_side = job
    score, ratio, frontal, dr, flags = score_video(path, _W_DET, frames_n, max_side)
    return {"path": rel, "subdir": subdir, "score": score,
            "face_ratio": ratio, "frontal": frontal,
            "detect_rate": dr, "flags": flags}


def main():
    ap = argparse.ArgumentParser(description="Hitomi 正脸优先选片打分")
    ap.add_argument("--input", required=True, help="视频根目录（递归）")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="输出目录（缺省 %s）" % DEFAULT_OUT_DIR)
    ap.add_argument("--frames", type=int, default=3, help="每条视频抽帧数（默认3）")
    ap.add_argument("--max-side", type=int, default=480, help="抽帧最长边降采样（默认480，打分够用且快）")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="并行进程数（默认4）")
    a = ap.parse_args()

    root = a.input
    files = collect_files(root)
    print("扫描 %d 个视频（%s）" % (len(files), root))
    os.makedirs(a.out_dir, exist_ok=True)

    jobs = [(f, os.path.relpath(f, root),
             os.path.dirname(os.path.relpath(f, root)) or "_flat",
             a.frames, a.max_side) for f in files]
    workers = max(1, min(a.workers, len(jobs)))

    import multiprocessing as mp
    entries = []
    t0 = time.time()
    with mp.Pool(workers, initializer=_init_worker) as pool:
        det_name = pool.apply(_detector_name)
        if not det_name:
            print("❌ 无人脸检测器可用（insightface/opencv 均缺失）")
            sys.exit(1)
        print("检测器: %s ｜ %d workers" % (det_name, workers))
        for i, e in enumerate(pool.imap_unordered(_score_one, jobs), 1):
            entries.append(e)
            if i % 20 == 0 or i == len(files):
                print("  [%d/%d] %.0fs" % (i, len(files), time.time() - t0), flush=True)

    # 按子目录分组，各组内降序，输出顺序清单
    by_subdir = {}
    for e in entries:
        by_subdir.setdefault(e["subdir"], []).append(e)
    order_files = []
    for subdir, items in sorted(by_subdir.items()):
        items.sort(key=lambda e: -e["score"])
        safe = subdir.replace("/", "_").replace("\\", "_")
        of = os.path.join(a.out_dir, "%s_order.txt" % safe)
        with open(of, "w", encoding="utf-8") as fp:
            for e in items:
                fp.write(os.path.basename(e["path"]) + "\n")
        order_files.append(of)

    no_face = [e["path"] for e in entries if "NO_FACE" in e["flags"] or any(
        fl.startswith("READ_ERROR") for fl in e["flags"])]
    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "detector": det_name,
        "root": os.path.abspath(root),
        "videos": entries,
        "summary": {
            "total": len(entries),
            "no_face_or_error": no_face,
            "by_subdir": {k: len(v) for k, v in sorted(by_subdir.items())},
        },
    }
    jpath = os.path.join(a.out_dir, "_face_priority.json")
    with open(jpath, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)

    print("\n==== 汇总 ====")
    print("总数 %d ｜ NO_FACE/读失败 %d ｜ 耗时 %.0fs" % (len(entries), len(no_face), time.time() - t0))
    for subdir, items in sorted(by_subdir.items()):
        top = "、".join("%s(%.2f)" % (os.path.basename(e["path"])[:24], e["score"]) for e in items[:3])
        print("  %-28s %3d 条 | top: %s" % (subdir[:28], len(items), top))
    if no_face:
        print("⚠️ NO_FACE/读失败清单（人工确认跳过或保留，未自动剔除）:")
        for p in no_face:
            print("   -", p)
    print("JSON: %s" % jpath)
    for of in order_files:
        print("顺序清单: %s" % of)


if __name__ == "__main__":
    main()
