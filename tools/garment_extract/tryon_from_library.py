# -*- coding: utf-8 -*-
"""从服装库取服装，注入 faceswap_tryon_combo_v1（ReActor 换脸 + IDM-VTON 换装）并提交 ComfyUI。

用法：
  # 查库
  <venv python> tools/garment_extract/tryon_from_library.py --list [tops|bottoms|full]

  # 提交换装（只提交不轮询，结果按 prompt_id 自行查询）
  <venv python> tools/garment_extract/tryon_from_library.py \
      --garment full_20261012_01 --person input/todo/tryon_cache/person.jpg \
      [--face input/todo/face/ken4.png] [--desc "black knit dress"] [--seed 42]

服装用库内 white.png（白底 RGB，IDM-VTON 参考图标准输入）；换装优先级见 garment_library/README.md。
"""
import argparse
import json
import os
import shutil
import sys
import urllib.request

ROOT = r"D:\ai_projects\ComfyUI"
LIB_INDEX = os.path.join(ROOT, "garment_library", "index.json")
WORKFLOW = os.path.join(ROOT, "workflows", "done", "faceswap_tryon_combo_v1.json")
STAGING = os.path.join(ROOT, "input", "tryon_library")  # ComfyUI input/ 下的相对路径从这里引用
COMFY_URL = "http://127.0.0.1:8188"


def http_post_json(url, payload):
    # 本机 8188 必须绕代理，否则 HTTP_PROXY 劫持成 502
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=30) as r:
        return json.loads(r.read())


def load_entries():
    with open(LIB_INDEX, encoding="utf-8") as f:
        return json.load(f)


def resolve_garment(gid, entries):
    for e in entries:
        if e["garment_id"] == gid:
            return e
    ids = ", ".join(e["garment_id"] for e in entries)
    raise SystemExit(f"garment_id 不在库中: {gid}（可选：{ids}）")


def stage(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return os.path.relpath(dst, os.path.join(ROOT, "input")).replace("\\", "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", nargs="?", const="all", default=None, metavar="CATEGORY")
    ap.add_argument("--garment", help="garment_id，如 full_20261012_01")
    ap.add_argument("--person", help="被换装的人物图路径")
    ap.add_argument("--face", help="换脸身份图（缺省用工作流里的默认脸）")
    ap.add_argument("--desc", help="服装描述（缺省用库内 note）")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    entries = load_entries()
    if args.list:
        for e in entries:
            if args.list == "all" or e["category"] == args.list:
                print(f"{e['garment_id']:22s} {e['category']:8s} {e['mean_hex']} "
                      f"{e['size'][0]}x{e['size'][1]} {e.get('note', '')[:50]}")
        return

    if not (args.garment and args.person):
        raise SystemExit("提交换装需要 --garment <id> --person <图>（--list 查库）")

    g = resolve_garment(args.garment, entries)
    garment_src = os.path.join(ROOT, "garment_library", g["dir"].replace("\\", "/"), "white.png")
    if not os.path.exists(garment_src):
        raise SystemExit(f"缺文件: {garment_src}")

    with open(WORKFLOW, encoding="utf-8") as f:
        wf = json.load(f)

    wf["1"]["inputs"]["image"] = stage(args.person, os.path.join(STAGING, "person" + os.path.splitext(args.person)[1]))
    if args.face:
        wf["2"]["inputs"]["image"] = stage(args.face, os.path.join(STAGING, "face" + os.path.splitext(args.face)[1]))
    wf["3"]["inputs"]["image"] = stage(garment_src, os.path.join(STAGING, f"{args.garment}_garment.png"))
    wf["9"]["inputs"]["garment_description"] = args.desc or g.get("note") or f"a {g['category']} garment"
    wf["9"]["inputs"]["seed"] = args.seed
    wf["10"]["inputs"]["filename_prefix"] = f"tryon_library/{args.garment}"

    out = http_post_json(f"{COMFY_URL}/prompt", {"prompt": wf, "client_id": "tryon_from_library"})
    print(f"已提交: prompt_id={out['prompt_id']}")
    print(f"服装: {args.garment} ({g['mean_hex']} {g['size'][0]}x{g['size'][1]})")
    print("结果目录: output/tryon_library/（只提交不轮询，完成后自行查询）")


if __name__ == "__main__":
    main()
