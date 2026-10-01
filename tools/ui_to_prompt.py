"""
UI 工作流 → API prompt 格式 转换器。
通过 /object_info 拿到每个节点的输入定义，按顺序把 widgets_values 映射到 inputs。
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

COMFY_URL = "http://127.0.0.1:8188"


def http_get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_object_info(node_types):
    """获取指定节点类型的定义。"""
    url = f"{COMFY_URL}/object_info"
    all_info = http_get_json(url)
    return {t: all_info[t] for t in node_types if t in all_info}


def classify_inputs(object_info_node):
    """
    返回 (widget_input_names_in_order, link_input_names_in_order)。
    widget 输入：会出现在 widgets_values 里的。
    link 输入：通过连接传入的。
    ComfyUI 前端按以下顺序填充 widgets_values：
      先 required 里的 widget 输入，再 optional 里的 widget 输入。
    link 输入不出现在 widgets_values 里，而是在 inputs 字典里作为 [from_id, from_slot]。
    """
    widget_names = []
    link_names = []
    inp = object_info_node.get("input", {})
    for section in ("required", "optional"):
        section_dict = inp.get(section, {}) or {}
        for name, spec in section_dict.items():
            if not isinstance(spec, list) or len(spec) == 0:
                continue
            type_name = spec[0]
            # 判断是否是 widget 类型：INT/FLOAT/STRING/BOOLEAN/enum(list of str)/dict with options
            # 注意: SAMPLER/SIGMAS/GUIDER/NOISE/VIDEO 是链接类型(纯链接输入), 误判为 widget 会导致值错位
            _LINK_TYPES = (
                "IMAGE", "MASK", "LATENT", "VAE", "CONDITIONING",
                "MODEL", "CLIP", "CLIP_VISION", "CLIP_VISION_OUTPUT",
                "AUDIO", "VHS_BatchManager", "VHS_VIDEOINFO",
                "FACE_MODEL", "FACE_BOOST", "VHS_FILENAMES",
                "CONTROL_NET", "STYLE_MODEL",
                "SAMPLER", "SIGMAS", "GUIDER", "NOISE", "VIDEO",
            )
            is_widget = (
                type_name in ("INT", "FLOAT", "STRING", "BOOLEAN")
                or isinstance(type_name, list)
                or (isinstance(type_name, str) and type_name not in _LINK_TYPES and not name.endswith("_opt"))
            )
            # 简化：如果该输入在 UI 节点的 inputs 数组里出现过（带 link），则是连接输入
            # 这里先按类型粗分，后续再用 UI 节点的 inputs 数组修正
            if type_name in _LINK_TYPES:
                link_names.append(name)
            else:
                widget_names.append(name)
    return widget_names, link_names


def convert_ui_to_prompt(ui):
    """把 UI 格式工作流转成 API prompt 格式。"""
    nodes = ui.get("nodes", [])
    links = ui.get("links", [])

    # 建 link_id → (from_node_id, from_slot) 映射
    # link 格式: [link_id, from_node_id, from_slot, to_node_id, to_slot, type]
    link_map = {}
    for link in links:
        link_id, from_node, from_slot, to_node, to_slot, link_type = link
        link_map[link_id] = (str(from_node), from_slot)

    # 收集所有节点类型
    node_types = list({n["type"] for n in nodes})
    obj_info = get_object_info(node_types)

    prompt = {}
    for node in nodes:
        node_id = str(node["id"])
        node_type = node["type"]
        # Note 节点只是 UI 注释，不参与执行，跳过
        if node_type == "Note":
            continue
        if node_type not in obj_info:
            raise RuntimeError(f"object_info 缺少节点类型: {node_type}")

        widget_names, link_names = classify_inputs(obj_info[node_type])

        # 构建 inputs 字典
        inputs = {}

        # 1. 连接输入：从 UI 节点的 inputs 数组读取
        for ui_input in node.get("inputs", []):
            name = ui_input["name"]
            link_id = ui_input.get("link")
            if link_id is not None and link_id in link_map:
                from_node, from_slot = link_map[link_id]
                inputs[name] = [from_node, from_slot]
            # 如果 link 是 None，连接输入为空，不填（API 格式里可以省略可选输入）

        # 2. Widget 输入：从 widgets_values 读取
        #    注意：如果某 widget 已被转换为连接输入（出现在 inputs 数组且 link 非 null），
        #    它已经在上面被填为 [from_node, from_slot]，这里跳过避免覆盖。
        widgets_values = node.get("widgets_values", [])
        if isinstance(widgets_values, dict):
            # VHS_VideoCombine 等用字典格式，直接按 key 填
            for k, v in widgets_values.items():
                # 跳过 videopreview 这种纯 UI 状态字段
                if k == "videopreview":
                    continue
                # 跳过已被连接占用的 key
                if k in inputs and isinstance(inputs[k], list):
                    continue
                inputs[k] = v
        else:
            # 数组格式：按 widget_names 顺序填
            for i, name in enumerate(widget_names):
                if i < len(widgets_values):
                    # 跳过已被连接占用的 name
                    if name in inputs and isinstance(inputs[name], list):
                        continue
                    inputs[name] = widgets_values[i]

        prompt[node_id] = {
            "class_type": node_type,
            "inputs": inputs,
        }

    return prompt


def main():
    workflow_file = Path(r"d:\ai_projects\ComfyUI\workflows\faceswap_video_reactor_260805_v2_verify.json")
    ui = json.loads(workflow_file.read_text(encoding="utf-8"))

    print("转换 UI → API prompt 格式...")
    prompt = convert_ui_to_prompt(ui)

    # 保存转换结果用于调试
    out_debug = Path(r"d:\ai_projects\ComfyUI\tools\v2_verify_api_prompt.json")
    out_debug.write_text(json.dumps(prompt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"API prompt 已保存到: {out_debug}")

    # 提交到 /prompt
    submission = {"prompt": prompt, "client_id": "v2_verify_agent"}
    print("提交到 ComfyUI /prompt...")
    resp = http_post_json(f"{COMFY_URL}/prompt", submission)
    print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    if "prompt_id" in resp:
        print(f"\nprompt_id = {resp['prompt_id']}")
        print("提交成功，请到 ComfyUI 前端查看执行进度")
    elif "error" in resp:
        print(f"\n提交失败: {resp['error']}")
        if "node_errors" in resp:
            print(f"节点错误: {json.dumps(resp['node_errors'], ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
