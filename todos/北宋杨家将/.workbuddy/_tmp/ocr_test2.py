import os, time, json, traceback
import fitz, numpy as np
OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr\test2.txt"
lines = []
try:
    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    doc = fitz.open(r"D:\BaiduNetdiskDownload\北宋杨家将\漫画\01杨令公归宋.pdf")
    for pi in (41, 80):
        pix = doc[pi].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), colorspace=fitz.csRGB)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = np.ascontiguousarray(img[:, :, :3])
        t1 = time.time()
        res, elapse = eng(img)
        dt = time.time() - t1
        lines.append("=== page %d | %.2fs | type=%s | len=%s" % (pi + 1, dt, type(res).__name__, len(res) if res else 0))
        if res:
            lines.append("first item type=%s" % type(res[0]).__name__)
            lines.append("first item repr=" + repr(res[0])[:600])
        lines.append("elapse=%r" % (elapse,))
        lines.append("")
    doc.close()
except Exception:
    lines.append("FATAL\n" + traceback.format_exc())
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
