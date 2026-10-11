import os, sys, traceback, json

OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\pymupdf_result.txt"
try:
    import fitz
    src = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
    lines = ["pymupdf=" + fitz.VersionBind]
    for f in sorted(os.listdir(src)):
        if not f.lower().endswith(".pdf"):
            continue
        p = os.path.join(src, f)
        try:
            d = fitz.open(p)
            n = d.page_count
            tot = 0
            sample = ""
            for i in range(min(n, 8)):
                t = d[i].get_text().strip()
                tot += len(t)
                if t:
                    sample += t.replace("\n", " ")[:150] + " || "
            pg = d[0]
            lines.append("== %s | pages=%d | textchars_first8=%d | %.0fx%.0f" % (f, n, tot, pg.rect.width, pg.rect.height))
            if sample:
                lines.append("   TXT: " + sample[:500])
            d.close()
        except Exception as e:
            lines.append("== %s | ERROR %r" % (f, e))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
except Exception:
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("FATAL\n" + traceback.format_exc())
