import os, fitz
SRC = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
OUTDIR = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\pages"
files = sorted([f for f in os.listdir(SRC) if f.lower().endswith(".pdf")])
for idx, f in enumerate(files, 1):
    d = fitz.open(os.path.join(SRC, f))
    for i in (1, d.page_count - 1):
        if 0 <= i < d.page_count:
            pix = d[i].get_pixmap(matrix=fitz.Matrix(1.0, 1.0), colorspace=fitz.csRGB)
            pix.save(os.path.join(OUTDIR, "b%02d_p%03d.jpg" % (idx, i + 1)), jpg_quality=82)
    d.close()
