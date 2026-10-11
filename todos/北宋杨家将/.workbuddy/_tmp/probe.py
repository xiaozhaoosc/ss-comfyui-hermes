import os, sys, json

OUT = r"D:\BaiduNetdiskDownload\北宋杨家将\.workbuddy\_tmp\probe_result.txt"
lines = []
lines.append("python=" + sys.version)

try:
    import pypdf
    lines.append("pypdf=" + pypdf.__version__)
except Exception as e:
    lines.append("pypdf MISSING: " + repr(e))

try:
    import fitz
    lines.append("pymupdf=" + fitz.__doc__.split("\n")[0])
except Exception as e:
    lines.append("pymupdf MISSING: " + repr(e))

src = r"D:\BaiduNetdiskDownload\北宋杨家将\漫画"
lines.append("dir_exists=" + str(os.path.isdir(src)))
if os.path.isdir(src):
    for f in sorted(os.listdir(src)):
        lines.append("FILE: " + f)

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
