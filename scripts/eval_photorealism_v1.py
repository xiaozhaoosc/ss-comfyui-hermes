# -*- coding: utf-8 -*-
"""
eval_photorealism_v1.py
========================
对三套 2K 重绘产物 (Qwen-Image 2.1 / Flux Abliterated / SDXL RealVisXL)
做客观量化评测，用于「塑料感 / 真实感」交付报告。

核心思路
--------
用户的诉求是「去 AI 假人感 / 塑料感」，落到可测指标上其实是三件事：

1. 微观起伏      —— 皮肤有没有毛孔级细节，还是被磨成一块塑料板   -> skin_hf
2. 血色层次      —— 皮下毛细血管的色度变化，死白磨皮会把色度抹平 -> skin_chroma_std
3. 死白/过曝     —— 磨皮会把高光推到 255 形成"白蜡"             -> skin_clip

再补一组「眼眸 / 唇部」的微区指标（假眼珠 = 眼区极均匀且无边沿反光），
以及相对原图切片的结构保真度（SSIM / NCC / Lab 色偏），确保"变真实"的同时
没有把人画走样。

尺度问题的处理
--------------
基线切片是 1024，产物是 2048。纹理指标对分辨率敏感，因此同一张图算两套：
  * @1024 ：统一降采样到 1024，模拟"整图观察尺度"，四路可比（含基线）
  * @2048 ：产物原生像素尺度，只看三路重绘（基线不参与，避免不公平）
"""

import os
import re
import csv
import sys
import json
import glob
import time
import argparse

import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.join(ROOT, "output", "2026-10-08", "cropped")
MODE_DIRS = {
    "base":   BASE_DIR,
    "qwen21": os.path.join(ROOT, "output", "2026-10-08", "qwen21_2k"),
    "flux":   os.path.join(ROOT, "output", "2026-10-08", "flux_2k"),
    "sdxl":   os.path.join(ROOT, "output", "2026-10-09", "sdxl_2k"),
}
# 各模式下文件名的正则：抓出 (组名, 行, 列, 序号)
KEY_RE = re.compile(r"^(?P<group>.+?)_R(?P<r>\d)C(?P<c>\d)_(?P<idx>\d+)_")

DET_PATH = r"C:\Users\kenzhao\.insightface\models\buffalo_l\det_10g.onnx"


# --------------------------------------------------------------------------
# 基础图像工具
# --------------------------------------------------------------------------
def imread_any(path):
    """中文路径安全读取。"""
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def hf_energy(gray, mask=None, sigma=1.5):
    """高频能量 = gray 与其高斯模糊之差的 std。
    数值越高，该区域微观起伏越丰富（毛孔 / 唇纹 / 虹膜纹理）。"""
    blur = cv2.GaussianBlur(gray, (0, 0), sigma)
    hf = gray.astype(np.float32) - blur.astype(np.float32)
    if mask is not None and mask.any():
        v = hf[mask]
    else:
        v = hf.ravel()
    return float(np.std(v)) if v.size > 16 else float("nan")


def skin_mask(bgr):
    """YCrCb 经典肤色掩膜，再叠一点 RGB 规则压制暖色背景。"""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    Y, Cr, Cb = ycrcb[:, :, 0], ycrcb[:, :, 1], ycrcb[:, :, 2]
    m = (Cr >= 133) & (Cr <= 185) & (Cb >= 77) & (Cb <= 135) & (Y > 40)
    b, g, r = bgr[:, :, 0].astype(np.int16), bgr[:, :, 1].astype(np.int16), bgr[:, :, 2].astype(np.int16)
    m &= (r > g) & (g > b) & (r - b > 12)
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)


def block_contrast(gray, bs=16):
    """局部对比度：16x16 分块 std 的均值。反映画面"沉稳 vs 发灰"。"""
    h, w = gray.shape[:2]
    h -= h % bs
    w -= w % bs
    if h == 0 or w == 0:
        return float("nan")
    g = gray[:h, :w].astype(np.float32)
    blocks = g.reshape(h // bs, bs, w // bs, bs).transpose(0, 2, 1, 3).reshape(-1, bs, bs)
    return float(np.mean(blocks.std(axis=(1, 2))))


# --------------------------------------------------------------------------
# 人脸区域定位（直接用 RetinaFace，不走 FaceAnalysis.get —— 后者会崩进程）
# --------------------------------------------------------------------------
_det = None


def get_detector():
    global _det
    if _det is None:
        from insightface.model_zoo import get_model
        _det = get_model(DET_PATH)
        try:
            _det.prepare(ctx_id=-1, input_size=(640, 640))
        except Exception:
            pass
    return _det


def detect_face(bgr):
    """返回 (bbox, kps)；失败返回 (None, None)。bbox=[x1,y1,x2,y2]。"""
    try:
        det = get_detector()
        out = det.detect(bgr, max_num=1)
        if isinstance(out, tuple):
            bboxes, kpss = out[0], (out[1] if len(out) > 1 else None)
        else:
            bboxes, kpss = out, None
        if bboxes is None or len(bboxes) == 0:
            return None, None
        bb = np.asarray(bboxes)[0][:4].astype(float)
        kps = np.asarray(kpss)[0].astype(float) if (kpss is not None and len(kpss)) else None
        return bb, kps
    except Exception:
        return None, None


def face_regions(bb, kps, W, H):
    """由 bbox + 5 点关键点推出 眼区 / 唇区 / 脸区（含越界裁剪）。"""
    x1, y1, x2, y2 = bb
    fw, fh = x2 - x1, y2 - y1

    def box(cx, cy, hw, hh):
        return (max(0, int(cx - hw)), max(0, int(cy - hh)),
                min(W, int(cx + hw)), min(H, int(cy + hh)))

    regs = {"face": box((x1 + x2) / 2, (y1 + y2) / 2, fw * 0.60, fh * 0.60)}
    if kps is not None and len(kps) >= 5:
        le, re_, nose, lm, rm = kps[:5]
        hw, hh = fw * 0.095, fh * 0.070
        regs["eyeL"] = box(le[0], le[1], hw, hh)
        regs["eyeR"] = box(re_[0], re_[1], hw, hh)
        regs["mouth"] = box((lm[0] + rm[0]) / 2, (lm[1] + rm[1]) / 2, fw * 0.145, fh * 0.095)
    return regs


# --------------------------------------------------------------------------
# 单图指标
# --------------------------------------------------------------------------
def measure(bgr, regs=None):
    """返回该图在自身分辨率下的全部指标。"""
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)

    m = {}
    m["w"] = W
    m["h"] = H
    m["lap_var"] = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    m["block_contrast"] = block_contrast(gray)
    m["lum_p99_p1"] = float(np.percentile(gray, 99) - np.percentile(gray, 1))
    m["lum_std"] = float(gray.std())
    m["sat_mean"] = float(hsv[:, :, 1].mean())
    m["sat_std"] = float(hsv[:, :, 1].std())

    sm = skin_mask(bgr)
    m["skin_ratio"] = float(sm.mean())

    # 皮肤：优先只统计人脸区，避免暖色背景（木地板/夕阳）污染
    if regs and "face" in regs:
        fx1, fy1, fx2, fy2 = regs["face"]
        fmask = np.zeros_like(sm)
        fmask[fy1:fy2, fx1:fx2] = True
        sm_face = sm & fmask
        if sm_face.mean() < 0.05:   # 脸区没抓到肤色就退回全图
            sm_face = sm
    else:
        sm_face = sm

    if sm_face.sum() > 200:
        L = lab[:, :, 0].astype(np.float32) * 255.0 / 255.0
        a = lab[:, :, 1].astype(np.float32)
        bb_ = lab[:, :, 2].astype(np.float32)
        m["skin_hf"] = hf_energy(gray, sm_face, sigma=1.5)      # 毛孔级
        m["skin_hf_mid"] = hf_energy(gray, sm_face, sigma=4.0)  # 中频立体感
        m["skin_lum_std"] = float(L[sm_face].std())
        m["skin_chroma_std"] = float(np.std(np.hypot(a[sm_face] - 128, bb_[sm_face] - 128)))
        m["skin_clip"] = float((gray[sm_face] >= 248).mean())   # 死白过曝
        m["skin_sat"] = float(hsv[:, :, 1][sm_face].mean())
        m["skin_px"] = int(sm_face.sum())
    else:
        for k in ("skin_hf", "skin_hf_mid", "skin_lum_std", "skin_chroma_std",
                  "skin_clip", "skin_sat"):
            m[k] = float("nan")
        m["skin_px"] = 0

    # 眼 / 唇 微区
    for name in ("eyeL", "eyeR", "mouth"):
        if regs and name in regs:
            x1, y1, x2, y2 = regs[name]
            if x2 - x1 > 8 and y2 - y1 > 8:
                sub = gray[y1:y2, x1:x2]
                m[f"{name}_hf"] = hf_energy(sub, None, sigma=1.5)
                m[f"{name}_std"] = float(sub.std())
                m[f"{name}_spec"] = float((sub >= 240).mean())
            else:
                m[f"{name}_hf"] = m[f"{name}_std"] = m[f"{name}_spec"] = float("nan")
        else:
            m[f"{name}_hf"] = m[f"{name}_std"] = m[f"{name}_spec"] = float("nan")

    if regs and "eyeL" in regs and "eyeR" in regs:
        e = [m.get("eyeL_hf"), m.get("eyeR_hf")]
        e = [v for v in e if v is not None and not np.isnan(v)]
        m["eye_hf"] = float(np.mean(e)) if e else float("nan")
    else:
        m["eye_hf"] = float("nan")

    return m


def fidelity(bgr_a, bgr_b, size=512):
    """a 相对 b 的结构保真度（两者都降到 size）。"""
    ga = cv2.resize(cv2.cvtColor(bgr_a, cv2.COLOR_BGR2GRAY), (size, size), interpolation=cv2.INTER_AREA)
    gb = cv2.resize(cv2.cvtColor(bgr_b, cv2.COLOR_BGR2GRAY), (size, size), interpolation=cv2.INTER_AREA)
    a = ga.astype(np.float64)
    b = gb.astype(np.float64)
    a -= a.mean()
    b -= b.mean()
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    ncc = float((a * b).sum() / denom) if denom > 1e-9 else float("nan")

    # 不引 skimage，手写一份简化 SSIM（窗口 11，高斯加权）
    def _ssim(x, y):
        C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
        k = cv2.getGaussianKernel(11, 1.5)
        ww = k @ k.T
        ux = cv2.filter2D(x, -1, ww)[5:-5, 5:-5]
        uy = cv2.filter2D(y, -1, ww)[5:-5, 5:-5]
        vx = cv2.filter2D(x * x, -1, ww)[5:-5, 5:-5] - ux ** 2
        vy = cv2.filter2D(y * y, -1, ww)[5:-5, 5:-5] - uy ** 2
        vxy = cv2.filter2D(x * y, -1, ww)[5:-5, 5:-5] - ux * uy
        num = (2 * ux * uy + C1) * (2 * vxy + C2)
        den = (ux ** 2 + uy ** 2 + C1) * (vx + vy + C2)
        return float(np.mean(num / den))

    la = cv2.cvtColor(cv2.resize(bgr_a, (size, size), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB).astype(np.float32)
    lb = cv2.cvtColor(cv2.resize(bgr_b, (size, size), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB).astype(np.float32)
    dlab = la - lb
    return {
        "ncc": ncc,
        "ssim": _ssim(ga.astype(np.float64), gb.astype(np.float64)),
        "dL": float(dlab[:, :, 0].mean()),
        "da": float(dlab[:, :, 1].mean() - 0),
        "db": float(dlab[:, :, 2].mean() - 0),
        "dE": float(np.sqrt((dlab ** 2).sum(axis=2)).mean()),
    }


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def index_dir(d, pattern="*.png"):
    out = {}
    for p in glob.glob(os.path.join(d, pattern)):
        fn = os.path.basename(p)
        mo = KEY_RE.match(fn)
        if not mo:
            continue
        key = (mo.group("group"), int(mo.group("r")), int(mo.group("c")), int(mo.group("idx")))
        out[key] = p
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个切片（调试用）")
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "2026-10-10_wb", "eval"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    t0 = time.time()

    base_idx = index_dir(BASE_DIR, "*_1x1.png")
    mode_idx = {k: index_dir(v) for k, v in MODE_DIRS.items() if k != "base"}
    print(f"[idx] base={len(base_idx)} " + " ".join(f"{k}={len(v)}" for k, v in mode_idx.items()))

    keys = sorted(base_idx.keys())
    if args.limit:
        keys = keys[: args.limit]

    rows = []
    nfail = 0
    for i, key in enumerate(keys):
        group, r, c, idx = key
        bp = base_idx[key]
        b_base = imread_any(bp)
        if b_base is None:
            nfail += 1
            continue

        # 人脸只在基线 1024 上跑一次，坐标按比例放大给 2K 产物复用
        bb, kps = detect_face(b_base)
        regs_base = face_regions(bb, kps, b_base.shape[1], b_base.shape[0]) if bb is not None else None

        base1024 = b_base if b_base.shape[0] == 1024 else cv2.resize(b_base, (1024, 1024), interpolation=cv2.INTER_AREA)

        for mode in ["base", "qwen21", "flux", "sdxl"]:
            p = bp if mode == "base" else mode_idx.get(mode, {}).get(key)
            if not p or not os.path.exists(p):
                continue
            img = imread_any(p)
            if img is None:
                nfail += 1
                continue
            H, W = img.shape[:2]

            regs = regs_base
            if regs_base is not None and W != b_base.shape[1]:
                s = W / float(b_base.shape[1])
                regs = {k: (int(v[0] * s), int(v[1] * s), int(v[2] * s), int(v[3] * s))
                        for k, v in regs_base.items()}

            # @1024 统一观察尺度
            v1024 = cv2.resize(img, (1024, 1024), interpolation=cv2.INTER_AREA)
            regs1024 = None
            if regs is not None:
                s = 1024.0 / W
                regs1024 = {k: (int(v[0] * s), int(v[1] * s), int(v[2] * s), int(v[3] * s))
                            for k, v in regs.items()}
            m1 = measure(v1024, regs1024)

            # @原生（仅 2K 产物）
            m2 = measure(img, regs) if W >= 2048 else None

            fid = fidelity(img, base1024) if mode != "base" else {}

            row = {
                "group": group, "row": r, "col": c, "idx": idx, "mode": mode,
                "file": os.path.basename(p), "has_face": int(regs is not None),
            }
            row.update({f"v1024_{k}": v for k, v in m1.items() if k not in ("w", "h")})
            if m2:
                row.update({f"nat_{k}": v for k, v in m2.items() if k not in ("w", "h")})
            row.update({f"fid_{k}": v for k, v in fid.items()})
            rows.append(row)

        if (i + 1) % 6 == 0 or i == len(keys) - 1:
            el = time.time() - t0
            print(f"[run] {i+1}/{len(keys)} elapsed={el:.1f}s rows={len(rows)} fail={nfail}", flush=True)

    # ---- 落盘 ----
    if not rows:
        print("[ERR] 没有任何有效数据")
        return 1
    cols = []
    for row in rows:
        for k in row:
            if k not in cols:
                cols.append(k)
    csv_path = os.path.join(args.out, "metrics_per_image.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    print(f"[out] {csv_path}  rows={len(rows)} cols={len(cols)}")

    # ---- 汇总 ----
    num_cols = [c for c in cols if c not in ("group", "row", "col", "idx", "mode", "file", "has_face")]
    summary = {}
    for mode in ["base", "qwen21", "flux", "sdxl"]:
        sub = [r_ for r_ in rows if r_["mode"] == mode]
        if not sub:
            continue
        summary[mode] = {"n": len(sub)}
        for c in num_cols:
            vals = [r_[c] for r_ in sub if isinstance(r_.get(c), (int, float)) and not np.isnan(float(r_[c]))]
            summary[mode][c] = round(float(np.mean(vals)), 4) if vals else None

    # 塑料感综合指数（在统一 1024 尺度上做 min-max，0=最真实 100=最塑料）
    def mm(vals):
        lo, hi = np.nanmin(vals), np.nanmax(vals)
        return (np.asarray(vals, dtype=float) - lo) / (hi - lo + 1e-9)

    all_hf = np.array([r_.get("v1024_skin_hf", np.nan) for r_ in rows], dtype=float)
    all_ch = np.array([r_.get("v1024_skin_chroma_std", np.nan) for r_ in rows], dtype=float)
    all_cl = np.array([r_.get("v1024_skin_clip", np.nan) for r_ in rows], dtype=float)
    ok = ~np.isnan(all_hf) & ~np.isnan(all_ch)
    plastic = np.full(len(rows), np.nan)
    if ok.sum() > 10 and np.nanstd(all_hf[ok]) > 1e-9:
        hf_n = np.nan_to_num((all_hf - np.nanmin(all_hf[ok])) / (np.nanmax(all_hf[ok]) - np.nanmin(all_hf[ok])))
        ch_n = np.nan_to_num((all_ch - np.nanmin(all_ch[ok])) / (np.nanmax(all_ch[ok]) - np.nanmin(all_ch[ok])))
        cl_n = np.nan_to_num((all_cl - np.nanmin(all_cl[~np.isnan(all_cl)])) /
                             (np.nanmax(all_cl[~np.isnan(all_cl)]) - np.nanmin(all_cl[~np.isnan(all_cl)]) + 1e-9))
        plastic = 100.0 * (0.55 * (1 - hf_n) + 0.30 * (1 - ch_n) + 0.15 * cl_n)
        for i, r_ in enumerate(rows):
            r_["plastic_index"] = round(float(plastic[i]), 2)
            summary.setdefault(r_["mode"], {}).setdefault("_plastic_tmp", []).append(plastic[i])
        for mode in summary:
            if "_plastic_tmp" in summary[mode]:
                summary[mode]["plastic_index"] = round(float(np.mean(summary[mode].pop("_plastic_tmp"))), 2)
        # 回写 CSV
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.DictWriter(f, fieldnames=cols + ["plastic_index"], extrasaction="ignore")
            wr.writeheader()
            wr.writerows(rows)

    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[out] summary.json")
    print(json.dumps({k: {kk: vv for kk, vv in v.items()
                          if kk in ("n", "v1024_skin_hf", "v1024_skin_chroma_std", "v1024_skin_clip",
                                    "v1024_lap_var", "plastic_index", "fid_ssim", "fid_ncc", "fid_dE")}
                      for k, v in summary.items()}, ensure_ascii=False, indent=2))
    print(f"[done] {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
