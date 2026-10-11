# -*- coding: utf-8 -*-
"""Probe ComfyUI /object_info for nodes relevant to H3 face-lock + temporal smoothing optimization."""
import json, urllib.request, os

COMFY = "http://127.0.0.1:8188"
OUT = r"D:\ai_projects\ComfyUI\_probe_result.txt"

lines = []


def get(ep, timeout=30):
    req = urllib.request.Request(COMFY + ep)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


try:
    info = get("/object_info", timeout=60)
    lines.append("object_info node count: %d" % len(info))
except Exception as e:
    lines.append("FAILED to fetch object_info: %r" % (e,))
    info = {}

# Keyword groups we care about
GROUPS = {
    "ReActor / faceswap": ["ReActor", "FaceSwap", "faceswap", "inswapper", "FaceRestore"],
    "face detect": ["FaceDetect", "YOLO", "RetinaFace", "MediaPipe", "SCRFD", "face_detection"],
    "temporal / smoothing": ["EMA", "Smooth", "Interpolat", "OpticalFlow", "Flow", "Temporal", "Deflicker", "Deflicker", "jitter"],
    "FaceDetailer / impact": ["FaceDetailer", "Detailer", "UltralyticsDetector", "SAMLoader", "SAM ", "BboxDetector", "SEGSDetailer", "MaskDetailer"],
    "upscale / restore": ["CodeFormer", "GFPGAN", "Restore", "Upscale", "ESRGAN", "RealESRGAN", "SwinIR"],
    "latent video / context": ["AnimateDiff", "Context", "LatentContext", "Chunk", "concat", "VideoLinearCFG"],
    "ipadapter / pulid / faceid": ["IPAdapter", "PuLID", "Pulid", "FaceID", "InstantID", "Redux", "StyleModel"],
    "video combine/output": ["VHS_", "VideoCombine", "SaveVideo", "CreateVideo"],
    "h3 / minimax": ["MiniMax", "H3"],
    "mask / composite": ["GrowMask", "ImageComposite", "RemoveBackground", "BiRefNet", "MaskToImage"],
    "color/frames util": ["ImageBlend", "ImageBatch", "LatentBatch", "RepeatImage", "ImageFromBatch", "GetImageRange"],
}

all_names = sorted(info.keys())

for gname, kws in GROUPS.items():
    lines.append("")
    lines.append("=== %s ===" % gname)
    hits = []
    for n in all_names:
        for k in kws:
            if k.lower() in n.lower():
                hits.append(n)
                break
    if not hits:
        lines.append("  (none)")
    for h in sorted(set(hits)):
        lines.append("  " + h)

# dump full input signature for the most important ones
lines.append("")
lines.append("=" * 70)
lines.append("FULL INPUT SIGNATURES")
lines.append("=" * 70)

INTEREST = [
    "ReActorFaceSwap", "ReActorFaceBoost",
    "MiniMaxH3ReferenceToVideo", "MiniMaxChunkFeedForward", "H3SLAAttention", "MiniMaxH3SigmaShift",
]


def sig(name):
    d = info.get(name)
    if not d:
        lines.append("  <%s> NOT FOUND" % name)
        return
    inp = d.get("input", {})
    lines.append("")
    lines.append("--- %s  (output: %s) ---" % (name, d.get("output")))
    for sect in ("required", "optional"):
        s = inp.get(sect) or {}
        if not s:
            continue
        lines.append("  [%s]" % sect)
        for k, v in s.items():
            t = v[0] if isinstance(v, list) and v else v
            if isinstance(t, list):
                t = "ENUM%s" % (t[:8],)
            extra = v[1] if isinstance(v, list) and len(v) > 1 and isinstance(v[1], dict) else {}
            dflt = (" default=%s" % extra.get("default")) if "default" in extra else ""
            lines.append("    %-28s %s%s" % (k, t, dflt))


for nm in INTEREST:
    sig(nm)

# search for any node with 'flow' or 'ema' anywhere
lines.append("")
lines.append("=== fuzzy: names containing flow/ema/smooth/temporal/deflicker ===")
for n in all_names:
    ln = n.lower()
    if any(k in ln for k in ("flow", "ema", "smooth", "temporal", "flicker", "jitter", "stab")):
        lines.append("  " + n)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT, len(lines), "lines")
