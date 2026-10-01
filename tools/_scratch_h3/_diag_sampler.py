# -*- coding: utf-8 -*-
"""
Diagnose the `unhashable type: 'list'` on SamplerCustomAdvanced.

Hypothesis: it's the sigmas/guider/sampler combination rather than latent_image.
We bisect by building:
  T1: the official example graph UNCHANGED (should pass) -> control
  T2: our base graph but sampler swapped to gradient_estimation
  T3: our base graph but with H3InjectSchedule instead of BasicScheduler
  T4: our base graph but LoraLoaderModelOnly removed
  T5: our base graph but SigmaShift removed
Each is validated via /prompt then interrupted.
"""
import copy, json, sys, urllib.request, urllib.error
sys.path.insert(0, r"D:\ai_projects\ComfyUI\tools")
import h3_rope_common as C
import run_h3_guard_v5 as V

OUT = r"D:\ai_projects\ComfyUI\_diag_sampler.txt"
lines = []

EX = r"D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-MAINodes\examples\motion_pipeline_ref2va_audioinit_api.json"


def try_submit(name, g):
    body = json.dumps({"prompt": g}).encode("utf-8")
    req = urllib.request.Request(C.COMFY + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode("utf-8"))
        C.interrupt_and_clear()
        lines.append("[PASS] %-46s prompt_id=%s" % (name, res.get("prompt_id")))
        return True
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        lines.append("[FAIL] %-46s HTTP %s" % (name, e.code))
        try:
            err = json.loads(raw)
            for nid, ne in (err.get("node_errors") or {}).items():
                ct = g.get(nid, {}).get("class_type", "?")
                for m in (ne.get("errors") or []):
                    lines.append("         node %s (%s): %s | %s" % (
                        nid, ct, m.get("type"), str(m.get("details"))[:400]))
        except Exception:
            lines.append("         raw: " + raw[:600])
        return False
    except Exception as e:
        lines.append("[ERR ] %-46s %r" % (name, e))
        return False


# ---------- T1: official example, control ----------
with open(EX, "r", encoding="utf-8") as f:
    ex = json.load(f)
# point it at files that exist locally so the graph is valid
for nid, n in ex.items():
    ct = n["class_type"]
    if ct == "UNETLoader":
        n["inputs"]["unet_name"] = V.UNET_REF2VA
    if ct == "CLIPLoader":
        n["inputs"]["clip_name"] = V.TE_NVFP4
    if ct == "VAELoader":
        if "video" in n["inputs"]["vae_name"]:
            n["inputs"]["vae_name"] = V.VAE_VINT8
        else:
            n["inputs"]["vae_name"] = V.VAE_AUDIO
    if ct == "LoraLoaderModelOnly":
        n["inputs"]["lora_name"] = V.LORA_TURBO
    if ct == "LoadImage":
        n["inputs"]["image"] = "characters/v3/C01_FACE_FRONT.png"
    if ct == "SaveVideo":
        n["inputs"]["filename_prefix"] = "diag/t1"
# strip the extra saves to keep it lean
try_submit("T1 official example (control)", ex)

# ---------- T2..T5: mutate our base graph ----------
base = V.build_graph("base", video="shiling_dance_wave.mp4",
                     char="characters/v3/C01_FACE_FRONT.png", bg=None,
                     width=448, height=768, length=73, seed=42, fps=24.0,
                     prefix="diag/base")

# T2: sampler -> gradient_estimation
g2 = copy.deepcopy(base)
for nid, n in g2.items():
    if n["class_type"] == "KSamplerSelect":
        n["inputs"]["sampler_name"] = "gradient_estimation"
for nid, n in g2.items():
    if n["class_type"] == "SaveVideo":
        n["inputs"]["filename_prefix"] = "diag/t2"
try_submit("T2 base + gradient_estimation", g2)

# T3: BasicScheduler -> H3InjectSchedule
g3 = copy.deepcopy(base)
sig_id = None
for nid, n in g3.items():
    if n["class_type"] == "BasicScheduler":
        sig_id = nid
        break
if sig_id:
    model_in = g3[sig_id]["inputs"]["model"]
    g3[sig_id] = {"class_type": "H3InjectSchedule", "inputs": {
        "model": model_in, "scheduler": "beta", "total_steps": 6, "inject": 0.7,
        "preset": "custom"}}
for nid, n in g3.items():
    if n["class_type"] == "SaveVideo":
        n["inputs"]["filename_prefix"] = "diag/t3"
try_submit("T3 base + H3InjectSchedule sigmas", g3)

# T4: drop LoRA
g4 = copy.deepcopy(base)
lora_id = None
for nid, n in g4.items():
    if n["class_type"] == "LoraLoaderModelOnly":
        lora_id = nid
        break
if lora_id:
    upstream = g4[lora_id]["inputs"]["model"]
    for nid, n in g4.items():
        for k, v in list(n["inputs"].items()):
            if isinstance(v, list) and len(v) == 2 and v[0] == lora_id:
                n["inputs"][k] = upstream
    del g4[lora_id]
for nid, n in g4.items():
    if n["class_type"] == "SaveVideo":
        n["inputs"]["filename_prefix"] = "diag/t4"
try_submit("T4 base without LoRA", g4)

# T5: drop SigmaShift
g5 = copy.deepcopy(base)
ss_id = None
for nid, n in g5.items():
    if n["class_type"] == "MiniMaxH3SigmaShift":
        ss_id = nid
        break
if ss_id:
    upstream = g5[ss_id]["inputs"]["model"]
    for nid, n in g5.items():
        for k, v in list(n["inputs"].items()):
            if isinstance(v, list) and len(v) == 2 and v[0] == ss_id:
                n["inputs"][k] = upstream
    del g5[ss_id]
for nid, n in g5.items():
    if n["class_type"] == "SaveVideo":
        n["inputs"]["filename_prefix"] = "diag/t5"
try_submit("T5 base without SigmaShift", g5)

# T6: base but ReActor chain removed
g6 = copy.deepcopy(base)
del_ids = [nid for nid, n in g6.items()
           if n["class_type"].startswith("ReActor")]
if del_ids:
    # VAEDecode output 0 -> CreateVideo images
    dec = None
    for nid, n in g6.items():
        if n["class_type"] == "VAEDecode":
            dec = nid
            break
    for nid in list(g6.keys()):
        if nid in del_ids:
            del g6[nid]
    for nid, n in g6.items():
        for k, v in list(n["inputs"].items()):
            if isinstance(v, list) and len(v) == 2 and v[0] in del_ids:
                n["inputs"][k] = [dec, 0]
for nid, n in g6.items():
    if n["class_type"] == "SaveVideo":
        n["inputs"]["filename_prefix"] = "diag/t6"
try_submit("T6 base without ReActor chain", g6)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
