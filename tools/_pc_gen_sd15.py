# -*- coding: utf-8 -*-
"""Generate the prompt set with an SD1.5 checkpoint (majicmixRealistic / Counterfeit / AOM3).

Usage:
  python tools/_pc_gen_sd15.py <ckpt_name> <out_subdir> [--scenes s01,s02] [--steps 28]
"""
import os, sys, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pc_common import (submit, wait, collect_outputs, save_meta, OUT_ROOT, BASE)
import _pc_prompts as P

CONFIG = {
    # ckpt_name : (steps, cfg, sampler, scheduler, width, height, seed_base, lora)
    "majicmixRealistic_v7.safetensors": (30, 7.0, "dpmpp_2m", "karras", 512, 768, 210000, None),
    "Counterfeit-V3.0_fp16.safetensors": (28, 8.0, "dpmpp_2m", "karras", 512, 768, 310000, None),
    "AOM3A3_orangemixs.safetensors": (28, 8.0, "dpmpp_2m", "karras", 512, 768, 410000, None),
}


def build(ckpt, pos, neg, w, h, steps, cfg, sampler, sched, seed, prefix, lora=None):
    """Minimal txt2img API graph. Node ids are strings."""
    g = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": pos, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": neg, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": cfg,
                         "sampler_name": sampler, "scheduler": sched,
                         "denoise": 1.0, "model": ["1", 0],
                         "positive": ["2", 0], "negative": ["3", 0],
                         "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["6", 0]}},
    }
    if lora:
        # insert LoraLoader between ckpt and CLIP/KSampler
        g["10"] = {"class_type": "LoraLoader",
                   "inputs": {"lora_name": lora, "strength_model": 0.8,
                              "strength_clip": 0.8, "model": ["1", 0], "clip": ["1", 1]}}
        g["2"]["inputs"]["clip"] = ["10", 1]
        g["3"]["inputs"]["clip"] = ["10", 1]
        g["5"]["inputs"]["model"] = ["10", 0]
    return g


def main():
    ckpt = sys.argv[1]
    sub = sys.argv[2]
    only = None
    steps_override = None
    for i, a in enumerate(sys.argv):
        if a == "--scenes" and i + 1 < len(sys.argv):
            only = set(sys.argv[i + 1].split(","))
        if a == "--steps" and i + 1 < len(sys.argv):
            steps_override = int(sys.argv[i + 1])

    steps, cfg, sampler, sched, w, h, sbase, lora = CONFIG[ckpt]
    if steps_override:
        steps = steps_override

    outdir = os.path.join(OUT_ROOT, sub)
    os.makedirs(outdir, exist_ok=True)
    results = []
    t_all = time.time()

    for i, sc in enumerate(P.SCENES):
        if only and sc["id"] not in only:
            continue
        seed = sbase + i
        prefix = "pc_%s_%s" % (sub, sc["id"])
        graph = build(ckpt, P.sd_positive(sc), P.SD_NEG, w, h, steps, cfg,
                      sampler, sched, seed, prefix, lora)
        ok, pid = submit(graph)
        print("[submit] %s seed=%s -> %s %s" % (sc["id"], seed, ok, pid), flush=True)
        if not ok:
            results.append({"scene": sc["id"], "ok": False, "err": str(pid)[:600]})
            continue
        t0 = time.time()
        done, hist = wait(pid, timeout=900)
        dt = round(time.time() - t0, 1)
        files = collect_outputs(hist) if done else []
        print("   [done] %s in %ss files=%s" % (done, dt, [f["filename"] for f in files]), flush=True)
        results.append({"scene": sc["id"], "ok": bool(files), "prompt_id": pid,
                        "seconds": dt, "seed": seed, "files": files,
                        "ckpt": ckpt, "steps": steps, "cfg": cfg,
                        "sampler": sampler, "scheduler": sched,
                        "size": [w, h], "lora": lora,
                        "note": sc["note"], "prompt_en": sc["sd"]})

    total = round(time.time() - t_all, 1)
    # merge with any previous partial run so a resumed batch keeps full history
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
    save_meta(meta_path,
              {"ckpt": ckpt, "total_seconds": total, "results": ordered})
    n_ok = sum(1 for r in ordered if r.get("ok"))
    print("\n=== %s : %d/%d ok, total %ss ===" % (ckpt, n_ok, len(ordered), total))


if __name__ == "__main__":
    main()
