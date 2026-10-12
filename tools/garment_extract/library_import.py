#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把既有提取产物批量导入服装库 garment_library/

支持两种源布局：
  A) <src>/<视频目录>/garment/garment_<rank>_transparent.png (+ _white.png)
     —— tools/garment_extract/extract_garment.py 的产物。
     注意：rank 1..N 是【同一件服装的不同候选帧版本】（按清晰度×面积排序，rank1 最佳），
     不是不同部位。因此每个 <视频目录> 记为 1 件服装，其余 rank 存为备选版本 alts/。
  B) <src>/<任意名>/{transparent.png, white.png}
     —— tools/garment_extract/extract_from_image.py 的产物，每个子目录 1 件。

用法:
  python tools/garment_extract/library_import.py output/2026-10-11/garment_extract \
      --category full --source-url <链接> --note "说明"

常用参数:
  --category   full|tops|bottoms（默认 full；整套穿搭/连衣裙填 full）
  --date       YYYYMMDD（默认今天）
  --only-rank  只导入指定 rank（默认全部，rank1 作为主版本）
  --dry-run    只打印计划，不写文件
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LIB = os.path.join(ROOT, "garment_library")

CAT_PREFIX = {"full": "full", "tops": "top", "bottoms": "btm"}
THUMB_MAX = 320

def hex_of(rgb_arr, mask):
    """mask 区域内 RGB 均值 -> #rrggbb"""
    if mask is None or mask.sum() < 10:
        return "#000000"
    mean = np.asarray(rgb_arr, np.float32)[mask].mean(0)
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in mean)


def sha1(path, n=12):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:n]


def mask_stats(png_path):
    """返回 (主色hex, mask像素数, (w,h), 不透明占比)"""
    im = Image.open(png_path)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    a = np.asarray(im.split()[-1], np.float32) / 255.0
    m = a > 0.5
    rgb = np.asarray(im.convert("RGB"), np.uint8)
    hexc = hex_of(rgb, m) if m.sum() > 10 else "#000000"
    return hexc, int(m.sum()), im.size, float(m.mean())


def discover(src):
    """返回 [(unit_dir, label, [rank_paths...], meta_src)] —— 每个 unit 是一件服装"""
    units = []
    for name in sorted(os.listdir(src)):
        udir = os.path.join(src, name)
        if not os.path.isdir(udir):
            continue
        # 模式 A：garment/garment_<rank>_*
        gdir = os.path.join(udir, "garment")
        if os.path.isdir(gdir):
            ranks = {}
            for f in os.listdir(gdir):
                mm = re.match(r"garment_(\d+)_transparent\.png$", f)
                if mm:
                    ranks[int(mm.group(1))] = os.path.join(gdir, f)
            if ranks:
                units.append((udir, name, [ranks[k] for k in sorted(ranks)], "A"))
                continue
        # 模式 B：直接 transparent.png
        tp = os.path.join(udir, "transparent.png")
        if os.path.isfile(tp):
            units.append((udir, name, [tp], "B"))
    return units


def load_manifest(src, unit_dir):
    """尽量找到 manifest.json 里属于该 unit 的记录"""
    mf = os.path.join(src, "manifest.json")
    if not os.path.isfile(mf):
        mf = os.path.join(os.path.dirname(src), "manifest.json")
    if not os.path.isfile(mf):
        return {}
    try:
        with open(mf, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    base = os.path.basename(unit_dir)
    out = {}
    for r in data:
        if isinstance(r, dict) and str(r.get("video", "")).startswith(base):
            out[int(r.get("rank", 0))] = r
    return out


def next_id(category, date, existing):
    prefix = CAT_PREFIX.get(category, category)
    pat = re.compile(rf"^{prefix}_{date}_(\d+)$")
    mx = 0
    for g in existing:
        mm = pat.match(g.get("garment_id", ""))
        if mm:
            mx = max(mx, int(mm.group(1)))
    return f"{prefix}_{date}_{mx + 1:02d}"


def short_label(name):
    """2026-10-05_05-59-28_DeGg3wkgn4p_1 -> DeGg3wkgn4p_1"""
    parts = name.split("_")
    if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) <= 2:
        return "_".join(parts[-2:])
    return parts[-1] if len(parts) >= 2 and len(parts[-1]) >= 4 else name


def make_thumb(white_png, dst):
    im = Image.open(white_png).convert("RGB")
    im.thumbnail((THUMB_MAX, THUMB_MAX), Image.LANCZOS)
    im.save(dst)


def main():
    ap = argparse.ArgumentParser(description="既有服装提取产物批量入库")
    ap.add_argument("src", help="提取产物根目录（含若干 <视频目录>/garment/）")
    ap.add_argument("--category", default="full", choices=["full", "tops", "bottoms"])
    ap.add_argument("--date", default=None, help="YYYYMMDD，默认今天")
    ap.add_argument("--source-url", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--only-rank", type=int, default=0, help="只导入该 rank（默认全部）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    if not os.path.isdir(src):
        sys.exit(f"源目录不存在: {src}")
    date = a.date or time.strftime("%Y%m%d")
    added = time.strftime("%Y-%m-%d")

    os.makedirs(LIB, exist_ok=True)
    idx_path = os.path.join(LIB, "index.json")
    existing = []
    if os.path.isfile(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            existing = json.load(f)

    units = discover(src)
    if not units:
        sys.exit(f"未在 {src} 下找到可导入的服装产物")

    seen_hash = set()
    for g in existing:
        sp = g.get("source_image", "")
        mm = re.search(r"_([0-9a-f]{12})\.", sp)
        if mm:
            seen_hash.add(mm.group(1))

    added_n = 0
    for udir, name, paths, mode in units:
        if a.only_rank and mode == "A":
            paths = [p for p in paths if f"garment_{a.only_rank}_" in os.path.basename(p)]
        if not paths:
            continue
        mf = load_manifest(src, udir)
        primary = paths[0]
        hexc, area, (w, h), fill = mask_stats(primary)

        # 源图存档（模式 A 有 keyframes/；模式 B 用同目录 source/ 或跳过）
        src_img = ""
        kf = os.path.join(udir, "keyframes")
        frame_name = mf.get(1, {}).get("source_frame", "")
        cand = os.path.join(kf, frame_name + ".jpg") if frame_name else ""
        if not os.path.isfile(cand):
            for ext in (".jpg", ".png", ".webp"):
                for base in (frame_name, "source", "best_frame"):
                    p = os.path.join(udir, base + ext)
                    if os.path.isfile(p):
                        cand = p
                        break
                if os.path.isfile(cand):
                    break
        if os.path.isfile(cand):
            hs = sha1(cand)
            if hs in seen_hash:
                print(f"[skip] {name}: 源图已入库过（{os.path.basename(cand)}）")
                continue
            seen_hash.add(hs)
            dst_src = os.path.join(LIB, "sources", f"{short_label(name)}_{hs}{os.path.splitext(cand)[1]}")
            src_img = os.path.relpath(dst_src, LIB)
            if not a.dry_run:
                os.makedirs(os.path.dirname(dst_src), exist_ok=True)
                Image.open(cand).save(dst_src)
        elif not a.dry_run:
            # 无原图时退化为用主版本白底图做 sources 记录
            pass

        gid = next_id(a.category, date, existing)
        gdir = os.path.join(LIB, a.category, gid)
        versions = []
        if not a.dry_run:
            os.makedirs(gdir, exist_ok=True)
            os.makedirs(os.path.join(gdir, "alts"), exist_ok=True)

        for i, p in enumerate(paths, 1):
            rank = int(re.search(r"garment_(\d+)_", os.path.basename(p)).group(1)) if mode == "A" else i
            white_p = p.replace("_transparent.png", "_white.png")
            if not os.path.isfile(white_p):
                rgba = Image.open(p)
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, (0, 0), rgba)
                white_p = None
            if i == 1:
                t_dst = os.path.join(gdir, "transparent.png")
                w_dst = os.path.join(gdir, "white.png")
                vfiles = ["transparent.png", "white.png"]
            else:
                t_dst = os.path.join(gdir, "alts", f"rank{rank}_transparent.png")
                w_dst = os.path.join(gdir, "alts", f"rank{rank}_white.png")
                vfiles = [f"alts/rank{rank}_transparent.png", f"alts/rank{rank}_white.png"]
            if not a.dry_run:
                Image.open(p).save(t_dst)
                if white_p:
                    Image.open(white_p).save(w_dst)
                else:
                    bg.save(w_dst)
                if i == 1:
                    make_thumb(w_dst, os.path.join(gdir, "thumb.png"))
            hx, ar_, sz, fl = mask_stats(p)
            versions.append({
                "rank": rank,
                "primary": i == 1,
                "size": list(sz),
                "mean_hex": hx,
                "mask_area_px": ar_,
                "fill_ratio": round(fl, 3),
                "source_frame": mf.get(rank, {}).get("source_frame", ""),
                "sharpness": mf.get(rank, {}).get("sharpness"),
                "method": mf.get(rank, {}).get("method", ""),
                "crop_bbox": mf.get(rank, {}).get("crop_bbox"),
                "files": vfiles,
            })

        meta = {
            "garment_id": gid,
            "category": a.category,
            "label": short_label(name),
            "mean_hex": hexc,
            "mask_area_px": area,
            "size": [w, h],
            "aspect": round(w / h, 3),
            "fill_ratio": round(fill, 3),
            "method": versions[0].get("method", ""),
            "versions": versions,
            "source_image": src_img,
            "source_url": a.source_url,
            "origin_dir": os.path.relpath(udir, ROOT),
            "added_date": added,
            "note": a.note,
        }
        if not a.dry_run:
            with open(os.path.join(gdir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

        existing.append({
            "garment_id": gid,
            "category": a.category,
            "label": meta["label"],
            "mean_hex": hexc,
            "mask_area_px": area,
            "size": [w, h],
            "method": meta["method"],
            "versions_count": len(versions),
            "source_image": src_img,
            "source_url": a.source_url,
            "origin_dir": meta["origin_dir"],
            "added_date": added,
            "dir": os.path.relpath(gdir, LIB),
        })
        added_n += 1
        print(f"[add] {gid} {hexc} {w}x{h} v{len(versions)} label={meta['label']} -> {os.path.relpath(gdir, ROOT)}")

    if not a.dry_run:
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"\nindex.json 更新完成：本次新增 {added_n}，共 {len(existing)} 条 -> {idx_path}")
    else:
        print(f"\n[dry-run] 计划新增 {added_n} 件，未写文件")


if __name__ == "__main__":
    main()
