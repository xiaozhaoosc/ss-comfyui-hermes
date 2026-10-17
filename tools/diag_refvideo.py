#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断任务：只跑白模/法线预处理支路，把中间产物落成视频。

回答三个问题：
  1. 白模（#164）和喂给 H3 的 ref_video（#92）是否真的是 124 帧、逐帧变化的图？
     —— #163 EmptyImage 的 batch_size=1 是个已知陷阱：comfy 的 composite 返回 destination，
        批长跟着 destination 走，单帧灰底会把整条支路压成 1 帧。
  2. 时长：驱动视频多少帧 / 生成多少帧，中间有没有被截断。
  3. 分段：图里有没有分段/分块节点（结论：没有，>5s 直接截断）。

用法:
  python tools/diag_refvideo.py --driver peach --ref 8 --tag diag92
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from submit_h3_duozhi_fix import build, submit, DRIVERS, REFS  # noqa: E402

TARGETS = ("92", "164")  # #92=喂 H3 的法线合成图(ref_video)  #164=白模合成图


def upstream(prompt, roots):
    """从 roots 出发沿 [node, slot] 边反查，返回需要保留的节点 id 集合。"""
    keep = set()
    stack = list(roots)
    while stack:
        nid = stack.pop()
        if nid in keep or nid not in prompt:
            continue
        keep.add(nid)
        for v in prompt[nid]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                if v[0] in prompt:
                    stack.append(v[0])
    return keep


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", choices=list(REFS), default="8")
    ap.add_argument("--driver", choices=list(DRIVERS), default="peach")
    ap.add_argument("--tag", default="diag92")
    args = ap.parse_args()

    prompt, nodes, unknown = build()
    prompt["29"]["inputs"]["image"] = REFS[args.ref]
    prompt["117"]["inputs"]["video"] = DRIVERS[args.driver]

    keep = upstream(prompt, TARGETS)
    print("保留节点 %d 个: %s" % (len(keep), sorted(keep, key=int)))

    out = {k: v for k, v in prompt.items() if k in keep}
    for tag, src in (("refvideo", "92"), ("whitemodel", "164")):
        out["9%02d" % len(out)] = {
            "class_type": "VHS_VideoCombine",
            "inputs": {"images": [src, 0], "frame_rate": 24.0, "loop_count": 0,
                       "filename_prefix": "%s_%s" % (args.tag, tag),
                       "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 16,
                       "save_metadata": False, "trim_to_audio": False, "pingpong": False,
                       "save_output": True}}
    print("节点数=%d 未注册=%s" % (len(out), dict(unknown) or "(无)"))
    res = submit(out, nodes, client_id="diag-refvideo")
    if res:
        print(">>> prompt_id=%s number=%s" % (res.get("prompt_id"), res.get("number")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
