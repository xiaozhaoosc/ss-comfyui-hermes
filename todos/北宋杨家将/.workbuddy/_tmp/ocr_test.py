import os, time, json, traceback
import fitz, numpy as np
OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr\test.txt"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
lines = []
try:
    from rapidocr_onnxruntime import RapidOCR
    lines.append("import OK")
    t0 = time.time()
    eng = RapidOCR()
    lines.append("engine init %.1fs" % (time.time() - t0))
    doc = fitz.open(r"D:\BaiduNetdiskDownload\北宋杨家将\漫画\01杨令公归宋.pdf")
    for pi in (5, 41, 80):
        t1 = time.time()
        pix = doc[pi].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), colorspace=fitz.csRGB)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = np.ascontiguousarray(img[:, :, :3])
        res, _ = eng(img)
        lines.append("--- page %d  (%.2fs) ---" % (pi + 1, time.time() - t1))
        if res:
            for item in res:
                box, text, score = item[0], item[1], item[2]
                y = int(min(p[1] for p in box))
                lines.append("  y=%4d s=%.2f  %s" % (y, score, text))
        else:
            lines.append("  (no text)")
    doc.close()
except Exception:
    lines.append("FATAL\n" + traceback.format_exc())
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
