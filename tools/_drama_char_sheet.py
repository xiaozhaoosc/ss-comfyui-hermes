# -*- coding: utf-8 -*-
"""角色资产表批次生成：读 char_ref.json -> 锁定 seed -> 逐视图提交 txt2img -> 合成 turnaround 表。

依赖（同目录 tools/ 下）：
  _pc_common  : submit / wait / collect_outputs / save_meta / comfy_prefix / BASE / server_alive
                （已内置绕代理 _OPENER，本地 HTTP 自动避开 127.0.0.1:8188 的代理劫持）
  _pc_gen_sd15: build()（传锁定 seed 即可复用 SD1.5 出图图）
  _pc_prompts : SD_NEG / SD_QUALITY
  _pc_sheet   : build_sheet()（图片路径列表 -> 网格资产表 PNG）

用法:
  python tools/_drama_char_sheet.py char_ref.json --date 2026-10-10 --proj mydrama
  python tools/_drama_char_sheet.py char_ref.json --model Counterfeit-V3.0_fp16.safetensors

char_ref.json 结构（与 AI_DRAMA_RUNBOOK.md 一致）:
  {"name":"角色A","seed":12345,"model":"Counterfeit-V3.0_fp16.safetensors",
   "lora":null,"traits":{"hair":"","clothes":"","prop":""},"sheet_path":"01_assets/char_A_sheet.png"}

⚠️ 负责任提醒：动漫角色生成请确保角色设定为「成年」，避免 minor-coded（幼态化）内容；
SD_NEG 已含 nsfw 负向词，人物题材务必再加显式负面提示词兜底。

产物：output/<date>/<proj>/01_assets/char_<name>/ 下：
  sheet_<name>_front.png / _side.png / _back.png / _face.png / _height.png
  <name>_sheet.png  （合成 turnaround 表）
  _run.json         （每视图 prompt_id / seed / files / ok）
"""
import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _pc_common as C
from _pc_gen_sd15 import build, CONFIG
import _pc_prompts as P
from _pc_sheet import build_sheet

# 五个视图（同一角色共用一个锁定 seed，保证外观一致）
VIEWS = [
    ("front",  "full body, front view, standing, feet visible, character sheet, reference sheet"),
    ("side",   "full body, side view, profile, standing, character sheet, reference sheet"),
    ("back",   "full body, back view, standing, character sheet, reference sheet"),
    ("face",   "head and shoulders close-up portrait, face detail, character sheet"),
    ("height", "full body, front view, standing straight, height chart, flat solid color background, character sheet"),
]

# SD1.5 全局默认档位（CONFIG 无对应 model 时回退）
DEF_STEPS, DEF_CFG, DEF_SAMPLER, DEF_SCHED = 28, 8.0, "dpmpp_2m", "karras"
DEF_W, DEF_H = 512, 768


def traits_to_prompt(traits, view, gender="female"):
    """把 traits 拼成 SD1.5 标签串（按 gender 选 1girl/1boy/solo + hair/clothes/prop）。"""
    g = (gender or "female").strip().lower()
    if g in ("male", "boy", "m", "男"):
        parts = ["1boy", "solo"]
    elif g in ("female", "girl", "f", "女"):
        parts = ["1girl", "solo"]
    else:
        parts = ["solo"]
    for k in ("hair", "clothes", "prop"):
        v = (traits or {}).get(k, "")
        if v:
            parts.append(v.strip())
    return ", ".join([p for p in parts if p])


def existing_view_png(outdir, name, vid):
    """Return the latest good (>=20KB) PNG for a view from a prior run, else None.

    用于断点续跑：重跑时只生成缺失/失败的视图，已成功的直接复用
    （seed 锁定，重跑结果完全一致，无需浪费 GPU）。
    """
    prefix = "sheet_%s_%s_" % (name, vid)
    best, bestsz = None, 0
    if os.path.isdir(outdir):
        for f in os.listdir(outdir):
            if f.startswith(prefix) and f.endswith(".png"):
                sz = os.path.getsize(os.path.join(outdir, f))
                if sz > 20000 and sz > bestsz:
                    best, bestsz = f, sz
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("char_json", help="角色 JSON 路径（char_ref.json 结构）")
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"),
                   help="产物日期目录 YYYY-MM-DD（默认今天）")
    ap.add_argument("--proj", default="default", help="项目名（默认 default）")
    ap.add_argument("--model", default=None, help="覆盖 JSON 的 model（ckpt 文件名）")
    a = ap.parse_args()

    with open(a.char_json, encoding="utf-8") as f:
        char = json.load(f)
    name = char["name"]
    seed = int(char["seed"])
    model = a.model or char.get("model") or "Counterfeit-V3.0_fp16.safetensors"
    lora = char.get("lora")
    traits = char.get("traits", {})
    gender = char.get("gender", "female")
    proj = a.proj or "default"

    # 档位：优先 CONFIG[model]，否则全局默认
    if model in CONFIG:
        steps, cfg, sampler, sched, w, h, _sbase, _lcfg = CONFIG[model]
    else:
        steps, cfg, sampler, sched, w, h = DEF_STEPS, DEF_CFG, DEF_SAMPLER, DEF_SCHED, DEF_W, DEF_H

    outdir = os.path.join(C.BASE, "output", a.date, proj, "01_assets", "char_" + name)
    os.makedirs(outdir, exist_ok=True)

    alive = C.server_alive()
    if not alive:
        print("[WARN] ComfyUI 未运行（127.0.0.1:8188）。请先启动：")
        print("        python main.py --lowvram --listen 0.0.0.0 --port 8188")
        print("        本脚本仍会写出 _run.json（ok=false），服务起后可重跑补齐。")

    results = []
    paths = []
    labels = []

    # 断点续跑：已有成功 PNG 的视图直接复用，只生成缺失/失败的
    existing = {}
    for vid, _ in VIEWS:
        p = existing_view_png(outdir, name, vid)
        if p:
            existing[vid] = p

    for vid, viewtag in VIEWS:
        pos = P.SD_QUALITY + ", " + traits_to_prompt(traits, vid, gender) + ", " + viewtag
        prefix = C.comfy_prefix(outdir, "sheet_%s_%s" % (name, vid))
        graph = build(model, pos, P.SD_NEG, w, h, steps, cfg, sampler, sched,
                      seed, prefix, lora=lora)
        rec = {"view": vid, "seed": seed, "model": model, "prompt": pos, "ok": False}
        if vid in existing:
            rec["ok"] = True
            rec["reused"] = True
            rec["files"] = [existing[vid]]
            paths.append(os.path.join(outdir, existing[vid]))
            labels.append(vid)
            print("  [REUSE] %-6s -> %s" % (vid, existing[vid]))
            results.append(rec)
            continue
        if alive:
            ok, pid = C.submit(graph)
            rec["prompt_id"] = pid if ok else None
            if ok:
                done, hist = C.wait(pid, timeout=int(os.environ.get("DRAM_WAIT_TIMEOUT", "900")))
                files = C.collect_outputs(hist) if done else []
                if files:
                    rec["files"] = [fl.get("filename") for fl in files]
                    rec["ok"] = True
                    paths.append(os.path.join(outdir, files[0]["filename"]))
                    labels.append(vid)
                    print("  [OK]   %-6s -> %s" % (vid, files[0]["filename"]))
                else:
                    print("  [FAIL] %s 无产物" % vid)
            else:
                print("  [FAIL] %s submit: %s" % (vid, str(pid)[:120]))
        else:
            print("  [SKIP] %s (server down)" % vid)
        results.append(rec)

    # 合成 turnaround 表（5 视图 -> 1 张网格 PNG，默认 3 列：上排 3 + 下排 2）
    sheet_name = os.path.join(outdir, "%s_sheet.png" % name)
    if paths:
        build_sheet(paths, labels, sheet_name,
                    "%s — character sheet (seed %d)" % (name, seed), cols=3, th=512)
    else:
        print("[skip] 无成功图片，跳过合成表")

    C.save_meta(os.path.join(outdir, "_run.json"),
                {"name": name, "seed": seed, "model": model, "lora": lora,
                 "outdir": outdir, "results": results})
    print("DONE %s -> %s" % (name, outdir))


if __name__ == "__main__":
    main()
