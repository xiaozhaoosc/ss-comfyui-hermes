import os, sys, traceback

OUTDIR = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\pages"
os.makedirs(OUTDIR, exist_ok=True)

def render(pdfname, pages, tag, scale=1.0):
    import fitz
    src = os.path.join(r"D:\BaiduNetdiskDownload\北宋杨家将\漫画", pdfname)
    d = fitz.open(src)
    outs = []
    for i in pages:
        if i >= d.page_count:
            continue
        pg = d[i]
        mat = fitz.Matrix(scale, scale)
        pix = pg.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        name = "%s_p%03d.jpg" % (tag, i + 1)
        path = os.path.join(OUTDIR, name)
        pix.save(path, jpg_quality=85)
        outs.append((name, pix.width, pix.height))
    d.close()
    return outs

log = []
try:
    log.append(str(render("01杨令公归宋.pdf", [0, 1, 2], "b01")))
except Exception:
    log.append(traceback.format_exc())

with open(os.path.join(OUTDIR, "_log.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(log))
