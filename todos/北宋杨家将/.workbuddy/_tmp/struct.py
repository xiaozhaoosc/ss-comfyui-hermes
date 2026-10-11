# -*- coding: utf-8 -*-
"""把 OCR JSONL 整理成逐页结构化数据：区分页型、抽取页脚说明文字、映射集数。"""
import os, json, re

OCR = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr\pages.jsonl"
OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr\pages_struct.json"

BOOKS = [
    ("01", "杨令公归宋", 82),
    ("02", "邠阳城救驾", 74),
    ("03", "殉国李陵碑", 106),
    ("04", "六郎收三将", 74),
    ("05", "八姐闯幽州", 82),
    ("06", "智救杨郡马", 82),
    ("07", "大破天门阵", 90),
    ("08", "穆桂英挂帅", 82),
]

# 集数 → (册, 起页, 止页)  含册边界切分
EPISODES = [
    (1,  1, 1, 41), (2,  1, 42, 82),
    (3,  2, 1, 37), (4,  2, 38, 74),
    (5,  3, 1, 35), (6,  3, 36, 70), (7, 3, 71, 88), (8, 3, 89, 106),
    (9,  4, 1, 30), (10, 4, 31, 60), (11, 4, 61, 74),
    (12, 5, 1, 45), (13, 5, 46, 82),
    (14, 6, 1, 30), (15, 6, 31, 60), (16, 6, 61, 82),
    (17, 7, 1, 22), (18, 7, 23, 44), (19, 7, 45, 66), (20, 7, 67, 90),
    (21, 8, 1, 21), (22, 8, 22, 42), (23, 8, 43, 62), (24, 8, 63, 82),
]

def episode_of(book, page):
    hits = [e for e in EPISODES if e[1] == book and e[2] <= page <= e[3]]
    return hits[0][0] if hits else None

def page_type(book, page):
    if page == 1:
        return "封面"
    if page == 2:
        return "题名页"
    if page == 3:
        return "内容简介"
    if page == 4:
        return "内容简介/版权"
    if page == 5:
        return "正文起"
    return "正文"

def norm(s):
    return re.sub(r"\s+", "", s or "")

rows = []
with open(OCR, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        b, p = rec["book"], rec["page"]
        segs = rec.get("segs") or []
        H = rec.get("h") or 1536
        # 页脚说明文字带：图片下部 42%
        band = [s for s in segs if s["y"] >= H * 0.58]
        if not band:
            band = segs
        band.sort(key=lambda s: (s["y"] // 40, s["x"]))
        caption = norm("".join(s["t"] for s in band))
        # 编号前缀（连环画每页有 "39." 之类）
        m = re.match(r"^[（(]?(\d{1,3})[.．、）)]", caption)
        num = m.group(1) if m else ""
        body = caption[m.end():] if m else caption
        rows.append({
            "book": b,
            "bookname": BOOKS[b - 1][1],
            "page": p,
            "ptype": page_type(b, p),
            "num": num,
            "text": body,
            "chars": len(body),
            "ep": episode_of(b, p),
        })

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)

# 概览
tot = len(rows)
withtext = sum(1 for r in rows if r["chars"] > 8)
print("rows=%d  with_text=%d (%.1f%%)" % (tot, withtext, 100.0 * withtext / max(tot, 1)))
