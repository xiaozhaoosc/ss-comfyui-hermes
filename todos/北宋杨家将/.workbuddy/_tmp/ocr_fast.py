# -*- coding: utf-8 -*-
"""逐页 OCR（优化版）：只裁页脚文字带 + 多进程并行。增量写 JSONL。"""
import os, sys, json, time, traceback

SRC = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
OUTDIR = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr"
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "pages.jsonl")
LOG = os.path.join(OUTDIR, "ocr.log")

FILES = sorted([f for f in os.listdir(SRC) if f.lower().endswith(".pdf")])

# 每册页数（用于生成任务表）
PAGECOUNT = {}


def log(msg):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))


_engine = None
def get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def ocr_one(job):
    """job = (book_idx, page_idx)  返回记录 dict"""
    import fitz, numpy as np
    bi, pi = job
    f = FILES[bi - 1]
    key = "%02d_%03d" % (bi, pi + 1)
    try:
        doc = fitz.open(os.path.join(SRC, f))
        page = doc[pi]
        r = page.rect
        scale = 1.6
        mat = fitz.Matrix(scale, scale)
        # 页码 1-4 为封面/题名/简介：整页 OCR
        if pi + 1 <= 4:
            clip = None
        else:
            clip = fitz.Rect(r.x0, r.y0 + r.height * 0.68, r.x1, r.y0 + r.height * 0.96)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, clip=clip)
        doc.close()
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = np.ascontiguousarray(img[:, :, :3])
        res, _ = get_engine()(img)
        segs = []
        if res:
            for item in res:
                box = item[0]
                text = str(item[1])
                try:
                    score = float(item[2])
                except Exception:
                    score = 0.0
                ys = [float(p[1]) for p in box]
                xs = [float(p[0]) for p in box]
                segs.append({
                    "t": text, "s": round(score, 3),
                    "y": int(min(ys)), "x": int(min(xs)),
                    "h": int(max(ys) - min(ys)),
                    "yf": round(min(ys) / max(pix.height, 1), 3),
                })
        return {
            "key": key, "book": bi, "page": pi + 1, "pdf": f,
            "w": pix.width, "h": pix.height,
            "band": (pi + 1 > 4), "segs": segs,
        }
    except Exception:
        return {"key": key, "book": bi, "page": pi + 1, "pdf": f,
                "error": traceback.format_exc(), "segs": []}


def main():
    import fitz
    # 建任务表
    jobs = []
    for bi, f in enumerate(FILES, 1):
        d = fitz.open(os.path.join(SRC, f))
        PAGECOUNT[bi] = d.page_count
        d.close()
        for pi in range(PAGECOUNT[bi]):
            jobs.append((bi, pi))

    done = set()
    if os.path.exists(OUT):
        with open(OUT, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["key"])
                except Exception:
                    pass
    todo = [j for j in jobs if ("%02d_%03d" % (j[0], j[1] + 1)) not in done]
    log("total=%d done=%d todo=%d pages=%r" % (len(jobs), len(done), len(todo), PAGECOUNT))

    import multiprocessing as mp
    nw = min(4, max(2, (os.cpu_count() or 4) - 2))
    log("workers=%d cpu=%s" % (nw, os.cpu_count()))
    t0 = time.time()
    n = 0
    with open(OUT, "a", encoding="utf-8") as fh, mp.Pool(nw) as pool:
        for rec in pool.imap_unordered(ocr_one, todo, chunksize=4):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            if n % 25 == 0:
                el = time.time() - t0
                log("progress %d/%d  %.1f s/page  eta %.1f min" % (n, len(todo), el / n, el / n * (len(todo) - n) / 60))
    log("DONE %d pages in %.1f min" % (n, (time.time() - t0) / 60))


if __name__ == "__main__":
    main()
