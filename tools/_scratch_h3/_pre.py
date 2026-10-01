# -*- coding: utf-8 -*-
"""开跑前的环境自检：语法编译 / ComfyUI 存活 / profile 列表。"""
import io, os, sys, py_compile, json, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "_pre_out.txt")
lines = []

# 1) 语法编译
for f in ["h3_rope_common.py", "run_h3_guard_v5.py"]:
    p = os.path.join(HERE, f)
    try:
        py_compile.compile(p, doraise=True)
        lines.append("compile  OK    %s" % f)
    except Exception as e:
        lines.append("compile  FAIL  %s : %r" % (f, e))

# 2) ComfyUI 存活（用 /queue，不用 /system_stats —— 后者本机返回 500）
try:
    r = urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=6)
    body = r.read()[:300]
    lines.append("server   OK    /queue status=%s body=%s" % (r.status, body))
except Exception as e:
    lines.append("server   FAIL  %r" % (e,))

# 3) profile 列表
sys.path.insert(0, HERE)
try:
    import run_h3_guard_v5 as M
    pf = getattr(M, "PROFILES", None)
    lines.append("profiles : %s" % (list(pf.keys()) if pf else "NO PROFILES ATTR"))
    for k, v in (pf or {}).items():
        lines.append("    %-10s %s" % (k, v.get("desc", "")))
except Exception as e:
    import traceback
    lines.append("import run_h3_guard_v5 FAIL : %r" % (e,))
    lines.append(traceback.format_exc())

# 4) 产物根目录
try:
    import h3_rope_common as H
    lines.append("out_root : %s" % H.out_root())
except Exception as e:
    lines.append("out_root FAIL %r" % (e,))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
