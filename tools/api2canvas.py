# -*- coding: utf-8 -*-
# 将 API prompt 格式的 workflow JSON 转为 ComfyUI 画布 (litegraph) 格式。
# 画布格式需要 nodes/links/pos 布局信息, API prompt 格式只有节点字典, 拖入画布为空。
# 用法: python tools/api2canvas.py <input_api.json> [-o output_canvas.json]
import argparse
import json
import sys
import urllib.request

HOST = "http://127.0.0.1:8188"


def fetch_object_info():
    with urllib.request.urlopen(HOST + "/object_info", timeout=30) as r:
        return json.load(r)


WIDGET_TYPE_NAMES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}


def _type_body(type_spec):
    """去掉尾部配置 dict 后的类型定义体。"""
    if isinstance(type_spec, list) and type_spec and isinstance(type_spec[-1], dict):
        return type_spec[:-1]
    return type_spec


def is_port_type(type_spec):
    """连接端口: "IMAGE"、["IMAGE"] 或 ["IMAGE", {"tooltip":...}]；类型名非 widget 基础类型即为端口。"""
    if isinstance(type_spec, str):
        return True
    body = _type_body(type_spec)
    if isinstance(body, list) and len(body) == 1 and isinstance(body[0], str) and body[0].isupper():
        return body[0] not in WIDGET_TYPE_NAMES
    return False


def port_type(type_spec):
    if isinstance(type_spec, str):
        return type_spec
    return _type_body(type_spec)[0]


def is_link_value(v, node_ids):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in node_ids and isinstance(v[1], int)


def class_inputs(obj_def):
    """required + optional 的 (name, spec) 有序列表, hidden 跳过。"""
    inp = obj_def.get("input", {})
    items = list(inp.get("required", {}).items()) + list(inp.get("optional", {}).items())
    return items


def build_canvas(prompt, object_info):
    node_ids = set(prompt.keys())
    links = []          # [link_id, from_node, from_slot, to_node, to_slot, TYPE]
    next_link = [1]
    nodes = []
    node_meta = {}      # node_id -> {"outputs": [...], "parents": [...]}

    for nid, spec in prompt.items():
        cls = spec["class_type"]
        if cls not in object_info:
            print(f"[WARN] 节点 {nid} 的类 {cls} 不在 /object_info 中, 跳过 (自定义节点未加载?)")
            continue
        obj_def = object_info[cls]
        api_inputs = spec.get("inputs", {})
        input_ports = []
        widgets_values = []
        parents = []

        for name, type_spec in class_inputs(obj_def):
            val = api_inputs.get(name)
            if is_port_type(type_spec):
                t = port_type(type_spec)
                # 连接端口
                if is_link_value(val, node_ids):
                    lid = next_link[0]; next_link[0] += 1
                    links.append([lid, int(val[0]), val[1], int(nid), len(input_ports), t])
                    input_ports.append({"name": name, "type": t, "link": lid})
                    parents.append(val[0])
                elif isinstance(val, list) and val and all(is_link_value(x, node_ids) for x in val):
                    # Autogrow 多连接: 每个元素一个同名端口
                    for x in val:
                        lid = next_link[0]; next_link[0] += 1
                        links.append([lid, int(x[0]), x[1], int(nid), len(input_ports), t])
                        input_ports.append({"name": name, "type": t, "link": lid})
                        parents.append(x[0])
                else:
                    input_ports.append({"name": name, "type": t, "link": None})
            else:
                # widget (类型为列表: COMBO / ["INT",{}] / ["STRING",{}] 等)
                cfg = type_spec[-1] if isinstance(type_spec[-1], dict) else {}
                widgets_values.append(val if val is not None else cfg.get("default"))
                # 前端会给 seed/noise_seed widget 自动附加 control_after_generate 下拉
                if cfg.get("control_after_generate") or name in ("seed", "noise_seed"):
                    widgets_values.append("fixed")
                if cfg.get("image_upload"):
                    widgets_values.append("image")

        if cls == "VHS_VideoCombine" and "format" in api_inputs:
            # VHS 前端期望 [frame_rate, loop_count, filename_prefix, format, {extra参数dict}, save_output]
            extra = {k: v for k, v in api_inputs.items()
                     if k not in ("images", "frame_rate", "loop_count", "filename_prefix", "format", "save_output")}
            widgets_values = [api_inputs.get("frame_rate"), api_inputs.get("loop_count"),
                              api_inputs.get("filename_prefix"), api_inputs.get("format"),
                              extra, api_inputs.get("save_output")]

        out_types = obj_def.get("output", [])
        out_names = obj_def.get("output_name") or [t if not isinstance(t, list) else str(t) for t in out_types]
        outputs = [{"name": out_names[i], "type": out_types[i], "links": [], "slot_index": i}
                   for i in range(len(out_types))]
        node_meta[nid] = {"outputs": outputs, "parents": parents, "cls": cls,
                          "input_ports": input_ports, "widgets_values": widgets_values}

    # 回填 outputs[].links
    for l in links:
        meta = node_meta.get(str(l[1]))
        if meta and l[2] < len(meta["outputs"]):
            meta["outputs"][l[2]]["links"].append(l[0])

    # 拓扑分层布局
    depth = {}
    def get_depth(nid):
        if nid in depth:
            return depth[nid]
        ps = node_meta[nid]["parents"]
        depth[nid] = 0 if not ps else max(get_depth(p) for p in ps) + 1
        return depth[nid]

    valid = list(node_meta.keys())
    for nid in valid:
        get_depth(nid)
    order = sorted(valid, key=lambda n: (depth[n], int(n)))
    col_count = {}
    for nid in order:
        col = depth[nid]
        row = col_count.get(col, 0)
        col_count[col] = row + 1
        meta = node_meta[nid]
        h = 80 + len(meta["widgets_values"]) * 28 + len(meta["input_ports"]) * 22
        nodes.append({
            "id": int(nid),
            "type": meta["cls"],
            "pos": [60 + col * 400, 60 + row * 280],
            "size": {"0": 340, "1": h},
            "flags": {},
            "order": len(nodes),
            "mode": 0,
            "inputs": meta["input_ports"],
            "outputs": meta["outputs"],
            "properties": {"Node name for S&R": meta["cls"]},
            "widgets_values": meta["widgets_values"],
        })

    return {
        "last_node_id": max(int(n) for n in valid),
        "last_link_id": next_link[0] - 1,
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompt = data["prompt"] if "prompt" in data else data

    object_info = fetch_object_info()
    canvas = build_canvas(prompt, object_info)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(canvas, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(canvas['nodes'])} nodes, {len(canvas['links'])} links -> {args.output}")


if __name__ == "__main__":
    sys.exit(main())
