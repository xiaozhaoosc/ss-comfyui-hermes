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
        # COMFY_DYNAMICCOMBO_V3 等动态下拉同样是 widget, 不能被当成端口。
        return body[0] not in WIDGET_TYPE_NAMES and "COMBO" not in body[0]
    return False


def widget_type_name(type_spec):
    """widget 对应的端口类型名 (转成输入时前端用 widget 的类型名, 如 FLOAT/INT/COMBO)。"""
    body = _type_body(type_spec)
    if isinstance(body, list) and len(body) == 1 and isinstance(body[0], str):
        return body[0]
    return "COMBO"


def port_type(type_spec):
    if isinstance(type_spec, str):
        return type_spec
    return _type_body(type_spec)[0]


def is_link_value(v, node_ids):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in node_ids and isinstance(v[1], int)


AUTOGROW = "COMFY_AUTOGROW_V3"


def is_autogrow(type_spec):
    body = _type_body(type_spec)
    return isinstance(body, list) and len(body) == 1 and body[0] == AUTOGROW


def autogrow_prefix(type_spec):
    cfg = type_spec[-1] if isinstance(type_spec[-1], dict) else {}
    return ((cfg.get("template") or {}).get("prefix")) or "item_"


def autogrow_inner_type(type_spec):
    """Autogrow 模板里实例输入端口的类型名（IMAGE / AUDIO ...）。"""
    cfg = type_spec[-1] if isinstance(type_spec[-1], dict) else {}
    inputs = ((cfg.get("template") or {}).get("input") or {})
    for grp in ("required", "optional"):
        for _n, spec in (inputs.get(grp) or {}).items():
            return port_type(spec)
    return "IMAGE"


def _autogrow_sort_key(key, prefix):
    tail = key[len(prefix):] if key.startswith(prefix) else key
    return int(tail) if tail.isdigit() else 0


def autogrow_ports(name, type_spec, val, node_ids, nid, input_ports, links, next_link, parents):
    """Autogrow（COMFY_AUTOGROW_V3）在真实 UI 文件里的形态是**每个实例一个端口**，
    端口名带点号前缀（如 `ref_videos.ref_video_0`）、带 `shape: 7`，首个实例另有 `label`。
    参考仓库内作者发布的真实 UI 工作流
    `workflows/v6/1-Aiden-动作迁移升级版本！法线参考！！.json` 的节点 12。
    API 侧的值是 dict（{ref_video_0: [node, slot]}）或 list（多连接）。"""
    inner = autogrow_inner_type(type_spec)
    prefix = autogrow_prefix(type_spec)
    if isinstance(val, dict):
        keys = sorted(val.keys(), key=lambda k: _autogrow_sort_key(k, prefix))
        items = [val[k] for k in keys]
    elif isinstance(val, list):
        keys = ["%s%d" % (prefix, i) for i in range(len(val))]
        items = list(val)
    else:
        keys, items = [], []
    for i, (key, lv) in enumerate(zip(keys, items)):
        port = {"name": "%s.%s" % (name, key), "shape": 7, "type": inner, "link": None}
        if i == 0:
            port["label"] = key
        if is_link_value(lv, node_ids):
            lid = next_link[0]; next_link[0] += 1
            links.append([lid, int(lv[0]), lv[1], int(nid), len(input_ports), inner])
            port["link"] = lid
            parents.append(lv[0])
        input_ports.append(port)
    if not items:
        # 一个实例都没接时，仍保留一个空槽，前端才会渲染出可连线的端口
        input_ports.append({"name": "%s.%s0" % (name, prefix), "shape": 7, "type": inner, "link": None})


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
            if is_autogrow(type_spec):
                # Autogrow：dict/list -> 每个实例一个点号端口（shape 7）
                autogrow_ports(name, type_spec, val, node_ids, nid,
                               input_ports, links, next_link, parents)
                continue
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
                if is_link_value(val, node_ids) or cfg.get("forceInput"):
                    # 前端把该 widget 转成了输入端口 (forceInput, 或被连线)。
                    t = widget_type_name(type_spec)
                    if is_link_value(val, node_ids):
                        # 依据真实 UI 文件: inputs 里带 "widget":{"name":...}, 且 widgets_values
                        # 仍保留该 widget 的值 (原顺序), 用默认值占位。
                        lid = next_link[0]; next_link[0] += 1
                        links.append([lid, int(val[0]), val[1], int(nid), len(input_ports), t])
                        input_ports.append({"name": name, "type": t, "widget": {"name": name}, "link": lid})
                        parents.append(val[0])
                        widgets_values.append(cfg.get("default"))
                    else:
                        # 纯 forceInput: 本就没有 widget, 不占 widgets_values。
                        input_ports.append({"name": name, "type": t, "link": None})
                else:
                    widgets_values.append(val if val is not None else cfg.get("default"))
                    # 前端会给 seed/noise_seed widget 自动附加 control_after_generate 下拉
                    if cfg.get("control_after_generate") or name in ("seed", "noise_seed"):
                        widgets_values.append("fixed")
                    if cfg.get("image_upload"):
                        widgets_values.append("image")

        # VHS 系列节点的前端 widget 序列与 /object_info 的 optional 列表**不一致**，
        # 必须按前端实际约定重排，否则位置错位会把值塞到错误的 widget 上。
        if cls == "VHS_VideoCombine":
            # 前端 serialize() 产出的是**字典**（不是数组），键名如下；
            # 依据：仓库内真实可用的 UI 工作流 user/default/workflows/faceswap_video_reactor.json
            widgets_values = {
                "frame_rate": api_inputs.get("frame_rate", 8),
                "loop_count": api_inputs.get("loop_count", 0),
                "filename_prefix": api_inputs.get("filename_prefix", "ComfyUI"),
                "format": api_inputs.get("format", "video/h264-mp4"),
                "pix_fmt": api_inputs.get("pix_fmt", "yuv420p"),
                "crf": api_inputs.get("crf", 19),
                "save_metadata": api_inputs.get("save_metadata", True),
                "pingpong": api_inputs.get("pingpong", False),
                "save_output": api_inputs.get("save_output", True),
            }
        elif cls in ("VHS_LoadVideo", "VHS_LoadVideoPath"):
            # 前端 widget 序列固定 8 项：
            # [video, force_rate, custom_width, custom_height, frame_load_cap,
            #  skip_first_frames, select_every_nth, force_size]
            # /object_info 里的 meta_batch / vae / format 前端**不渲染**，必须丢弃；
            # 末尾 force_size 前端默认 "Disabled"（同样是上面那份真实 UI 文件里的取值）。
            widgets_values = [
                api_inputs.get("video", ""),
                api_inputs.get("force_rate", 0),
                api_inputs.get("custom_width", 0),
                api_inputs.get("custom_height", 0),
                api_inputs.get("frame_load_cap", 0),
                api_inputs.get("skip_first_frames", 0),
                api_inputs.get("select_every_nth", 1),
                "Disabled",
            ]

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
            "size": [340, h],
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
