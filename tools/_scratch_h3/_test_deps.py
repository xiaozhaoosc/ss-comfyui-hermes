# -*- coding: utf-8 -*-
"""决定性依赖测试：triton / sageattention 到底能不能 import（与 ComfyUI 同解释器）。"""
import io, os, site, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_test_deps_out.txt")
L = []

L.append("python = %s" % sys.executable)
L.append("")

for mod in ["triton", "triton.language", "sageattention"]:
    try:
        m = __import__(mod)
        L.append("OK    import %-18s -> %s" % (
            mod, getattr(m, "__version__", "?")))
    except Exception as e:
        L.append("FAIL  import %-18s -> %s: %s" % (mod, type(e).__name__, e))

L.append("")

# 打印 ComfyUI 自己那套依赖里的 triton
try:
    import triton
    L.append("triton.__file__ = %s" % triton.__file__)
except Exception:
    pass

# site-packages 里是否存在 triton 目录
sp_list = []
try:
    sp_list += list(site.getsitepackages())
except Exception:
    pass
try:
    sp_list.append(site.getusersitepackages())
except Exception:
    pass
sp_list.append(os.path.dirname(os.__file__) + r"\site-packages")

for sp in sorted(set(sp_list)):
    for name in ("triton", "sageattention"):
        p = os.path.join(sp, name)
        if os.path.isdir(p):
            L.append("dir exists: %s" % p)

# 顺带看看 ComfyUI requirements 里的痕迹
try:
    import importlib.metadata as md
    for pkg in ("triton", "sageattention", "torch"):
        try:
            L.append("pkg %-14s version=%s" % (pkg, md.version(pkg)))
        except Exception as e:
            L.append("pkg %-14s not installed (%s)" % (pkg, type(e).__name__))
except Exception as e:
    L.append("metadata FAIL %r" % (e,))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
