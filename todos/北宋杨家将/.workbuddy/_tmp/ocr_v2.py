# -*- coding: utf-8 -*-
"""逐页 OCR（v2）：修 Windows spawn 导入 + 失败降级为串行。增量写 JSONL。"""
import os, sys, json, time, traceback

# 关键：限制每个进程的线程数，否则 4 个 worker 各开 16 线程 → 严重争抢，反而更慢
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "ORT_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SRC = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
OUTDIR = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\ocr"
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "pages.jsonl")
LOG = os.path.join(OUTDIR, "ocr.log")

FILES = sorted([f for f in os.listdir(SRC) if f.lower().endswith(".pdf")])


def log(msg):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))


_engine = None
def get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR(use_angle_cls=False)
    return _engine


def ocr_one(job):
    import fitz, numpy as np
    bi, pi = job
    f = FILES[bi - 1]
    key = "%02d_%03d" % (bi, pi + 1)
    try:
        doc = fitz.open(os.path.join(SRC, f))
        page = doc[pi]
        r = page.rect
        scale = 1.3
        # 整页原尺寸渲染：det 的 limit_side_len=736 会对窄条上采样，反而更慢且截断文字
        clip = None
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, clip=clip)
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
                segs.append({"t": text, "s": round(score, 3),
                             "y": int(min(ys)), "x": int(min(xs)),
                             "h": int(max(ys) - min(ys)),
                             "yf": round(min(ys) / max(pix.height, 1), 3)})
        return {"key": key, "book": bi, "page": pi + 1, "pdf": f,
                "w": pix.width, "h": pix.height, "band": (pi + 1 > 4), "segs": segs}
    except Exception:
        return {"key": key, "book": bi, "page": pi + 1, "pdf": f,
                "error": traceback.format_exc(), "segs": []}


def write_rec(fh, rec):
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    fh.flush()


def main():
    import fitz
    jobs = []
    for bi, f in enumerate(FILES, 1):
        d = fitz.open(os.path.join(SRC, f))
        for pi in range(d.page_count):
            jobs.append((bi, pi))
        d.close()

    done = set()
    if os.path.exists(OUT):
        with open(OUT, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["key"])
                except Exception:
                    pass
    todo = [j for j in jobs if ("%02d_%03d" % (j[0], j[1] + 1)) not in done]
    log("v2 total=%d done=%d todo=%d" % (len(jobs), len(done), len(todo)))

    nw = min(8, max(4, (os.cpu_count() or 4) // 2))
    t0 = time.time()
    n = 0
    try:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        with open(OUT, "a", encoding="utf-8") as fh, ctx.Pool(nw) as pool:
            log("pool started workers=%d" % nw)
            for rec in pool.imap_unordered(ocr_one, todo, chunksize=4):
                write_rec(fh, rec)
                n += 1
                if n % 20 == 0:
                    el = time.time() - t0
                    log("P %d/%d  %.2f s/p  eta %.1f min" % (n, len(todo), el / n, el / n * (len(todo) - n) / 60))
    except Exception:
        log("POOL FAILED, fallback to serial:\n" + traceback.format_exc())
        with open(OUT, "a", encoding="utf-8") as fh:
            for j in todo:
                key = "%02d_%03d" % (j[0], j[1] + 1)
                if key in done:
                    continue
                rec = ocr_one(j)
                write_rec(fh, rec)
                n += 1
                if n % 20 == 0:
                    el = time.time() - t0
                    log("S %d/%d  %.2f s/p  eta %.1f min" % (n, len(todo), el / n, el / n * (len(todo) - n) / 60))
    log("DONE %d pages in %.1f min" % (n, (time.time() - t0) / 60))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL\n" + traceback.format_exc())
