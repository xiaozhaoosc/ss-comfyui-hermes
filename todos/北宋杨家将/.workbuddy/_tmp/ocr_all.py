# -*- coding: utf-8 -*-
"""逐页 OCR：抽每页说明文字（连环画页脚 caption）。结果增量写入 JSONL。"""
import os, sys, json, time, traceback

SRC = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
OUTDIR = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr"
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "pages.jsonl")
LOG = os.path.join(OUTDIR, "ocr.log")

import fitz
import numpy as np

engine = None
def get_engine():
    global engine
    if engine is None:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
    return engine

def log(msg):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")

files = sorted([f for f in os.listdir(SRC) if f.lower().endswith(".pdf")])
log("START %s" % time.strftime("%H:%M:%S"))

done = set()
if os.path.exists(OUT):
    with open(OUT, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                done.add(json.loads(line)["key"])
            except Exception:
                pass
log("already done: %d" % len(done))

total = 0
t0 = time.time()
with open(OUT, "a", encoding="utf-8") as fh:
    for bi, f in enumerate(files, 1):
        doc = fitz.open(os.path.join(SRC, f))
        n = doc.page_count
        for pi in range(n):
            key = "%02d_%03d" % (bi, pi + 1)
            if key in done:
                continue
            try:
                page = doc[pi]
                # 2 倍渲染，提升 OCR 精度
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), colorspace=fitz.csRGB)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                img = np.ascontiguousarray(img[:, :, :3])
                res, _ = get_engine()(img)
                segs = []
                if res:
                    for item in res:
                        box, text, score = item[0], item[1], item[2]
                        ys = [p[1] for p in box]
                        xs = [p[0] for p in box]
                        segs.append({
                            "t": text,
                            "s": round(float(score), 3),
                            "y": int(min(ys)),
                            "x": int(min(xs)),
                            "h": int(max(ys) - min(ys)),
                        })
                rec = {
                    "key": key, "book": bi, "page": pi + 1,
                    "pdf": f, "w": pix.width, "h": pix.height,
                    "segs": segs,
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                total += 1
                if total % 20 == 0:
                    el = time.time() - t0
                    log("progress %d pages, %.1fs, %.2fs/page" % (total, el, el / total))
            except Exception:
                log("ERR %s\n%s" % (key, traceback.format_exc()))
                fh.write(json.dumps({"key": key, "book": bi, "page": pi + 1,
                                     "pdf": f, "error": True, "segs": []}, ensure_ascii=False) + "\n")
                fh.flush()
        doc.close()
        log("book %d done: %s" % (bi, f))

log("ALL DONE %d pages in %.1fs" % (total, time.time() - t0))
