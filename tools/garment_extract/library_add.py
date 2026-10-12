# -*- coding: utf-8 -*-
"""把 extract_from_image.py 的提取结果登记进 garment_library。

用法：
  <ComfyUI venv python> tools/garment_extract/library_add.py <run_dir> \
      [--label 显示名] [--source-url URL] [--note 备注]

动作：
  1. 读 <run_dir>/manifest.json；
  2. 每件服装按 name 映射类别（top→tops / bottom→bottoms / 其余→full），
     分配 garment_id（<类别前缀>_<日期>_<两位序号>）；
  3. 拷 transparent.png / white.png / meta.json 进库，原始图存档到 sources/；
  4. 更新 garment_library/index.json（幂等：同 source+category 已入库则跳过）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys

LIB_ROOT = r"D:\ai_projects\ComfyUI\garment_library"
CATEGORY = {"top": "tops", "bottom": "bottoms", "skirt": "bottoms", "pants": "bottoms"}
PREFIX = {"tops": "top", "bottoms": "btm", "full": "full"}


def _sha16(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--label", default="", help="服装显示名（默认用来源文件名）")
    ap.add_argument("--source-url", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    mf_path = os.path.join(a.run_dir, "manifest.json")
    with open(mf_path, encoding="utf-8") as f:
        manifest = json.load(f)
    if not manifest:
        print("manifest 为空，没有可入库的服装")
        return 2

    idx_path = os.path.join(LIB_ROOT, "index.json")
    index = []
    if os.path.isfile(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            index = json.load(f)

    today = dt.date.today().strftime("%Y%m%d")
    src_img = manifest[0]["source_image"]
    src_name = os.path.splitext(os.path.basename(src_img))[0]

    # 原始参考图存档（按内容哈希去重）
    digest = _sha16(src_img)
    src_dir = os.path.join(LIB_ROOT, "sources")
    os.makedirs(src_dir, exist_ok=True)
    src_stored = os.path.join(src_dir, f"{src_name}_{digest}{os.path.splitext(src_img)[1]}")
    if not os.path.isfile(src_stored):
        shutil.copy2(src_img, src_stored)
        print(f"[source] 存档 -> {src_stored}")
    else:
        print(f"[source] 已有存档，跳过拷贝")

    added = 0
    for g in manifest:
        category = CATEGORY.get(g["name"], "full")
        prefix = PREFIX[category]
        seq = 1 + sum(1 for e in index if e["category"] == category and e["id"].startswith(f"{prefix}_{today}"))
        gid = f"{prefix}_{today}_{seq:02d}"
        gdir = os.path.join(LIB_ROOT, category, gid)
        os.makedirs(gdir, exist_ok=True)
        for fn in ("transparent.png", "white.png", "meta.json"):
            shutil.copy2(os.path.join(a.run_dir, g["name"], fn), os.path.join(gdir, fn))

        # 回写 meta 里的库信息
        meta_path = os.path.join(gdir, "meta.json")
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        meta.update({
            "garment_id": gid, "category": category,
            "label": a.label or src_name,
            "source_image": os.path.relpath(src_stored, LIB_ROOT),
            "source_url": a.source_url, "note": a.note,
            "added_date": dt.date.today().isoformat(),
        })
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        entry = {k: meta.get(k) for k in
                 ("garment_id", "category", "label", "mean_hex", "mask_area_px",
                  "crop_bbox", "method", "source_image", "source_url", "added_date")}
        entry["dir"] = os.path.relpath(gdir, LIB_ROOT)
        # 幂等：同来源同类别不重复登记
        if any(e["category"] == category and e.get("source_image") == entry["source_image"]
               for e in index):
            print(f"[skip] {category} 里已有同来源条目")
            continue
        index.append(entry)
        added += 1
        print(f"[add] {gid}  hex={meta['mean_hex']}  -> {gdir}")

    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\nindex.json 更新完成：本次新增 {added}，共 {len(index)} 条 -> {idx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
