# -*- coding: utf-8 -*-
"""Inventory: models on disk relevant to H3 de-rope / low-VRAM / upscale + example graphs."""
import os, json, urllib.request

BASE = r"D:\ai_projects\ComfyUI"
OUT = r"D:\ai_projects\ComfyUI\_asset_inv.txt"
lines = []


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return "%.2f %s" % (n, u)
        n /= 1024.0
    return "%.2f PB" % n


def scan(d, exts, label, recurse=True):
    lines.append("")
    lines.append("=== %s ===" % label)
    lines.append("  dir: %s  (exists=%s)" % (d, os.path.isdir(d)))
    if not os.path.isdir(d):
        return
    found = []
    if recurse:
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if not x.startswith(".")]
            for fn in files:
                if any(fn.lower().endswith(e) for e in exts):
                    fp = os.path.join(root, fn)
                    try:
                        sz = os.path.getsize(fp)
                    except Exception:
                        sz = -1
                    rel = os.path.relpath(fp, d)
                    found.append((rel, sz))
    else:
        for fn in os.listdir(d):
            fp = os.path.join(d, fn)
            if os.path.isfile(fp) and any(fn.lower().endswith(e) for e in exts):
                found.append((fn, os.path.getsize(fp)))
    found.sort(key=lambda t: -t[1])
    for rel, sz in found:
        lines.append("  %-70s %s" % (rel, human(sz) if sz >= 0 else "?"))
    lines.append("  TOTAL: %d file(s)" % len(found))


M = os.path.join(BASE, "models")

# diffusion models (H3 family + turbo loras)
scan(os.path.join(M, "diffusion_models"), [".safetensors", ".ckpt", ".gguf", ".pt"], "diffusion_models (unet)")
scan(os.path.join(M, "unet"), [".safetensors", ".ckpt", ".gguf", ".pt"], "unet")
scan(os.path.join(M, "text_encoders"), [".safetensors", ".gguf", ".pt", ".bin"], "text_encoders")
scan(os.path.join(M, "clip"), [".safetensors", ".gguf", ".pt", ".bin"], "clip")
scan(os.path.join(M, "vae"), [".safetensors", ".pt", ".ckpt"], "vae")

# LoRAs - H3 / lightx2v / motion adapter
LORA = os.path.join(M, "loras")
lines.append("")
lines.append("=== loras: H3 / turbo / motion / lightx2v subset ===")
if os.path.isdir(LORA):
    all_lora = []
    for root, dirs, files in os.walk(LORA):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for fn in files:
            if fn.lower().endswith((".safetensors", ".pt", ".ckpt")):
                fp = os.path.join(root, fn)
                try:
                    all_lora.append((os.path.relpath(fp, LORA), os.path.getsize(fp)))
                except Exception:
                    pass
    lines.append("  total loras on disk: %d" % len(all_lora))
    KEY = ("h3", "minimax", "turbo", "lightx2v", "motion", "derope", "de-rope", "sla")
    hits = [t for t in all_lora if any(k in t[0].lower() for k in KEY)]
    hits.sort(key=lambda t: -t[1])
    for rel, sz in hits:
        lines.append("  %-72s %s" % (rel, human(sz)))
    lines.append("  (matched %d)" % len(hits))

# upscale models
scan(os.path.join(M, "upscale_models"), [".safetensors", ".pth", ".pt"], "upscale_models")
# reactor models
scan(os.path.join(M, "insightface"), [".onnx"], "insightface (faceswap)")
scan(os.path.join(M, "facerestore_models"), [".pth", ".onnx"], "facerestore_models")
scan(os.path.join(M, "sams"), [".pth"], "sams")
scan(os.path.join(M, "ultralytics"), [".pt"], "ultralytics (bbox/segm)")

# character refs
scan(os.path.join(BASE, "input", "characters"), [".png", ".jpg", ".jpeg", ".webp"], "input/characters (refs)", recurse=True)
# input videos
scan(os.path.join(BASE, "input"), [".mp4", ".mov", ".mkv"], "input videos", recurse=False)

# MAINodes examples
EX = os.path.join(BASE, "custom_nodes", "ComfyUI-MAINodes", "examples")
lines.append("")
lines.append("=== MAINodes examples/ ===")
if os.path.isdir(EX):
    for root, dirs, files in os.walk(EX):
        rel = os.path.relpath(root, EX)
        js = sorted(f for f in files if f.endswith(".json"))
        if js:
            lines.append("  [%s]" % rel)
            for f in js:
                lines.append("     " + f)
else:
    lines.append("  (not found)")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
