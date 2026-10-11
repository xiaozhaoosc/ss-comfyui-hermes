# -*- coding: utf-8 -*-
"""诊断：逐集实际页码范围 vs 声明范围；缺口页的 OCR 原文。"""
import os, re, json
from collections import defaultdict

BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
SRC = os.path.join(BASE, r"动画改编方案\杨家将_剧本与分镜全本.html")
OCR = os.path.join(BASE, r".workbuddy\_tmp\ocr\pages.jsonl")
OUT = os.path.join(BASE, r".workbuddy\_tmp\qc\diagnose.txt")

PAGES = {1: 82, 2: 74, 3: 106, 4: 74, 5: 82, 6: 82, 7: 90, 8: 82}

ocr = {}
with open(OCR, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        segs = r.get("segs") or []
        band = [s for s in segs if s.get("yf", 1.0) >= 0.60] or segs
        band.sort(key=lambda s: (s["y"] // 40, s["x"]))
        ocr[(r["book"], r["page"])] = re.sub(r"\s+", "", "".join(s["t"] for s in band))

html = open(SRC, "r", encoding="utf-8").read()
blocks = re.split(r'<div class="ep">', html)[1:]

L = ["逐集：声明范围 vs 实际使用范围", "=" * 96]
for blk in blocks:
    m = re.search(r'<div class="n">(\d+)</div><div class="t">(.*?)</div><div class="pages">(.*?)</div>', blk)
    if not m:
        continue
    num, title, pages = int(m.group(1)), m.group(2).strip(), m.group(3).strip()
    mk = re.findall(r'<span class="pg">(\d+)-(\d+)</span>', blk)
    mk = [(int(a), int(b)) for a, b in mk]
    books = sorted(set(a for a, _ in mk))
    L.append("")
    L.append("第%2d集《%s》  声明：%s" % (num, title, pages))
    for bk in books:
        ps = sorted(set(b for a, b in mk if a == bk))
        lo, hi = min(ps), max(ps)
        body = list(range(5, PAGES[bk]))
        gaps = [x for x in body if lo <= x <= hi and x not in ps]
        L.append("   册%d  实际用 %3d–%3d   声明页数上限 %3d   此区间内未标注 %d 页：%s"
                 % (bk, lo, hi, PAGES[bk], len(gaps),
                    ",".join(map(str, gaps)) if len(gaps) <= 20 else (",".join(map(str, gaps[:20])) + " …")))
        for g in gaps:
            t = ocr.get((bk, g), "")
            L.append("        · 册%d 第%3d 页 OCR：%s" % (bk, g, (t[:110] if t else "（无文字）")))

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("ok")
