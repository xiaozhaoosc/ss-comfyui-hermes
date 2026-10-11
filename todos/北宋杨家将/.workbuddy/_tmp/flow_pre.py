# -*- coding: utf-8 -*-
import os, re
BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
D = os.path.join(BASE, r"动画改编方案\试片")
LOG = os.path.join(BASE, r".workbuddy\_tmp\flow_pre.log")
s = open(os.path.join(D, "杨家将_六镜试片_GoogleFlow版.html"), "r", encoding="utf-8").read()
pres = re.findall(r"<pre>(.*?)</pre>", s, re.S)
L = ["<pre> blocks = %d（6 条正稿 + 1 条 Extend）" % len(pres)]
NEG = ["no ", "not ", "without ", "avoid", "don't", "不要", "禁止", "无阴影", "无渐变"]
for i, p in enumerate(pres, 1):
    words = len(p.split())
    hits = [n for n in NEG if n in p.lower()]
    L.append("  #%d  %d 词  否定式命中=%s" % (i, words, hits if hits else "无"))
    L.append("      " + p[:90].replace("\n", " ") + " …")
open(LOG, "w", encoding="utf-8").write("\n".join(L))
