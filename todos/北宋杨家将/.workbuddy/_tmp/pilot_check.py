# -*- coding: utf-8 -*-
import os, re, json, traceback
import importlib.util, sys
BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
LOG = os.path.join(BASE, r".workbuddy\_tmp\qc\pilot_check.log")
L = []
try:
    spec = importlib.util.spec_from_file_location("pilotmod", os.path.join(BASE, r".workbuddy\_tmp\pilot.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["pilotmod"] = m
    spec.loader.exec_module(m)   # 会重跑 main 并重新生成，无副作用
    allshots = list(m.E1) + list(m.E6)
    ws = [len(en.split()) for *_x, en, _r in [(a, b, c, d, e, f) for a, b, c, d, e, f in allshots]]
    L.append("提示词词数：min=%d max=%d avg=%.0f" % (min(ws), max(ws), sum(ws) / len(ws)))
    over = [(a, len(e.split())) for a, b, c, d, e, f in allshots if len(e.split()) > 95]
    L.append("超 95 词的 = %d 条 %s" % (len(over), over if over else ""))
    L.append("")
    for f in ["杨家将_试播集制作包.html"]:
        p = os.path.join(BASE, "动画改编方案", f)
        s = open(p, "r", encoding="utf-8").read()
        L.append("== %s  (%.1f KB)" % (f, len(s.encode("utf-8")) / 1024))
        toks = set(re.findall(r"@@[A-Z0-9]+@@", s))
        L.append("   残留 token = %s" % (toks if toks else "无"))
        for t in ("html", "head", "body", "div", "table", "tbody", "thead", "pre", "button", "script"):
            o = len(re.findall(r"<%s[ >]" % t, s)); c = len(re.findall(r"</%s>" % t, s))
            if o != c:
                L.append("   *** <%s> %d/%d 不匹配 ***" % (t, o, c))
        L.append("   镜头卡 = %d  需改写标记 = %d" % (len(re.findall(r'<div class="shot', s)),
                                                len(re.findall(r'class="tg rw"', s))))
        L.append("   复制按钮 = %d  <tr> = %d" % (len(re.findall(r'onclick="cp\(this\)"', s)),
                                                len(re.findall(r"<tr[ >]", s))))
    import openpyxl
    wb = openpyxl.load_workbook(os.path.join(BASE, r"动画改编方案\杨家将_试播集切分表.xlsx"))
    L.append("")
    L.append("XLSX: " + " / ".join(wb.sheetnames))
    for n in wb.sheetnames:
        L.append("  [%s] rows=%d" % (n, wb[n].max_row))
    w1 = wb["试播集72镜"]
    d = {}
    for r in range(2, w1.max_row + 1):
        d[w1.cell(r, 4).value] = d.get(w1.cell(r, 4).value, 0) + 1
    L.append("  段长分布 %s  合计 %d 秒" % (d, sum(k * v for k, v in d.items())))
except Exception:
    L.append("FATAL\n" + traceback.format_exc())
open(LOG, "w", encoding="utf-8").write("\n".join(L))
