# -*- coding: utf-8 -*-
"""把 ComfyUI UI(graph) 工作流转成可直接 POST /prompt 的 API 格式。

用法：
    python tools/uiwf_to_api.py "workflows/v6/xxx.json" [-o out.json]

要点：
- 依赖本机 ComfyUI(127.0.0.1:8188) 的 /object_info 做节点定义校验与 widget 回退推断，
  结果缓存在 tools/.cache/object_info/。
- mode=2(mute)/4(bypass) 的节点跳过，bypass 节点的连线自动穿透到上游。
- Note / MarkdownNote / Reroute / PrimitiveNode 不进 API。
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "http://127.0.0.1:8188"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "object_info")
VIRTUAL = {"Note", "MarkdownNote", "Reroute", "PrimitiveNode"}
CONTROL_AFTER = {"randomize", "fixed", "increment", "decrement"}

# 本机设了 HTTP_PROXY，直连 127.0.0.1:8188 会被劫持成 502，必须绕代理
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def object_info(class_type):
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, class_type.replace("/", "_") + ".json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    url = "%s/object_info/%s" % (HOST, urllib.parse.quote(class_type, safe=""))
    try:
        r = _OPENER.open(url, timeout=30)
        body = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("  [warn] object_info 拉取失败 %s: %s" % (class_type, e))
        return None
    data = body.get(class_type)
    if not data:
        return None
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


# object_info 里只有这些类型会渲染成 widget，其余（IMAGE/VAE/MODEL/自定义 socket）是连线输入
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "SEED"}


def input_type(spec, key):
    for grp in ("required", "optional"):
        v = (spec["input"].get(grp) or {}).get(key)
        if v is not None:
            return v[0] if isinstance(v, (list, tuple)) else v
    return None


def spec_keys(spec):
    keys = []
    for grp in ("required", "optional"):
        keys.extend((spec["input"].get(grp) or {}).keys())
    return keys


def raw_options(spec, key):
    for grp in ("required", "optional"):
        v = (spec["input"].get(grp) or {}).get(key)
        if v is None or not isinstance(v, (list, tuple)):
            continue
        if len(v) > 1 and isinstance(v[1], dict) and v[1].get("options"):
            return v[1]["options"]
        if isinstance(v[0], list):
            return v[0]
    return None


def combo_options(spec, key):
    opts = raw_options(spec, key)
    if opts and isinstance(opts[0], dict):
        return None  # DynamicCombo 的选项带子输入，只校验主选择键
    return opts


def accepts_key(spec, key):
    """Autogrow / DynamicCombo 的子输入写作 values.a、selection.tau，按前缀认。"""
    keys = spec_keys(spec)
    return key in keys or key.split(".")[0] in keys


def widget_names(spec):
    """按 object_info 顺序给出会生成 widget 的输入名。"""
    out = []
    for grp in ("required", "optional"):
        for k, v in (spec["input"].get(grp) or {}).items():
            t = v[0] if isinstance(v, (list, tuple)) else v
            if isinstance(t, list) or t in WIDGET_TYPES:
                out.append(k)
    return out


def map_widgets(spec, values):
    """把 widgets_values 还原成 {输入名: 值}。

    ⚠️ VHS 之类节点存的是 dict（自带键名）；其余是数组，要按 object_info 顺序回推，
    且 seed 后面跟的 control_after_generate 是虚拟 widget，要吃掉。
    """
    if isinstance(values, dict):
        return {k: v for k, v in values.items() if not str(k).endswith("control_after_generate")}
    names = widget_names(spec)
    out = {}
    vals = list(values or [])
    for name in names:
        if not vals:
            break
        v = vals.pop(0)
        out[name] = v
        if name.endswith("seed") and vals and vals[0] in CONTROL_AFTER:
            vals.pop(0)
    return out


FILE_EXTS = (".safetensors", ".gguf", ".pth", ".pt", ".bin", ".onnx", ".ckpt",
             ".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp")


def build_index():
    """models/ 与 input/ 下文件名 -> [(根目录类别, 相对路径)]，用于校正下拉里存的模型名。"""
    idx = {}
    for root in ("models", "input"):
        base = os.path.join(BASE, root)
        if not os.path.isdir(base):
            continue
        for dp, _, fns in os.walk(base):
            for fn in fns:
                if not fn.lower().endswith(FILE_EXTS):
                    continue
                rel = os.path.relpath(os.path.join(dp, fn), base).replace("\\", "/")
                kind = rel.split("/", 1)[0] if root == "models" else "input"
                idx.setdefault(fn.lower(), []).append((kind, rel))
    return idx


def fix_files(api, idx, alts):
    """UI 存的引用名可能带过期子目录前缀，按磁盘实际情况校正。"""
    notes = []
    for nid, entry in sorted(api.items(), key=lambda kv: int(kv[0])):
        for key, val in entry["inputs"].items():
            if not isinstance(val, str) or not val.lower().endswith(FILE_EXTS):
                continue
            alt = alts.get((nid, key))
            if alt and val != alt:
                notes.append("ALT  #%s %s.%s: %s -> %s（取 UI 当前值）" % (nid, entry["class_type"], key, val, alt))
                entry["inputs"][key] = val = alt
            name = os.path.basename(val.replace("\\", "/")).lower()
            cands = idx.get(name)
            if not cands:
                near = [k for k in idx if os.path.splitext(k)[0][:12] == os.path.splitext(name)[0][:12]]
                notes.append("MISS #%s %s.%s = %s（盘上没有；近似：%s）"
                             % (nid, entry["class_type"], key, val, ", ".join(idx[k][0][1] for k in near[:3]) or "无"))
                continue
            want = val.replace("\\", "/").split("/")[0] if "/" in val.replace("\\", "/") else None
            pick = next((c for c in cands if want and c[1].startswith(want + "/")), cands[0])
            new = pick[1].split("/", 1)[1] if pick[0] != "input" and "/" in pick[1] else pick[1]
            if new != val:
                entry["inputs"][key] = new
                notes.append("FIX  #%s %s.%s: %s -> %s" % (nid, entry["class_type"], key, val, new))
    return notes


class Graph:
    def __init__(self, wf):
        self.nodes = {n["id"]: n for n in wf["nodes"]}
        # links 可能是数组 [id, origin_id, origin_slot, target_id, target_slot, type]
        self.links = {}
        for l in wf.get("links", []):
            if isinstance(l, dict):
                self.links[l["id"]] = l
            else:
                self.links[l[0]] = {"id": l[0], "origin_id": l[1], "origin_slot": l[2]}

    def resolve(self, link_id):
        """顺着 Reroute / bypass 节点回溯到真实上游，返回 [node_id, slot]。"""
        seen = set()
        lid = link_id
        while lid is not None and lid not in seen:
            seen.add(lid)
            link = self.links.get(lid)
            if not link:
                return None
            up = self.nodes.get(link["origin_id"])
            if not up:
                return None
            if up["type"] in VIRTUAL or up.get("mode") == 4:
                ins = up.get("inputs") or []
                if not ins:
                    return None
                lid = ins[0].get("link", ins[0].get("linkId"))
                continue
            return [str(link["origin_id"]), int(link["origin_slot"])]
        return None


def type_ok(src_type, dst_type):
    if dst_type == "*" or src_type == "*":
        return True
    return src_type in str(dst_type).split(",")


def check_types(api, specs):
    """逐条连线核对上游输出类型与下游输入类型，抓 slot 错位。"""
    problems = []
    for nid, entry in api.items():
        refs = dict(entry["inputs"])
        for ag in [v for v in refs.values() if isinstance(v, dict)]:
            refs.update(ag)
        for key, val in refs.items():
            if not (isinstance(val, list) and len(val) == 2 and isinstance(val[0], str)):
                continue
            src_id, slot = val[0], val[1]
            src = specs.get(api[src_id]["class_type"]) if src_id in api else None
            if not src:
                continue
            outs = src.get("output") or []
            if slot >= len(outs):
                problems.append("node %s: 引用 #%s 的第 %d 个输出，但只有 %d 个" % (nid, src_id, slot, len(outs)))
                continue
            dst = specs.get(entry["class_type"])
            if not dst:
                continue
            dst_type = input_type(dst, key)
            if dst_type is None or isinstance(dst_type, list):
                continue
            if not type_ok(outs[slot], dst_type):
                problems.append("node %s(%s).%s 需要 %s，但 #%s 输出 %s"
                                % (nid, entry["class_type"], key, dst_type, src_id, outs[slot]))
    return problems


def combo_check(api):
    """下拉值必须落在服务端给出的选项里，否则 /prompt 会直接拒。"""
    problems = []
    for nid, entry in api.items():
        spec = object_info(entry["class_type"])
        if not spec:
            continue
        for k, v in entry["inputs"].items():
            if not isinstance(v, str):
                continue
            opts = combo_options(spec, k)
            if opts and v not in opts:
                problems.append("node %s(%s).%s = %r 不在下拉列表（可选：%s）"
                                % (nid, entry["class_type"], k, v, ", ".join(map(str, opts[:6]))))
    return problems


def convert(wf):
    g = Graph(wf)
    api = {}
    problems = []
    specs = {}
    alts = {}
    for node in wf["nodes"]:
        nid, ctype = node["id"], node["type"]
        if node.get("mode") in (2, 4) or ctype in VIRTUAL:
            continue
        spec = object_info(ctype)
        if spec is None:
            problems.append("node %s: 找不到节点类型 %s（自定义节点未启用？）" % (nid, ctype))
        else:
            specs[ctype] = spec
        keys = spec_keys(spec) if spec else []

        inputs = {}
        # widgets_values 是 UI 上的当前值，named 只是快照，文件类引用失效时用它兜底
        fallback = map_widgets(spec, node.get("widgets_values")) if spec else {}
        alts.update({(str(nid), k): v for k, v in fallback.items()})
        named = node.get("widgets_values_named")
        if named:
            for k, v in named.items():
                if keys and not (k in keys or k.split(".")[0] in keys):
                    continue  # control_after_generate 之类虚拟 widget
                inputs[k] = v
        elif spec is not None:
            inputs.update(fallback)
        else:
            problems.append("node %s: 无 widgets_values_named 且拿不到 %s 定义" % (nid, ctype))

        for inp in node.get("inputs") or []:
            lid = inp.get("link", inp.get("linkId"))
            if lid is None:
                continue
            ref = g.resolve(lid)
            if ref is None:
                problems.append("node %s(%s): 输入 %s 的连线断了" % (nid, ctype, inp.get("name")))
                continue
            name = inp.get("name")
            if keys and name not in keys and not accepts_key(spec, name):
                problems.append("node %s(%s): 输入名 %s 不在节点定义里" % (nid, ctype, name))
            inputs[name] = ref

        if spec:
            for k in (spec["input"].get("required") or {}):
                if k in inputs:
                    continue
                if "AUTOGROW" not in str(input_type(spec, k)):
                    problems.append("node %s(%s): 必填输入 %s 未赋值" % (nid, ctype, k))
                elif not any(i.startswith(k + ".") for i in inputs):
                    problems.append("node %s(%s): autogrow 输入 %s.* 一个都没填" % (nid, ctype, k))

        entry = {"inputs": inputs, "class_type": ctype}
        if node.get("title"):
            entry["_meta"] = {"title": node["title"]}
        api[str(nid)] = entry

    # autogrow 里的连线也要纳入类型检查
    flat = {}
    for nid, entry in api.items():
        flat[nid] = entry
    problems.extend(check_types(flat, specs))
    return api, problems, specs, alts


def summarize(api, wf):
    titles = {str(n["id"]): n.get("title") or n["type"] for n in wf["nodes"]}
    print("\n== 可调入口（调用时通常要改的） ==")
    for nid, entry in sorted(api.items(), key=lambda kv: int(kv[0])):
        ct = entry["class_type"]
        if ct in ("LoadImage", "LoadVideo", "VHS_LoadVideo", "VHS_LoadImages",
                  "SaveImage", "VHS_VideoCombine", "PreviewImage"):
            vals = {k: v for k, v in entry["inputs"].items() if not isinstance(v, list)}
            print("  #%s %s %s" % (nid, titles.get(nid, ct), json.dumps(vals, ensure_ascii=False)[:160]))
    print("\n== seed 节点 ==")
    for nid, entry in sorted(api.items(), key=lambda kv: int(kv[0])):
        for k in ("seed", "noise_seed"):
            if k in entry["inputs"]:
                print("  #%s %s.%s = %s" % (nid, entry["class_type"], k, entry["inputs"][k]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--no-cache", action="store_true", help="忽略 object_info 本地缓存")
    ap.add_argument("--no-file-check", action="store_true", help="不做模型/素材文件校正")
    ap.add_argument("--map", action="append", default=[],
                    help="手工替换引用值，格式 旧值=新值（可多次，用于模型改名）")
    args = ap.parse_args()

    if args.no_cache and os.path.isdir(CACHE):
        for f in os.listdir(CACHE):
            os.remove(os.path.join(CACHE, f))

    with open(args.src, encoding="utf-8") as f:
        wf = json.load(f)
    if "nodes" not in wf:
        sys.exit("不是 UI 格式工作流（缺 nodes）")

    api, problems, _, alts = convert(wf)
    for pair in args.map:
        old, _, new = pair.partition("=")
        for nid, entry in api.items():
            for key, val in entry["inputs"].items():
                if val == old:
                    entry["inputs"][key] = new
                    problems.append("MAP  #%s %s.%s -> %s（手工映射）" % (nid, entry["class_type"], key, new))
    notes = [] if args.no_file_check else fix_files(api, build_index(), alts)
    problems.extend(combo_check(api))
    problems.sort(key=lambda s: 0 if s.startswith("MAP") else 1)
    out = args.out or (os.path.splitext(args.src)[0] + "_api.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(api, f, ensure_ascii=False, indent=2)

    src_nodes = len(wf["nodes"])
    print("节点 %d -> API %d（跳过 %d）" % (src_nodes, len(api), src_nodes - len(api)))
    print("输出:", out)
    if problems:
        print("\n== 问题 %d 条 ==" % len(problems))
        for p in problems:
            print("  !", p)
    else:
        print("结构校验：全部节点类型已注册、必填输入齐全、连线类型匹配")
    if notes:
        print("\n== 文件引用 %d 条 ==" % len(notes))
        for n in notes:
            print("  ", n)
    summarize(api, wf)


if __name__ == "__main__":
    main()
