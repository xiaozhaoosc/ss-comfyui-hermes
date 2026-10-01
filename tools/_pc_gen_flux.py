# -*- coding: utf-8 -*-
"""Generate the prompt set with Flux Dev (T8 abliterated GGUF) + optional Asian-mix LoRA.

Flux topology:
  UnetLoaderGGUF -> MODEL
  DualCLIPLoaderGGUF(clip_l + t5xxl, type=flux) -> CLIP
  VAELoader(flux-vae-bf16) -> VAE
  CLIPTextEncode(pos) -> CONDITIONING -> FluxGuidance(3.5) -> KSampler positive
  (negative = zeroed conditioning, cfg=1.0 so unused)
  EmptySD3LatentImage -> KSampler -> VAEDecode -> SaveImage

Usage: python tools/_pc_gen_flux.py <variant> [--scenes s01] [--steps 20]
  variant: q8 | q6 | q4 | fp8
"""
import os, sys, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _pc_common import submit, wait, collect_outputs, save_meta, OUT_ROOT
import _pc_prompts as P
import importlib
importlib.reload(P)

VARIANTS = {
    "q8":  ("T8-flux.1-dev-abliterated-V2-GGUF-Q8_0.gguf", "flux_dev_q8"),
    "q6":  ("T8-flux.1-dev-abliterated-V2-GGUF-Q6_K.gguf", "flux_dev_q6"),
    "q4":  ("T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M.gguf", "flux_dev_q4"),
    "fp8": ("flux1-dev-fp8.safetensors", "flux_dev_fp8"),
}

T5 = "t5xxl_fp8_e4m3fn.safetensors"
CLIP_L = "clip_l.safetensors"
VAE = "flux-vae-bf16.safetensors"
LORA_ASIAN = "hinaFluxDevAsianMix_v12.safetensors"

FLUX_NEG = P.FLUX_NEG  # abliterated base: explicit clothing/safety negative


def build(unet, pos, w, h, steps, seed, prefix, guidance=3.5,
          lora=None, lora_strength=0.8, use_gguf=True):
    loader = "UnetLoaderGGUF" if use_gguf else "UNETLoader"
    key = "unet_name"
    pos = P.FLUX_ANCHOR + pos
    node1 = ({key: unet} if use_gguf
             else {key: unet, "weight_dtype": "default"})
    g = {
        "1": {"class_type": loader, "inputs": node1},
        "2": {"class_type": "DualCLIPLoaderGGUF" if use_gguf else "DualCLIPLoader",
              "inputs": {"clip_name1": CLIP_L, "clip_name2": T5, "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"text": pos, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"text": FLUX_NEG, "clip": ["2", 0]}},
        "6": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    }
    model_ref = ["1", 0]
    clip_ref = ["2", 0]
    if lora:
        g["20"] = {"class_type": "LoraLoader",
                   "inputs": {"lora_name": lora,
                              "strength_model": lora_strength,
                              "strength_clip": lora_strength,
                              "model": ["1", 0], "clip": ["2", 0]}}
        model_ref = ["20", 0]
        clip_ref = ["20", 1]
        g["4"]["inputs"]["clip"] = clip_ref
        g["5"]["inputs"]["clip"] = clip_ref

    g["10"] = {"class_type": "FluxGuidance",
               "inputs": {"guidance": guidance, "conditioning": ["4", 0]}}
    g["7"] = {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": steps, "cfg": 1.0,
                         "sampler_name": "euler", "scheduler": "simple",
                         "denoise": 1.0, "model": model_ref,
                         "positive": ["10", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0]}}
    return g


def main():
    variant = sys.argv[1]
    unf, sub = VARIANTS[variant]
    use_gguf = not unf.endswith(".safetensors")

    only = None
    steps = 20
    w = h = 768
    guidance = 3.5
    lora = None
    for i, a in enumerate(sys.argv):
        if a == "--scenes" and i + 1 < len(sys.argv):
            only = set(x.strip() for x in sys.argv[i + 1].split(",") if x.strip())
        if a == "--steps" and i + 1 < len(sys.argv):
            steps = int(sys.argv[i + 1])
        if a == "--size" and i + 1 < len(sys.argv):
            w = h = int(sys.argv[i + 1])
        if a == "--wh" and i + 1 < len(sys.argv):
            w, h = [int(x) for x in sys.argv[i + 1].split("x")]
        if a == "--guidance" and i + 1 < len(sys.argv):
            guidance = float(sys.argv[i + 1])
        if a == "--lora" and i + 1 < len(sys.argv):
            lora = sys.argv[i + 1]

    outdir = os.path.join(OUT_ROOT, sub)
    os.makedirs(outdir, exist_ok=True)
    results = []
    t_all = time.time()
    sbase = 710000

    for i, sc in enumerate(P.SCENES):
        if only and sc["id"] not in only:
            continue
        seed = sbase + i
        prefix = "pc_%s_%s" % (sub, sc["id"])
        graph = build(unf, sc["flux"], w, h, steps, seed, prefix,
                      guidance=guidance, lora=lora, use_gguf=use_gguf)
        ok, pid = submit(graph)
        print("[submit] %s seed=%s -> %s %s" % (sc["id"], seed, ok, pid), flush=True)
        if not ok:
            results.append({"scene": sc["id"], "ok": False, "err": str(pid)[:900]})
            continue
        t0 = time.time()
        done, hist = wait(pid, timeout=1800)
        dt = round(time.time() - t0, 1)
        files = collect_outputs(hist) if done else []
        st = (hist or {}).get("status", {}) if done else {}
        err = json.dumps(st, ensure_ascii=False)[:400] if not files else ""
        print("   [done] %s in %ss files=%s %s" % (done, dt,
              [f["filename"] for f in files], err), flush=True)
        results.append({"scene": sc["id"], "ok": bool(files), "prompt_id": pid,
                        "seconds": dt, "seed": seed, "files": files,
                        "unet": unf, "steps": steps, "guidance": guidance,
                        "size": [w, h], "lora": lora,
                        "note": sc["note"], "prompt_en": sc["flux"],
                        "status": st})

    total = round(time.time() - t_all, 1)
    save_meta(os.path.join(outdir, "_run.json"),
              {"unet": unf, "variant": variant, "total_seconds": total,
               "results": results})
    n_ok = sum(1 for r in results if r.get("ok"))
    print("\n=== flux %s : %d/%d ok, total %ss ===" % (unf, n_ok, len(results), total))


if __name__ == "__main__":
    main()
