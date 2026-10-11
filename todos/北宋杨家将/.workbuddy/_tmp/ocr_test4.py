import sys, time, os
sys.path.insert(0, r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp")
import fitz, numpy as np
from rapidocr_onnxruntime import RapidOCR

OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr\test4.txt"
eng = RapidOCR(use_angle_cls=False)
SRC = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
lines = []
doc = fitz.open(os.path.join(SRC, "01杨令公归宋.pdf"))
for scale, clip_band in [(1.0, False), (1.0, True), (1.3, False)]:
    t0 = time.time()
    for pi in (41, 80):
        page = doc[pi]
        r = page.rect
        clip = fitz.Rect(r.x0, r.y0 + r.height*0.68, r.x1, r.y0 + r.height*0.96) if clip_band else None
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, clip=clip)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = np.ascontiguousarray(img[:, :, :3])
        res, _ = eng(img)
        txt = "".join(str(i[1]) for i in (res or []))
        lines.append("scale=%.1f band=%s size=%dx%d  %.2fs" % (scale, clip_band, pix.width, pix.height, (time.time()-t0)/(1 if pi==41 else 2)))
        lines.append("   " + txt[:200])
    lines.append("TOTAL %.2fs for 2 pages" % (time.time()-t0))
    lines.append("")
doc.close()
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
