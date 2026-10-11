# -*- coding: utf-8 -*-
"""Generate the prompt set with Z-Image Turbo (bf16) — **默认后端**.

Z-Image topology (verified on this machine 2026-10-10):
  UNETLoader(z_image_turbo_bf16, weight_dtype=default) -> MODEL
  CLIPLoader(qwen_3_4b, type=qwen_image)              -> CLIP
      ⚠️ 下拉列表里没有 z_image 这个 type，但 comfy/sd.py:1758-1764 会在 TE 被识别为
         QWEN3_4B 且 clip_type != FLUX/FLUX2 时自动路由到 comfy.text_encoders.z_image，
         所以传 qwen_image 即可。别被下拉列表误导成"版本不支持"。
  VAELoader(ae) -> VAE
  EmptySD3LatentImage -> KSampler(**steps=8, cfg=1.0**, euler/simple) -> VAEDecode -> SaveImage

cfg=1.0 意味着**负面提示词不生效** —— 着装约束必须由正向 ZIMAGE_ANCHOR 承担。
不需要 ModelSamplingAuraFlow。实测 1024×1024 / 8 步 ≈ 0.9 分钟（含首次加载）。

Usage:
  python tools/_pc_gen_zimage.py [--scenes s01,s02] [--steps 8] [--wh 1024x1024]
                                 [--seed 900000] [--outdir <dir>] [--dry]
"""
import os, sys, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pc_common import (submit, wait, collect_outputs, save_meta, today_root,
                        server_alive, comfy_prefix)
import _pc_prompts as P
import importlib
importlib.reload(P)

UNET = "z_image_turbo_bf16.safetensors"
TE = "qwen_3_4b.safetensors"
VAE = "ae.safetensors"
TE_TYPE = "qwen_image"          # 见文件头说明：这是 Z-Image TE 的正确入口
MODEL = "z_image_turbo"         # 对比表 / 文件名里用的模型标识
OUT_SUB = MODEL

DEF_STEPS = 8
DEF_CFG = 1.0
DEF_SAMPLER = "euler"
DEF_SCHED = "simple"
DEF_W = DEF_H = 1024
DEF_SEED_BASE = 900000


def build(pos, neg, w, h, steps, cfg, seed, prefix,
          sampler=DEF_SAMPLER, sched=DEF_SCHED, lora=None, lora_strength=0.8):
    g = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": TE, "type": TE_TYPE}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["2", 0]}},
        "6": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "7": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": sampler, "scheduler": sched,
                         "denoise": 1.0, "model": ["1", 0],
                         "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }
    if lora:
        g["20"] = {"class_type": "LoraLoader",
                   "inputs": {"lora_name": lora, "strength_model": lora_strength,
                              "strength_clip": lora_strength,
                              "model": ["1", 0], "clip": ["2", 0]}}
        g["7"]["inputs"]["model"] = ["20", 0]
        g["4"]["inputs"]["clip"] = ["20", 1]
        g["5"]["inputs"]["clip"] = ["20", 1]
    return g


def main():
    only = None
    steps = DEF_STEPS
    cfg = DEF_CFG
    w = h = DEF_W
    seed_base = DEF_SEED_BASE
    outdir = None
    lora = None
    dry = False
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

    outdir = outdir or today_root(OUT_SUB)
    os.makedirs(outdir, exist_ok=True)

    if not server_alive():
        print("!! ComfyUI 未响应 http://127.0.0.1:8188 —— 先启动：")
        print("   python main.py --lowvram --listen 0.0.0.0 --port 8188")
        return

    print("=== Z-Image Turbo | %dx%d | steps=%d cfg=%s %s/%s | out=%s ===" % (
        w, h, steps, cfg, sampler, sched, outdir), flush=True)

    results = []
    t_all = time.time()
    for i, sc in enumerate(P.SCENES):
        if only and sc["id"] not in only:
            continue
        seed = seed_base + i
        prefix = comfy_prefix(outdir, "pc_%s_%s" % (MODEL, sc["id"]))
        graph = build(P.zimage_positive(sc), P.ZIMAGE_NEG, w, h, steps, cfg,
                      seed, prefix, sampler, sched, lora)

        if dry:
            print("[dry] %s seed=%d nodes=%d" % (sc["id"], seed, len(graph)), flush=True)
            results.append({"scene": sc["id"], "ok": None, "seed": seed, "dry": True})
            continue

        ok, pid = submit(graph)
        print("[submit] %s seed=%s -> %s %s" % (sc["id"], seed, ok, pid), flush=True)
        if not ok:
            results.append({"scene": sc["id"], "ok": False, "err": str(pid)[:800]})
            continue

        t0 = time.time()
        done, hist = wait(pid, timeout=1800)
        dt = round(time.time() - t0, 1)
        files = collect_outputs(hist) if done else []
        st = (hist or {}).get("status", {}) if done else {}
        err = "" if files else json.dumps(st, ensure_ascii=False)[:400]
        print("   [done] %s in %ss files=%s %s" % (
            done, dt, [f["filename"] for f in files], err), flush=True)
        results.append({"scene": sc["id"], "ok": bool(files), "prompt_id": pid,
                        "seconds": dt, "seed": seed, "files": files,
                        "backend": "zimage", "unet": UNET, "te": TE, "te_type": TE_TYPE,
                        "steps": steps, "cfg": cfg, "sampler": sampler,
                        "scheduler": sched, "size": [w, h], "lora": lora,
                        "note": sc["note"], "prompt_en": sc["flux"],
                        "status": st})

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
        save_meta(meta_path, {"backend": "zimage", "unet": UNET, "te": TE,
                              "steps": steps, "cfg": cfg, "size": [w, h],
                              "total_seconds": total, "results": ordered})
        n_ok = sum(1 for r in ordered if r.get("ok"))
        print("\n=== zimage : %d/%d ok, total %ss ===" % (n_ok, len(ordered), total))
        print("meta: %s" % meta_path)


if __name__ == "__main__":
    main()
