# -*- coding: utf-8 -*-
"""打印指定节点的输入规格（判断参数名/类型是否用错）。"""
import io, os, json, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_spec_out.txt")
TARGETS = ["ReActorMaskHelper", "ReActorFaceSwapOpt", "ReActorOptions",
           "ImageCompositeMasked", "GrowMaskWithBlur"]

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
oi = json.loads(op.open("http://127.0.0.1:8188/object_info", timeout=90).read())


def fmt(v):
    if isinstance(v, list) and v:
        t = v[0]
        extra = v[1] if len(v) > 1 and isinstance(v[1], dict) else {}
        d = extra.get("default")
        return "%s default=%r" % (
            t if not isinstance(t, list) else ("COMBO%s" % (t[:6],)), d)
    return str(v)[:100]


L = []
for t in TARGETS:
    n = oi.get(t)
    if not n:
        L.append("[%s] <不存在>" % t)
        L.append("")
        continue
    inp = n.get("input", {})
    L.append("[%s]" % t)
    for k, v in (inp.get("required") or {}).items():
        L.append("   req  %-30s %s" % (k, fmt(v)))
    for k, v in (inp.get("optional") or {}).items():
        L.append("   opt  %-30s %s" % (k, fmt(v)))
    L.append("   outputs = %s" % (n.get("output") or []))
    L.append("")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
