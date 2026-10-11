# avatar_wf1~wf5 工作流结构验证: 引用完整性 + 连通性 + 输出节点
# 用法: python tools/validate_avatar_workflows.py
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    "avatar_wf1_head_swap.json",
    "avatar_wf2_face_swap.json",
    "avatar_wf3_cloth_swap.json",
    "avatar_wf4_motion_transfer.json",
    "avatar_wf5_full_pipeline.json",
    "avatar_wf5_short.json",
    "avatar_wf5_short_v2.json",
]
OUTPUT_NODES = {"SaveImage", "SaveVideo", "VHS_VideoCombine", "SaveAnimatedWEBP", "SaveAudio"}


def is_link(v):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)


def main():
    ok = True
    for name in FILES:
        path = os.path.join(BASE, "workflows", name)
        wf = json.load(open(path, encoding="utf-8"))
        p = wf["prompt"]
        ids = set(p.keys())
        errs = []

        for nid, node in p.items():
            if not isinstance(node, dict) or "class_type" not in node:
                continue
            for k, v in node.get("inputs", {}).items():
                if is_link(v) and v[0] not in ids:
                    errs.append(f"节点{nid} 输入{k} 引用不存在的节点 {v[0]}")

        referenced = set()
        for node in p.values():
            if not isinstance(node, dict):
                continue
            for v in node.get("inputs", {}).values():
                if is_link(v):
                    referenced.add(v[0])
        for nid, node in p.items():
            if not isinstance(node, dict) or "class_type" not in node:
                continue
            if nid not in referenced and node["class_type"] not in OUTPUT_NODES:
                errs.append(f"孤儿节点 {nid} ({node['class_type']})")

        if not any(isinstance(n, dict) and n.get("class_type") in OUTPUT_NODES for n in p.values()):
            errs.append("无输出节点")

        if errs:
            ok = False
            print(f"[FAIL] {name}")
            for e in errs:
                print(f"   - {e}")
        else:
            outs = sum(1 for n in p.values() if isinstance(n, dict) and n.get("class_type") in OUTPUT_NODES)
            print(f"[OK] {name}: {len(p)} 节点, {outs} 输出")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
