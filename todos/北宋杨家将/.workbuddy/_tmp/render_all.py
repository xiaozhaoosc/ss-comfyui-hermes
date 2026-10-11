import os, traceback
import fitz

SRC = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
OUTDIR = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\pages"
os.makedirs(OUTDIR, exist_ok=True)

log = []
files = sorted([f for f in os.listdir(SRC) if f.lower().endswith(".pdf")])
for idx, f in enumerate(files, 1):
    tag = "b%02d" % idx
    try:
        d = fitz.open(os.path.join(SRC, f))
        n = d.page_count
        # cover(0), synopsis candidates(2,3,4), first content(5), mid, last
        targets = [0, 2, 3, 4, 5, n // 2, n - 2]
        for i in targets:
            if i < 0 or i >= n:
                continue
            pix = d[i].get_pixmap(matrix=fitz.Matrix(1.0, 1.0), colorspace=fitz.csRGB)
            pix.save(os.path.join(OUTDIR, "%s_p%03d.jpg" % (tag, i + 1)), jpg_quality=82)
        log.append("%s | %s | pages=%d | ok" % (tag, f, n))
        d.close()
    except Exception:
        log.append("%s | %s | FAIL\n%s" % (tag, f, traceback.format_exc()))

with open(os.path.join(OUTDIR, "_log.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(log))
