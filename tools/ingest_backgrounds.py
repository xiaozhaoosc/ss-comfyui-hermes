#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Flow 出的背景图按 manifest 入库 background_library/。

用法:
  venv/Scripts/python.exe tools/ingest_backgrounds.py \
      --manifest background_library/manifest.json \
      --src output/2026-10-17/flow_images --dest background_library --date 2026-10-17
"""
import argparse
import datetime
import glob
import json
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def phash64(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(g, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    d = cv2.dct(small)[:8, :8].flatten()
    return int.from_bytes(np.packbits(d > np.median(d)).tobytes(), "big")


def hamming(a, b):
    return bin(a ^ b).count("1")


def lap_var(img):
    return float(cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


def estimate_ground_y(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H = g.shape[0]
    roi = g[int(H * 0.4):, :]
    sob = np.abs(cv2.Sobel(roi, cv2.CV_64F, 0, 1, ksize=3)).sum(axis=1)
    sob = np.convolve(sob, np.ones(9) / 9.0, mode="same")
    row = int(np.argmax(sob)) + int(H * 0.4)
    return min(max(row / H, 0.4), 0.95)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="background_library/manifest.json")
    ap.add_argument("--src", required=True)
    ap.add_argument("--dest", default="background_library")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--flow-project", default="")
    args = ap.parse_args()

    items = json.load(open(args.manifest, encoding="utf-8"))["items"]
    idx_path = os.path.join(args.dest, "index.json")
    index = []
    if os.path.exists(idx_path):
        index = json.load(open(idx_path, encoding="utf-8"))
    by_id = {e["bg_id"]: e for e in index}

    for it in items:
        pat = os.path.join(args.src, it["flow_task_name"] + "_*.png")
        files = sorted(glob.glob(pat), key=os.path.getmtime, reverse=True)
        if not files:
            print(f"[skip] {it['bg_id']}: 无产物")
            continue
        d = os.path.join(args.dest, "backgrounds", it["bg_id"])
        os.makedirs(os.path.join(d, "alts"), exist_ok=True)
        main_path = os.path.join(d, "main.png")
        if os.path.exists(main_path) and it["bg_id"] in by_id:
            files = [f for f in files if os.path.abspath(f) !=
                     os.path.abspath(by_id[it["bg_id"]]["file"])]
        else:
            shutil_src = files[0]
            cv2.imwrite(main_path, cv2.imread(shutil_src))
            files = files[1:]
        alts = []
        for i, f in enumerate(files, 1):
            dst = os.path.join(d, "alts", f"{i:02d}.png")
            if not os.path.exists(dst):
                cv2.imwrite(dst, cv2.imread(f))
            alts.append({"file": f"backgrounds/{it['bg_id']}/alts/{i:02d}.png",
                         "src": f, "lap_var": round(lap_var(cv2.imread(dst)), 1)})

        img = cv2.imread(main_path)
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        entry = {
            "bg_id": it["bg_id"], "slug": it["slug"], "name_cn": it["name_cn"],
            "category": it["category"], "scene_type": it["scene_type"],
            "person_space": it["person_space"], "light_dir": it["light_dir"],
            "ground_y": round(estimate_ground_y(img), 4),
            "ground_y_manifest": it["ground_y"],
            "file": f"backgrounds/{it['bg_id']}/main.png",
            "thumb": f"backgrounds/{it['bg_id']}/thumb.png",
            "alts": alts,
            "width": w, "height": h,
            "aspect": round(w / h, 4),
            "prompt_note": it["scene"][:120],
            "source": "google_flow",
            "flow_project_url": args.flow_project,
            "flow_task_name": it["flow_task_name"],
            "phash": phash64(img),
            "quality": {
                "lap_var": round(lap_var(img), 1),
                "mean_luma": round(float(gray.mean()), 1),
                "std": round(float(gray.std()), 1),
                "black_ratio": round(float((gray < 10).mean()), 4),
                "person_ratio": None, "dup_of": None,
            },
            "added_date": args.date,
        }
        th = cv2.resize(img, (288, int(round(288 * h / w))), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(d, "thumb.png"), th)
        json.dump(entry, open(os.path.join(d, "meta.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        if it["bg_id"] in by_id:
            index = [e for e in index if e["bg_id"] != it["bg_id"]]
        index.append(entry)
        print(f"[ok] {it['bg_id']}: {w}x{h}, alts={len(alts)}")

    # 批内近似重复标记
    for a in index:
        for b in index:
            if a is b or a.get("quality", {}).get("dup_of"):
                continue
            if a.get("phash") and b.get("phash") and \
                    hamming(a["phash"], b["phash"]) <= 6:
                worse, better = (a, b) if a["quality"]["lap_var"] <= b["quality"]["lap_var"] \
                    else (b, a)
                worse.setdefault("quality", {})["dup_of"] = better["bg_id"]
                print(f"[dup] {worse['bg_id']} ≈ {better['bg_id']}")

    json.dump(index, open(idx_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"index.json: {len(index)} 条")


if __name__ == "__main__":
    main()
