# -*- coding: utf-8 -*-
"""Z-Image 皮肤纹理补偿 —— A/B 对照实验（提交后不等待，进度用手工查）。

四组对照（同一组场景提示词、同一 seed 基线，只改「纹理补偿手段」）：
  zimg_base     基线，无补偿
  zimg_skinlora 皮肤纹理 LoRA（skin_texture_zturbo_v45，strength 0.7）
  zimg_realism  写实 LoRA（zimage_realism_lora，strength 0.8）
  zimg_boost    纯提示词强化（append 皮肤纹理触发词，无 LoRA）

默认 **只提交不等待**（--no-wait 语义），台账落 _submit_log.json；
进度用 `python tools/_pc_status.py` 手工查询，或加 --wait 才阻塞等待。

用法：
  python tools/_pc_lora_ab.py                    # 提交全部 4 组 × 8 场景
  python tools/_pc_lora_ab.py --scenes s01_x,s02_y
  python tools/_pc_lora_ab.py --groups zimg_base,zimg_skinlora
  python tools/_pc_lora_ab.py --dry              # 只校验图
  python tools/_pc_lora_ab.py --wait             # 提交并阻塞等待（默认关闭）
"""
import os, sys, json, io, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pc_common import submit, wait, collect_outputs, save_meta, today_root, \
    server_alive, comfy_prefix, BASE
import _pc_prompts as P
import _pc_gen_zimage as Z
import importlib
importlib.reload(P)

SUB = "lora_ab"

# 作者建议的触发词（Skin Texture ZTurbo v4.5 / Realism LoRA）
BOOST = (", incredibly lifelike, cinematic, detailed, sharp, fine texture, "
         "hyperrealistic, photorealistic, visible skin pores, natural skin detail")

GROUPS = [
    # (组名, LoRA 文件 或 None, strength, 是否加提示词强化)
    ("zimg_base", None, None, False),
    ("zimg_skinlora", "skin_texture_zturbo_v45.safetensors", 0.7, False),
    ("zimg_realism", "zimage_realism_lora.safetensors", 0.8, False),
    ("zimg_boost", None, None, True),
]

LORA_DIR = os.path.join(BASE, "models", "loras")


def main():
    only, groups_sel = None, None
    dry, do_wait, strength_override = False, False, None
    outdir_root = today_root(SUB)

    a = sys.argv
    for i, tok in enumerate(a):
        nxt = a[i + 1] if i + 1 < len(a) else None
        if tok == "--scenes" and nxt:
            only = set(x.strip() for x in nxt.split(",") if x.strip())
        elif tok == "--groups" and nxt:
            groups_sel = set(x.strip() for x in nxt.split(",") if x.strip())
        elif tok == "--strength" and nxt:
            strength_override = float(nxt)
        elif tok == "--outdir" and nxt:
            outdir_root = nxt
        elif tok == "--dry":
            dry = True
        elif tok == "--wait":
            do_wait = True

    if not dry and not server_alive():
        print("!! ComfyUI 未响应，先启动 main.py --lowvram ...")
        return

    os.makedirs(outdir_root, exist_ok=True)
    ledger_path = os.path.join(outdir_root, "_submit_log.json")
    ledger = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "no_wait": not do_wait,
              "jobs": []}

    print("=== Z-Image 皮肤纹理补偿 A/B | 输出 %s ===" % outdir_root, flush=True)
    print("模式: %s" % ("提交并等待" if do_wait else "只提交（用 _pc_status.py 查进度）"),
          flush=True)

    missing_lora = []
    for gname, lora, strength, boost in GROUPS:
        if groups_sel and gname not in groups_sel:
            continue
        if lora and not os.path.exists(os.path.join(LORA_DIR, lora)):
            missing_lora.append("%s -> %s" % (gname, lora))

    if missing_lora:
        print("")
        print("!! 以下 LoRA 尚未下载完成，请先跑：")
        print("   python tools/_dl_weights.py --set lora_skin")
        for m in missing_lora:
            print("   - %s" % m)

    for gname, lora, strength, boost in GROUPS:
        if groups_sel and gname not in groups_sel:
            continue
        if lora and not os.path.exists(os.path.join(LORA_DIR, lora)):
            print("[skip] %s（LoRA 缺失）" % gname, flush=True)
            continue

        st = strength_override if strength_override is not None else strength
        gdir = os.path.join(outdir_root, gname)
        os.makedirs(gdir, exist_ok=True)
        print("")
        print("--- 组 %s | lora=%s strength=%s boost=%s ---" % (gname, lora, st, boost),
              flush=True)

        for i, sc in enumerate(P.SCENES):
            if only and sc["id"] not in only:
                continue
            seed = 900000 + i          # 与基线同 seed，保证可比
            pos = P.zimage_positive(sc)
            if boost:
                pos = pos + BOOST
            prefix = comfy_prefix(gdir, "pc_%s_%s" % (gname, sc["id"]))
            graph = Z.build(pos, P.ZIMAGE_NEG, 1024, 1024, Z.DEF_STEPS, Z.DEF_CFG,
                            seed, prefix, Z.DEF_SAMPLER, Z.DEF_SCHED, lora, st or 0.8)

            if dry:
                print("[dry] %s / %s seed=%d nodes=%d" % (gname, sc["id"], seed, len(graph)),
                      flush=True)
                continue

            ok, pid = submit(graph)
            print("[submit] %-14s %-24s seed=%d -> %s %s" % (
                gname, sc["id"], seed, ok, str(pid)[:60]), flush=True)
            rec = {"group": gname, "scene": sc["id"], "seed": seed, "lora": lora,
                   "strength": st, "boost": boost, "prompt_id": pid if ok else None,
                   "prefix": prefix, "ok_submit": ok,
                   "submitted_at": time.strftime("%H:%M:%S")}
            if not ok:
                rec["err"] = str(pid)[:400]
            ledger["jobs"].append(rec)

            if ok and do_wait:
                done, hist = wait(pid, timeout=1800)
                files = collect_outputs(hist) if done else []
                rec["ok"] = bool(files)
                rec["files"] = files

    save_meta(ledger_path, ledger)
    print("")
    print("=== 已登记 %d 个任务 -> %s ===" % (len(ledger["jobs"]), ledger_path))
    if not do_wait:
        print("查进度：python tools/_pc_status.py")
        print("出图完成后重新评测：python tools/eval_pc_models.py   （模型列表需含这些组）")


if __name__ == "__main__":
    main()
