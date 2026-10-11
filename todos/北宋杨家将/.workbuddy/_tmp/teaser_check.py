# -*- coding: utf-8 -*-
import os, re, json, traceback
BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
H = os.path.join(BASE, r"动画改编方案\试片\杨家将_六镜试片.html")
TMP = os.path.join(BASE, r".workbuddy\_tmp")
LOG = os.path.join(TMP, "teaser_check.log")
L = []
try:
    s = open(H, "r", encoding="utf-8").read()
    L.append("html chars = %d" % len(s))
    for t in ("html", "head", "body", "div", "script", "table", "tbody", "thead", "figure"):
        o = len(re.findall(r"<%s[ >]" % t, s)); c = len(re.findall(r"</%s>" % t, s))
        L.append("  <%s> %d / %d %s" % (t, o, c, "OK" if o == c else "*** MISMATCH ***"))
    m = re.search(r"const SHOTS=(\[.*?\]);\s*const TOTAL=(\d+);", s, re.S)
    if not m:
        L.append("SHOTS array NOT FOUND")
    else:
        arr = json.loads(m.group(1))
        L.append("SHOTS parsed OK: %d shots, total=%s s" % (len(arr), m.group(2)))
        tot = sum(x["sec"] for x in arr)
        L.append("  sum(sec) = %d  %s" % (tot, "OK" if tot == int(m.group(2)) else "*** MISMATCH ***"))
        for x in arr:
            L.append("   %s %-14s %2ds  %s" % (x["n"], x["title"], x["sec"], x["frm"]))
    # 抽出 <script> 内容交给 node 做语法检查
    sc = re.findall(r"<script>(.*?)</script>", s, re.S)
    L.append("script blocks = %d" % len(sc))
    p = os.path.join(TMP, "teaser_script.js")
    open(p, "w", encoding="utf-8").write(sc[-1] if sc else "")
    L.append("script written -> %s (%d chars)" % (p, len(sc[-1]) if sc else 0))
except Exception:
    L.append("FATAL\n" + traceback.format_exc())
open(LOG, "w", encoding="utf-8").write("\n".join(L))
