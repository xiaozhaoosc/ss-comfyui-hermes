# -*- coding: utf-8 -*-
import json, os
BASE = r"D:\BaiduNetdiskDownload\北宋杨家将"
J = os.path.join(BASE, r".workbuddy\_tmp\qc\shots.json")
OUT = os.path.join(BASE, r".workbuddy\_tmp\qc\pilot_shots.txt")
d = json.load(open(J, "r", encoding="utf-8"))
L = []
for ep in (1, 6):
    rs = [r for r in d["rows"] if r["ep"] == ep]
    L.append("=" * 100)
    L.append("第 %d 集《%s》  共 %d 镜  总 %d 秒" % (ep, rs[0]["epname"], len(rs), sum(r["dur"] for r in rs)))
    L.append("=" * 100)
    cur = ""
    for r in rs:
        if r["scene"] != cur:
            cur = r["scene"]
            L.append("")
            L.append("── 场 %s" % cur)
        flag = ("  ★需改运镜→" + r["vfix"]) if r["vfix"] else ""
        L.append("  [%02d] p%-7s %ds  %s%s" % (r["idx"], r["mark"] or "—", r["dur"], r["txt"], flag))
open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("ok")
