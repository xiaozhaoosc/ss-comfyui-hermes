# -*- coding: utf-8 -*-
"""把导出的 API 工作流整理成可读列表（连线解析成节点标题），便于核对结构。"""
import io, os, json, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WF = (sys.argv[1] if len(sys.argv) > 1
      else r"D:\ai_projects\ComfyUI\workflows\v5\h3_guard_v5_full_api.json")
OUT = os.path.join(HERE, "_wfdump_out.txt")

with io.open(WF, "r", encoding="utf-8") as f:
    g = json.load(f)


def label(nid):
    n = g.get(str(nid))
    if not n:
        return "?%s" % nid
    t = (n.get("_meta") or {}).get("title") or n.get("class_type")
    return "%s(#%s)" % (t, nid)


lines = ["workflow: %s" % WF, "nodes = %d" % len(g), ""]
keys = sorted(g.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)

for nid in keys:
    n = g[nid]
    ct = n.get("class_type")
    ti = (n.get("_meta") or {}).get("title", "")
    lines.append("#%s  %s   [%s]" % (nid, ct, ti))
    for k, v in (n.get("inputs") or {}).items():
        is_link = (isinstance(v, list) and len(v) == 2
                   and isinstance(v[0], (str, int)) and isinstance(v[1], int)
                   and not isinstance(v[0], list))
        if is_link:
            lines.append("      %-24s <- %s" % (k, label(v[0])))
        else:
            lines.append("      %-24s = %s" % (k, str(v)[:72]))
    lines.append("")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
