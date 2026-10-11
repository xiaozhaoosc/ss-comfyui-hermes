# -*- coding: utf-8 -*-
"""把 api2canvas 产出的画布 JSON 后处理成可直接在 ComfyUI 打开的 UI 工作流：
   1) size 对象 -> 数组
   2) 修正被误判为端口的 widget（SaveVideo.codec 是动态下拉 widget）
   3) [inject:xxx] 占位符 -> 可用默认值（按同字段原始值做类型转换）
   4) 追加 Note 说明节点
   5) 结构校验（节点类型 / 端口 / 连线 / 端口类型 / widget 数量）
配套：tools/api2canvas.py（API prompt 格式 -> 画布格式）。
用法：
  python tools/api2canvas.py <api.json> -o <canvas.json>
  python tools/ui_workflow_postprocess.py <canvas.json> <api.json> <out_ui.json> "<note文本>" '<values JSON>'
"""
import json
import os
import sys
import urllib.request

HOST = "http://127.0.0.1:8188"

# 各类型的 widget 期望数量（依据当前前端刚保存的 workflows/工作流/低显存版工作流/06_fl2v_*.json
# 校准；object_info 会多报隐藏 widget，如 H3SLAAttention 报 14 而前端只存 6）
EXPECT_WIDGETS = {
    "UNETLoader": 2, "CLIPLoader": 3, "VAELoader": 1,
    "MiniMaxChunkFeedForward": 2, "H3SLAAttention": 6, "MiniMaxH3SigmaShift": 2,
    "LoadImage": 1, "LoadVideo": 1, "MiniMaxH3ImageToVideo": 4,
    "RandomNoise": 2, "BasicScheduler": 3, "KSamplerSelect": 1,
    "BasicGuider": 0, "SamplerCustomAdvanced": 0, "VAEDecode": 0, "VAEDecodeAudio": 0,
    "CreateVideo": 3, "SaveVideo": 3, "GetVideoComponents": 0,
    "RIFEInterpolation": 6, "UpscaleModelLoader": 1, "ImageUpscaleWithModel": 0,
    "ImageScale": 4, "Note": 1,
}
# 前端实际渲染的 widget 数少于 object_info 时截断（按 object_info 顺序取前 N 个）
WIDGET_KEEP = {"H3SLAAttention": 6}
# 前端存在、但 object_info 未声明的尾部 widget
WIDGET_EXTRA = {"CreateVideo": ["sRGB"]}

BASE_WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COMFY_DYNAMICCOMBO_V3"}


def widget_specs(cls, object_info):
    """按 object_info 顺序返回 [(name, 类型, 配置)]，含被前端隐藏的 widget。"""
    inp = object_info[cls].get("input", {})
    items = list(inp.get("required", {}).items()) + list(inp.get("optional", {}).items())
    specs = []
    for name, t in items:
        cfg = t[-1] if isinstance(t, list) and t and isinstance(t[-1], dict) else {}
        head = t[:-1] if cfg else t
        if isinstance(head, list):
            if head and isinstance(head[0], str) and head[0].isupper():
                if head[0] not in BASE_WIDGET_TYPES:
                    continue          # 真端口
                type_name = head[0]
            else:
                type_name = "COMBO"   # 选项列表
        else:
            continue                  # 纯字符串类型名 = 端口
        specs.append((name, type_name, cfg))
    return specs


def coerce_by_type(value, type_name):
    if isinstance(value, bool):
        return value
    if type_name == "INT":
        return int(round(float(value)))
    if type_name == "FLOAT":
        return float(value)
    if type_name == "BOOLEAN":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    return str(value) if not isinstance(value, str) else value


def load_api_values(api_path):
    """API 里出现过的字面量值：{node_id: {input_name: value}}，跳过连线。"""
    api = json.load(open(api_path, encoding="utf-8"))
    out = {}
    ids = set(api.keys())
    for nid, spec in api.items():
        row = {}
        for k, v in spec.get("inputs", {}).items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in ids:
                continue
            row[k] = v
        out[nid] = row
    return out


def main():
    ui_path, api_path, out_path, note_text, values_json = sys.argv[1:6]
    # 第 5 个参数可以是内联 JSON，也可以是一个 JSON 文件路径（便于传入长提示词）
    if os.path.isfile(values_json):
        values = json.load(open(values_json, encoding="utf-8-sig"))
    else:
        values = json.loads(values_json)

    ui = json.load(open(ui_path, encoding="utf-8"))
    api_vals = load_api_values(api_path)
    object_info = json.load(urllib.request.urlopen(HOST + "/object_info", timeout=30))
    errors, warnings = [], []

    for n in ui["nodes"]:
        nid = str(n["id"])
        cls = n["type"]
        # 1) size: {"0":w,"1":h} -> [w,h]
        if isinstance(n.get("size"), dict):
            n["size"] = [n["size"].get("0"), n["size"].get("1")]

        # 2) SaveVideo.codec 被误判为端口 -> 收回为 widget
        if cls == "SaveVideo":
            ports = n.get("inputs", [])
            for p in list(ports):
                if p["name"] == "codec":
                    ports.remove(p)
            n["inputs"] = ports
            if api_vals.get(nid, {}).get("codec") is not None:
                n["widgets_values"] = list(n.get("widgets_values") or []) + [api_vals[nid]["codec"]]

        # 3) 重建 widgets_values：按 object_info 顺序取「API 字面量 or 节点默认值」，
        #    占位符 [inject:xxx] 换成可用默认值；顺带补 seed 的 "fixed" 与前端额外 widget
        if cls == "Note":
            continue
        raw = api_vals.get(nid, {})
        specs = widget_specs(cls, object_info)
        keep = WIDGET_KEEP.get(cls)
        if keep:
            specs = specs[:keep]
        built = []
        for wname, wtype, wcfg in specs:
            val = raw.get(wname, wcfg.get("default"))
            if isinstance(val, str) and val.startswith("[inject:") and val.endswith("]"):
                key = val[len("[inject:"):-1]
                if key in values:
                    val = coerce_by_type(values[key], wtype)
                else:
                    warnings.append(f"节点{nid}({cls}) 占位符 {val} 无默认值，改用节点默认")
                    val = wcfg.get("default")
            elif val is not None:
                val = coerce_by_type(val, wtype)
            built.append(val)
            if wcfg.get("control_after_generate") or wname in ("seed", "noise_seed"):
                built.append("fixed")
        built.extend(WIDGET_EXTRA.get(cls, []))
        n["widgets_values"] = built

    # 4) 追加 Note 说明节点
    new_id = max(n["id"] for n in ui["nodes"]) + 1
    ui["nodes"].append({
        "id": new_id, "type": "Note", "pos": [60, 60], "size": [440, 240],
        "flags": {}, "order": len(ui["nodes"]), "mode": 0,
        "inputs": [], "outputs": [],
        "title": "说明：本 UI 版对应的 API 文件",
        "properties": {}, "widgets_values": [note_text],
    })
    ui["last_node_id"] = new_id

    # 5) 校验
    ids = {n["id"] for n in ui["nodes"]}
    by_id = {n["id"]: n for n in ui["nodes"]}
    link_ids = {l[0]: l for l in ui["links"]}

    for l in ui["links"]:
        lid, src, sslot, dst, dslot, ltype = l
        if src not in ids:
            errors.append(f"link {lid}: 源节点 {src} 不存在")
        if dst not in ids:
            errors.append(f"link {lid}: 目标节点 {dst} 不存在")
        s, d = by_id.get(src), by_id.get(dst)
        if s:
            outs = s.get("outputs") or []
            if sslot >= len(outs):
                errors.append(f"link {lid}: 源 {src} 无输出槽 {sslot}")
            else:
                if lid not in outs[sslot].get("links", []):
                    errors.append(f"link {lid}: 源 {src} 输出槽 {sslot} 未登记该连线")
                otype = outs[sslot].get("type")
                if d and dslot < len(d.get("inputs") or []):
                    itype = d["inputs"][dslot].get("type")
                    if otype and itype and otype != itype:
                        errors.append(f"link {lid}: 类型不匹配 {otype} -> {itype}")
        if d:
            ins = d.get("inputs") or []
            if dslot >= len(ins):
                errors.append(f"link {lid}: 目标 {dst} 无输入槽 {dslot}")
            elif ins[dslot].get("link") != lid:
                errors.append(f"link {lid}: 目标 {dst} 输入槽 {dslot} 的 link 值不符")

    for n in ui["nodes"]:
        cls = n["type"]
        if cls != "Note" and cls not in object_info:
            errors.append(f"节点{n['id']}: 类型 {cls} 不在 /object_info")
        exp = EXPECT_WIDGETS.get(cls)
        got = len(n.get("widgets_values") or [])
        if exp is not None and got != exp:
            warnings.append(f"节点{n['id']}({cls}): widgets {got} != 期望 {exp}")
        for p in n.get("inputs") or []:
            if p.get("link") is not None and p["link"] not in link_ids:
                errors.append(f"节点{n['id']}({cls}) 端口 {p['name']} 的 link {p['link']} 不存在")

    json.dump(ui, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[写出] {out_path}  节点={len(ui['nodes'])} 连线={len(ui['links'])}")
    print(f"[校验] 错误 {len(errors)} 条")
    for e in errors:
        print("   ERR " + e)
    print(f"[校验] 警告 {len(warnings)} 条")
    for w in warnings:
        print("   WARN " + w)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())