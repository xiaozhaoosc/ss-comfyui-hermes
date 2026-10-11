# -*- coding: utf-8 -*-
import os, re
BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
H = os.path.join(BASE, r"动画改编方案\试片\杨家将_六镜试片.html")
LOG = os.path.join(BASE, r".workbuddy\_tmp\div_scan.log")
s = open(H, "r", encoding="utf-8").read()

# 去掉 style 与 script 内容，避免误判
s2 = re.sub(r"<style>.*?</style>", "<style></style>", s, flags=re.S)
s2 = re.sub(r"<script>.*?</script>", "<script></script>", s2, flags=re.S)

depth = 0
lines = []
for m in re.finditer(r"</?div[ >]", s2):
    tok = m.group(0)
    depth += 1 if tok.startswith("<div") else -1
    if depth < 0 or depth == 0:
        ln = s2[:m.start()].count("\n") + 1
        ctx = s2[max(0, m.start()-160):m.start()+40].replace("\n", " ")
        lines.append("depth=%d @line %d ... %s" % (depth, ln, ctx[-180:]))
        if depth < 0:
            break

out = ["final depth = %d" % depth, "events at depth<=0: %d" % len(lines)] + lines
open(LOG, "w", encoding="utf-8").write("\n".join(out))
