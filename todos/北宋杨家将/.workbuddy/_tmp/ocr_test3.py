import sys, time, json
sys.path.insert(0, r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp")
import ocr_fast

OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr\test3.txt"
lines = []
jobs = [(1, 41), (1, 80), (3, 53), (3, 105), (7, 45)]
t0 = time.time()
for j in jobs:
    t1 = time.time()
    rec = ocr_fast.ocr_one(j)
    dt = time.time() - t1
    txt = "".join(s["t"] for s in (rec.get("segs") or []))
    lines.append("=== 册%d 页%d | %.2fs | band=%s | segs=%d" % (j[0], j[1]+1, dt, rec.get("band"), len(rec.get("segs") or [])))
    lines.append("  " + txt[:400])
    lines.append("")
lines.append("total %.2fs for %d pages" % (time.time()-t0, len(jobs)))
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
