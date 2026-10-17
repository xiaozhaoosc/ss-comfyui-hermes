#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 background_library/manifest.json 组装成 Flow unattended worker 的任务 JSON。

用法:
  venv/Scripts/python.exe tools/build_bg_flow_tasks.py \
      --manifest background_library/manifest.json --split 9,9,2 --out-dir tools/_flow_bg \
      [--only-missing --index background_library/index.json]
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NEG_TAIL = (
    "no people, no animals, no mannequins, no silhouettes, no text, no letters, no signage, "
    "no logos, no watermark, no captions, no UI overlay, "
    "photorealistic photography, 35mm lens, f/4, deep depth of field, natural color grade, "
    "subtle film grain, ultra detailed"
)


def build_prompt(item):
    scene = item["scene"].strip()
    for art in ("a ", "an ", "the "):
        if scene.lower().startswith(art):
            scene = scene[len(art):]
            break
    parts = [
        f"A completely empty {scene}",
        "vertical 9:16 composition with a clear open floor area in the center "
        "for one standing person",
        item["ground"].strip(),
        item["light"].strip(),
        "a soft ambient occlusion gradient on the floor where a person would stand",
        item["extra"].strip(),
        NEG_TAIL,
    ]
    return ", ".join(p for p in parts if p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="background_library/manifest.json")
    ap.add_argument("--split", default="9,9,2")
    ap.add_argument("--out-dir", default="tools/_flow_bg")
    ap.add_argument("--only-missing", action="store_true",
                    help="跳过 index.json 里已有 main.png 的条目")
    ap.add_argument("--index", default="background_library/index.json")
    args = ap.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        items = json.load(f)["items"]

    if args.only_missing and os.path.exists(args.index):
        with open(args.index, "r", encoding="utf-8") as f:
            done = set(e["bg_id"] for e in json.load(f))
        items = [it for it in items if it["bg_id"] not in done]
        print(f"only-missing: 剩余 {len(items)} 条")

    split = [int(x) for x in args.split.split(",")]
    if sum(split) < len(items):
        raise SystemExit(f"split {split} 总容量 {sum(split)} < 条目数 {len(items)}")

    os.makedirs(args.out_dir, exist_ok=True)
    pos = 0
    for seg, size in enumerate(split, 1):
        chunk = items[pos:pos + size]
        pos += size
        if not chunk:
            continue
        tasks = [
            {
                "name": it["flow_task_name"],
                "prompt": build_prompt(it),
                "aspect": "9:16",
                "character": "",
            }
            for it in chunk
        ]
        out = os.path.join(args.out_dir, f"tasks_bg_{seg:02d}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=1)
        print(f"{out}: {len(tasks)} 条 ({chunk[0]['bg_id']} .. {chunk[-1]['bg_id']})")
        for t in tasks:
            print(f"  - {t['name']}: {t['prompt'][:90]}...")


if __name__ == "__main__":
    main()
