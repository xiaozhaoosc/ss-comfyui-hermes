# -*- coding: utf-8 -*-
"""
analyze_eval.py —— 读取 metrics_per_image.csv，产出报告所需的统计口径。

关键：@1024 尺度对基线不公平（基线原生 1024，三路是 2048 降采样而来，
降采样会抹掉像素级颗粒）。因此：
  * 跨「基线 vs 三路」的结论  -> 只看结构类指标（SSIM/NCC/色偏）+ 中频立体感
  * 三路之间的微观质感对比     -> 只看 nat_*（2048 原生尺度，完全公平）

另外引入 grain_ratio = nat_skin_hf / v1024_skin_hf：
  * 高  -> 细节主要停留在像素级（疑似噪点/锐化，不是真毛孔）
  * 低  -> 细节扛得住降采样（结构性细节，即真实的皮纹/立体起伏）
"""

import os
import re
import csv
import json
import glob
import sys
import argparse

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_photorealism_v1 import ROOT, BASE_DIR, MODE_DIRS, KEY_RE, index_dir, imread_any  # noqa: E402

MODES = ["base", "qwen21", "flux", "sdxl"]


def load(csv_path):
    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            for k, v in list(r.items()):
                if k in ("group", "mode", "file"):
                    continue
                try:
                    r[k] = float(v) if v not in ("", "None", None) else np.nan
                except ValueError:
                    pass
            rows.append(r)
    return rows


def agg(rows, col, by="mode"):
    out = {}
    for r in rows:
        k = r[by]
        v = r.get(col, np.nan)
        if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v)):
            out.setdefault(k, []).append(float(v))
    return {k: (round(float(np.mean(v)), 4), round(float(np.std(v)), 4), len(v)) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(ROOT, "output", "2026-10-10_wb", "eval", "metrics_per_image.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "2026-10-10_wb", "eval"))
    args = ap.parse_args()

    rows = load(args.csv)
    print(f"[load] {len(rows)} rows")

    # ---------- 0) 找出缺失/损坏文件 ----------
    base_idx = index_dir(BASE_DIR, "*_1x1.png")
    mode_idx = {k: index_dir(v) for k, v in MODE_DIRS.items() if k != "base"}
    missing = []
    for key in sorted(base_idx):
        for mode in ("qwen21", "flux", "sdxl"):
            p = mode_idx.get(mode, {}).get(key)
            if not p:
                missing.append({"key": "|".join(map(str, key)), "mode": mode, "reason": "文件不存在"})
                continue
            if imread_any(p) is None:
                sz = os.path.getsize(p)
                missing.append({"key": "|".join(map(str, key)), "mode": mode,
                                "reason": f"解码失败 (size={sz} bytes)", "file": os.path.basename(p)})
    print(f"[check] 缺失/损坏 {len(missing)} 项")
    for m in missing:
        print("   ", m)
    with open(os.path.join(args.out, "missing_files.json"), "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=False, indent=2)

    # ---------- 1) 派生指标 ----------
    for r in rows:
        nat = r.get("nat_skin_hf", np.nan)
        v10 = r.get("v1024_skin_hf", np.nan)
        r["grain_ratio"] = (nat / v10) if (v10 and not np.isnan(v10) and v10 > 1e-6
                                           and not np.isnan(nat)) else np.nan
        natm = r.get("nat_skin_hf_mid", np.nan)
        r["struct_ratio"] = (natm / nat) if (nat and not np.isnan(nat) and nat > 1e-6) else np.nan

    # ---------- 2) 三路 @2048 原生尺度 ----------
    nat_cols = ["nat_skin_hf", "nat_skin_hf_mid", "nat_skin_lum_std", "nat_skin_chroma_std",
                "nat_skin_clip", "nat_skin_sat", "nat_lap_var", "nat_block_contrast",
                "nat_eye_hf", "nat_eyeL_hf", "nat_eyeR_hf", "nat_mouth_hf",
                "nat_mouth_std", "nat_lum_p99_p1", "grain_ratio", "struct_ratio"]
    print("\n===== @2048 原生尺度（仅三路重绘，公平对比） =====")
    nat_table = {}
    for c in nat_cols:
        d = agg([r for r in rows if r["mode"] != "base"], c)
        if d:
            nat_table[c] = d
            print(f"{c:24s} " + "  ".join(
                f"{k}={v[0]:>8.3f}(sd {v[1]:.3f})" for k, v in sorted(d.items())))

    # ---------- 3) @1024 统一尺度（含基线） ----------
    v_cols = ["v1024_skin_hf", "v1024_skin_hf_mid", "v1024_skin_chroma_std", "v1024_skin_lum_std",
              "v1024_skin_clip", "v1024_lap_var", "v1024_block_contrast", "v1024_sat_mean",
              "v1024_lum_p99_p1", "v1024_eye_hf", "v1024_mouth_hf", "plastic_index"]
    print("\n===== @1024 统一尺度（含基线；基线享原生分辨率优势，仅供参考） =====")
    v_table = {}
    for c in v_cols:
        d = agg(rows, c)
        if d:
            v_table[c] = d
            print(f"{c:24s} " + "  ".join(
                f"{k}={v[0]:>8.3f}(sd {v[1]:.3f})" for k, v in sorted(d.items())))

    # ---------- 4) 保真度 ----------
    print("\n===== 相对原图切片的结构保真度 =====")
    fid_table = {}
    for c in ["fid_ssim", "fid_ncc", "fid_dE", "fid_dL", "fid_da", "fid_db"]:
        d = agg([r for r in rows if r["mode"] != "base"], c)
        if d:
            fid_table[c] = d
            print(f"{c:12s} " + "  ".join(
                f"{k}={v[0]:>8.4f}(sd {v[1]:.4f})" for k, v in sorted(d.items())))

    # ---------- 5) 分场景 ----------
    print("\n===== 分场景（@2048 三路关键指标） =====")
    groups = sorted({r["group"] for r in rows})
    per_group = {}
    for g in groups:
        sub = [r for r in rows if r["group"] == g and r["mode"] != "base"]
        per_group[g] = {}
        for c in ["nat_skin_hf", "nat_skin_chroma_std", "nat_eye_hf", "nat_mouth_hf",
                  "grain_ratio", "fid_ssim", "fid_dE"]:
            per_group[g][c] = agg(sub, c)
        line = " | ".join(
            f"{c}: " + "/".join(f"{k[:6]}{per_group[g][c].get(k, (float('nan'),))[0]:.2f}"
                                for k in ("qwen21", "flux", "sdxl"))
            for c in ["nat_skin_hf", "nat_skin_chroma_std", "nat_eye_hf"])
        print(f"{g[:18]:20s} {line}")

    # ---------- 6) 逐场景胜出统计 ----------
    print("\n===== 逐切片胜出次数（越高越真实/越保真） =====")
    win = {}
    for metric, higher_better in [("nat_skin_hf", True), ("nat_skin_chroma_std", True),
                                  ("nat_eye_hf", True), ("nat_mouth_hf", True),
                                  ("fid_ssim", True), ("fid_dE", False),
                                  ("grain_ratio", False)]:
        cnt = {m: 0 for m in ("qwen21", "flux", "sdxl")}
        by_key = {}
        for r in rows:
            if r["mode"] == "base":
                continue
            by_key.setdefault((r["group"], r["row"], r["col"], r["idx"]), {})[r["mode"]] = r.get(metric, np.nan)
        for k, d in by_key.items():
            vals = {m: v for m, v in d.items() if v is not None and not (isinstance(v, float) and np.isnan(v))}
            if len(vals) < 3:
                continue
            best = max(vals, key=vals.get) if higher_better else min(vals, key=vals.get)
            cnt[best] += 1
        win[metric] = cnt
        print(f"{metric:22s} {cnt}")

    out = {"nat@2048": nat_table, "view@1024": v_table, "fidelity": fid_table,
           "per_group": per_group, "win_counts": win, "missing": missing}
    with open(os.path.join(args.out, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[out] {os.path.join(args.out, 'analysis.json')}")


if __name__ == "__main__":
    main()
