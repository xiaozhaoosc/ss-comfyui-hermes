# -*- coding: utf-8 -*-
"""Generate the prompt set with Qwen-Image 2.1 (GGUF Q4_K_M).

Qwen-Image 2.1 topology (b本机件已齐，2026-10-10 探测确认):
  UnetLoaderGGUF(qwen-image-2.1-UC-Q4_K_M.gguf)          -> MODEL（GGUF 不走 UNETLoader）
  CLIPLoader(qwen3vl_8b_int8_convrot, type=qwen_image)   -> CLIP
      注：TE 是 Qwen3-VL-8B，sd.py:1768-1774 会在 QWEN3_8B + CLIPType.QWEN_IMAGE 时
      路由到 comfy.text_encoders.qwen_image21
  VAELoader(qwen_image_2.1_vae_bf16)                     -> VAE
  ModelSamplingAuraFlow(shift=3.0)                       -> 采样调度
  KSampler(steps=25, cfg=3.0, euler/simple) -> VAEDecode -> SaveImage

⚠️ 与 Z-Image 不同：Qwen-Image 是**非蒸馏**模型，cfg>1 → **负面提示词有效**，
   所以着装约束可以同时用正向锚点和负向词兜住。

Usage:
  python tools/_pc_gen_qwen21.py [--scenes s01_x] [--steps 25] [--cfg 3.0]
                                 [--wh 1024x1024] [--seed 800000] [--outdir <dir>]
                                 [--lora <name>] [--dry] [--no-wait]
"""
import os, sys, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pc_common import (submit, wait, collect_outputs, save_meta, today_root,
                        server_alive, comfy_prefix)
import _pc_prompts as P
import importlib
importlib.reload(P)

UNET = "qwen-image-2.1-UC-Q4_K_M.gguf"
TE = "qwen3vl_8b_int8_convrot.safetensors"
TE_TYPE = "qwen_image"
VAE = "qwen_image_2.1_vae_bf16.safetensors"
MODEL = "qwen_image_21"
OUT_SUB = MODEL

DEF_STEPS = 25
DEF_CFG = 3.0
DEF_SHIFT = 3.0
DEF_SAMPLER = "euler"
DEF_SCHED = "simple"
DEF_W = DEF_H = 1024
DEF_SEED_BASE = 800000

QWEN_NEG = ("lowres, bad anatomy, bad hands, extra limbs, deformed, watermark, "
            "text, jpeg artifacts, blurry, plastic skin, waxy skin")


def build(pos, neg, w, h, steps, cfg, seed, prefix, shift=DEF_SHIFT,
          sampler=DEF_SAMPLER, sched=DEF_SCHED, lora=None, lora_strength=0.8):
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": UNET}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": TE, "type": TE_TYPE}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["2", 0]}},
        "6": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "10": {"class_type": "ModelSamplingAuraFlow",
               "inputs": {"shift": shift, "model": ["1", 0]}},
        "7": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": sampler, "scheduler": sched, "denoise": 1.0,
                         "model": ["10", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }
    if lora:
        g["20"] = {"class_type": "LoraLoader",
                   "inputs": {"lora_name": lora, "strength_model": lora_strength,
                              "strength_clip": lora_strength,
                              "model": ["10", 0], "clip": ["2", 0]}}
        g["7"]["inputs"]["model"] = ["20", 0]
        g["4"]["inputs"]["clip"] = ["20", 1]
        g["5"]["inputs"]["clip"] = ["20", 1]
    return g


def main():
    only, steps, cfg, shift = None, DEF_STEPS, DEF_CFG, DEF_SHIFT
    w = h = DEF_W
    seed_base = DEF_SEED_BASE
    outdir = lora = None
    dry = no_wait = False
    sampler, sched = DEF_SAMPLER, DEF_SCHED

    a = sys.argv
    for i, tok in enumerate(a):
        nxt = a[i + 1] if i + 1 < len(a) else None
        if tok == "--scenes" and nxt:
            only = set(x.strip() for x in nxt.split(",") if x.strip())
        elif tok == "--steps" and nxt:
            steps = int(nxt)
        elif tok == "--cfg" and nxt:
            cfg = float(nxt)
        elif tok == "--shift" and nxt:
            shift = float(nxt)
        elif tok == "--size" and nxt:
            w = h = int(nxt)
        elif tok == "--wh" and nxt:
            w, h = [int(x) for x in nxt.split("x")]
        elif tok == "--seed" and nxt:
            seed_base = int(nxt)
        elif tok == "--outdir" and nxt:
            outdir = nxt
        elif tok == "--lora" and nxt:
            lora = nxt
        elif tok == "--sampler" and nxt:
            sampler = nxt
        elif tok == "--scheduler" and nxt:
            sched = nxt
        elif tok == "--dry":
            dry = True
        elif tok == "--no-wait":
            no_wait = True

    outdir = outdir or today_root(OUT_SUB)
    os.makedirs(outdir, exist_ok=True)

    if not server_alive():
        print("!! ComfyUI 未响应，先启动 main.py --lowvram ...")
        return

    print("=== Qwen-Image 2.1 | %dx%d | steps=%d cfg=%s shift=%s | out=%s ===" % (
        w, h, steps, cfg, shift, outdir), flush=True)

    results = []
    t_all = time.time()
    for i, sc in enumerate(P.SCENES):
        if only and sc["id"] not in only:
            continue
        seed = seed_base + i
        prefix = comfy_prefix(outdir, "pc_%s_%s" % (MODEL, sc["id"]))
        graph = build(P.zimage_positive(sc), QWEN_NEG, w, h, steps, cfg, seed,
                      prefix, shift, sampler, sched, lora)

        if dry:
            print("[dry] %s seed=%d nodes=%d" % (sc["id"], seed, len(graph)), flush=True)
            results.append({"scene": sc["id"], "ok": None, "seed": seed, "dry": True})
            continue

        ok, pid = submit(graph)
        print("[submit] %s seed=%s -> %s %s" % (sc["id"], seed, ok, pid), flush=True)
        if not ok:
            results.append({"scene": sc["id"], "ok": False, "err": str(pid)[:800]})
            continue

        if no_wait:
            # 只提交，不阻塞；进度请用 tools/_pc_status.py 手工查询
            results.append({"scene": sc["id"], "ok": None, "pending": True,
                            "prompt_id": pid, "seed": seed,
                            "prefix": prefix, "backend": "qwen_image_21"})
            continue

        t0 = time.time()
        done, hist = wait(pid, timeout=3600)
        dt = round(time.time() - t0, 1)
        files = collect_outputs(hist) if done else []
        st = (hist or {}).get("status", {}) if done else {}
        err = "" if files else json.dumps(st, ensure_ascii=False)[:400]
        print("   [done] %s in %ss files=%s %s" % (
            done, dt, [f["filename"] for f in files], err), flush=True)
        results.append({"scene": sc["id"], "ok": bool(files), "prompt_id": pid,
                        "seconds": dt, "seed": seed, "files": files,
                        "backend": MODEL, "unet": UNET, "te": TE, "steps": steps,
                        "cfg": cfg, "shift": shift, "size": [w, h], "lora": lora,
                        "note": sc["note"], "prompt_en": sc["flux"]})

    total = round(time.time() - t_all, 1)
    if not dry:
        meta_path = os.path.join(outdir, "_run.json")
        prev = []
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    prev = json.load(f).get("results", [])
            except Exception:
                prev = []
        merged = {r["scene"]: r for r in prev if r.get("scene")}
        for r in results:
            merged[r["scene"]] = r
        ordered = [merged[s["id"]] for s in P.SCENES if s["id"] in merged]
        save_meta(meta_path, {"backend": MODEL, "unet": UNET, "te": TE, "steps": steps,
                              "cfg": cfg, "shift": shift, "size": [w, h], "lora": lora,
                              "total_seconds": total, "no_wait": no_wait,
                              "results": ordered})
        n_ok = sum(1 for r in ordered if r.get("ok"))
        print("\n=== qwen_image_21 : %d/%d ok, total %ss ===" % (n_ok, len(ordered), total))
        print("meta: %s" % meta_path)


if __name__ == "__main__":
    main()
