# -*- coding: utf-8 -*-
"""导出 OCR 说明文字为分季可读文本。"""
import os, json, re

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
OCR = os.path.join(BASE, r".workbuddy\_tmp\ocr\pages.jsonl")
OUT = os.path.join(BASE, r".workbuddy\_tmp\ocr")

BOOKS = ["杨令公归宋","邠阳城救驾","殉国李陵碑","六郎收三将","八姐闯幽州","智救杨郡马","大破天门阵","穆桂英挂帅"]
EP = [(1,1,41),(2,42,82),(3,1,37),(4,38,74),(5,1,35),(6,36,70),(7,71,88),(8,89,106),
      (9,1,30),(10,31,60),(11,61,74),(12,1,45),(13,46,82),(14,1,30),(15,31,60),(16,61,82),
      (17,1,22),(18,23,44),(19,45,66),(20,67,90),(21,1,21),(22,22,42),(23,43,62),(24,63,82)]
EPBOOK = {1:1,2:1,3:2,4:2,5:3,6:3,7:3,8:3,9:4,10:4,11:4,12:5,13:5,14:6,15:6,16:6,17:7,18:7,19:7,20:7,21:8,22:8,23:8,24:8}

raw = {}
with open(OCR, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        raw[(r["book"], r["page"])] = r

def norm(s):
    return re.sub(r"\s+", "", s or "")

def caption(rec, page):
    segs = rec.get("segs") or []
    if page <= 4:
        keep = sorted(segs, key=lambda s: (s["y"]//40, s["x"]))
    else:
        band = [s for s in segs if s.get("yf", 1.0) >= 0.60]
        if not band:
            band = segs
        keep = sorted(band, key=lambda s: (s["y"]//40, s["x"]))
    return norm("".join(s["t"] for s in keep))

seasons = {1: list(range(1,9)), 2: list(range(9,17)), 3: list(range(17,25))}
for sk, eps in seasons.items():
    lines = []
    for ep in eps:
        bk = EPBOOK[ep]
        p0 = p1 = None
        for e in EP:
            if e[0] == ep:
                p0, p1 = e[1], e[2]
        lines.append("")
        lines.append("############ 第%d集  册%d《%s》 页%d-%d ############" % (ep, bk, BOOKS[bk-1], p0, p1))
        for p in range(p0, p1+1):
            rec = raw.get((bk, p), {})
            c = caption(rec, p)
            lines.append("[%d-%d] %s" % (bk, p, c if c else "（无文字 / 纯画面页）"))
    path = os.path.join(OUT, "season%d.txt" % sk)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

# 统计
tot = 0; empty = 0
for k, rec in raw.items():
    c = caption(rec, k[1])
    tot += 1
    if len(c) < 6:
        empty += 1
print("pages=%d  low_text=%d" % (tot, empty))
