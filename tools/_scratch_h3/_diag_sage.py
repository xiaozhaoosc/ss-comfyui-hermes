# -*- coding: utf-8 -*-
"""诊断：KJNodes 的 sage attention patch 失败原因 + 环境/节点可用性。"""
import io, os, re, json, importlib.util, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_diag_sage_out.txt")
LOG = r"D:\ai_projects\ComfyUI\output\2026-09-22_wb\h3_guard\_run_full.log"
L = []


def dec(raw):
    for enc in ("utf-8", "gbk", "utf-16", "utf-16-le"):
        try:
            t = raw.decode(enc)
        except Exception:
            continue
        if t.count("\x00") > len(t) * 0.1:
            continue
        return t
    return raw.decode("utf-8", "replace")


# 1) 完整日志 + 提取异常字段
L.append("======== 完整 _run_full.log ========")
if os.path.exists(LOG):
    with open(LOG, "rb") as f:
        raw = f.read()
    t = dec(raw).replace("\x00", "")
    L.append(t)
    L.append("\n======== 抽取的异常字段 ========")
    for m in re.finditer(r'"exception_message"\s*:\s*"((?:[^"\\]|\\.)*)"', t):
        L.append(">>> exception_message: %s" % m.group(1)[:800])
    for m in re.finditer(r'"exception_type"\s*:\s*"((?:[^"\\]|\\.)*)"', t):
        L.append(">>> exception_type: %s" % m.group(1)[:200])
else:
    L.append("(no log)")

# 2) 关键依赖是否装了
L.append("\n======== 依赖检查 ========")
for mod in ["sageattention", "triton", "flash_attn", "xformers"]:
    try:
        spec = importlib.util.find_spec(mod)
        L.append("  %-14s %s" % (mod, "FOUND" if spec else "NOT INSTALLED"))
    except Exception as e:
        L.append("  %-14s spec FAIL %r" % (mod, e))

# 3) 与 Sage/Attention 相关的节点
L.append("\n======== object_info 中含 sage/attention 的节点 ========")
try:
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    r = op.open("http://127.0.0.1:8188/object_info", timeout=90)
    oi = json.loads(r.read())
    keys = sorted(k for k in oi
                  if ("sage" in k.lower() or "attention" in k.lower()))
    for k in keys:
        L.append("  %s" % k)
    L.append("")
    for target in ["PatchSageAttentionKJ", "PathchSageAttentionKJ",
                   "MiniMaxH3MemoryEfficientSageAttentionPatch",
                   "H3SLAAttention"]:
        if target in oi:
            inp = oi[target].get("input", {})
            L.append("  [%s]" % target)
            L.append("     required = %s" % json.dumps(inp.get("required"),
                                                       ensure_ascii=False)[:600])
            L.append("     optional = %s" % json.dumps(inp.get("optional"),
                                                       ensure_ascii=False)[:600])
        else:
            L.append("  [%s] <不存在>" % target)
except Exception as e:
    L.append("object_info FAIL %r" % (e,))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L) + "\n")
