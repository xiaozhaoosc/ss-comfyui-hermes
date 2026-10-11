# -*- coding: utf-8 -*-
import os, re, json, traceback
BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
D = os.path.join(BASE, r"动画改编方案\试片")
LOG = os.path.join(BASE, r".workbuddy\_tmp\flow_check.log")
L = []
try:
    h = os.path.join(D, "杨家将_六镜试片_GoogleFlow版.html")
    s = open(h, "r", encoding="utf-8").read()
    L.append("HTML %.1f KB" % (len(s.encode("utf-8")) / 1024))
    for t in ("html", "head", "body", "div", "script", "table", "tbody", "thead", "pre", "button"):
        o = len(re.findall(r"<%s[ >]" % t, s)); c = len(re.findall(r"</%s>" % t, s))
        L.append("  <%s> %d/%d %s" % (t, o, c, "OK" if o == c else "*** MISMATCH ***"))
    # 图片内嵌数
    L.append("  embedded images = %d" % len(re.findall(r"data:image/jpeg;base64,", s)))
    L.append("  Shot cards = %d" % len(re.findall(r'<div class="shot">', s)))
    L.append("  copy buttons = %d" % len(re.findall(r"onclick=\"cp\(this\)\"", s)))
    # 负向词残留检查（Flow 版不应出现否定式指令）
    bad = []
    for kw in ["no shading", "no gradients", "no 3D", "不要阴影", "不要渐变", "不要3D"]:
        if kw.lower() in s.lower():
            bad.append(kw)
    L.append("  负向词残留 = %s" % (bad if bad else "无（符合 Flow 要求）"))
    # TXT
    t = os.path.join(D, "Flow提示词_可直接粘贴.txt")
    ts = open(t, "r", encoding="utf-8").read()
    L.append("TXT %.1f KB, 镜段数 = %d" % (len(ts.encode("utf-8")) / 1024, ts.count("【镜 ")))
    L.append("  含 Extend 续写 = %s" % ("是" if "[Extend 续写 4 秒]" in ts else "否"))
    # 目录
    L.append("目录文件：")
    for f in sorted(os.listdir(D)):
        L.append("  %s  %.0f KB" % (f, os.path.getsize(os.path.join(D, f)) / 1024))
except Exception:
    L.append("FATAL\n" + traceback.format_exc())
open(LOG, "w", encoding="utf-8").write("\n".join(L))
