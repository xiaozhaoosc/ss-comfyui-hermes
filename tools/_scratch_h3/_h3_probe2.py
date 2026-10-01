# -*- coding: utf-8 -*-
"""Deep-dive into specific high-value nodes for H3 face-stability optimization."""
import json, urllib.request

COMFY = "http://127.0.0.1:8188"
OUT = r"D:\ai_projects\ComfyUI\_probe2_result.txt"

req = urllib.request.Request(COMFY + "/object_info")
with urllib.request.urlopen(req, timeout=60) as r:
    info = json.loads(r.read().decode("utf-8"))

TARGETS = [
    # core face pipeline
    "ReActorFaceSwapOpt",
    "ReActorRestoreFaceAdvanced",
    "ReActorOptions",
    "ReActorMaskHelper",
    "ReActorFaceSimilarity",
    "ReActorSetWeight",
    "ReActorBuildFaceModel",
    "ReActorLoadFaceModel",
    "ReActorSaveFaceModel",
    # detectors available
    "UltralyticsDetectorProvider",
    # H3 motion / jerk analysis (very promising!)
    "H3JerkHeatmap",
    "H3JerkOracle",
    "H3DriftControl",
    "H3DeltaColorCarry",
    "H3MotionComposite",
    "H3TimeSmear",
    "H3TimelineAnalyze",
    "H3TrajectoryBank",
    "H3TrajectoryLoad",
    "H3ClockRemap",
    "H3TrueClock",
    "H3PrefixFreezeMask",
    "H3ProtectPrefix",
    "H3ExactRecover",
    "H3AudioRecover",
    "H3SeamNormalize",
    "H3ModeSwitch",
    "H3Cache" ,
    "H3MiniMaxCache",
    "H3LatentUpscale",
    "H3UpscaleSizeLD",
    "H3VideoFit",
    "H3TemporalInsert",
    # optical flow / temporal
    "OpticalFlowLoader",
    "MaskOptFlow",
    "Unimatch_OptFlowPreprocessor",
    "FrameInterpolate",
    "RIFEInterpolation",
    "FrameInterpolationModelLoader",
    "TemporalScoreRescaling",
    "UNetTemporalAttentionMultiply",
    # upscale
    "UpscaleModelLoader",
    "ImageUpscaleWithModel",
    "ImageUpscaleWithModelBatched",
    "MMH3UltimateUpscale",
    # mediapipe
    "MediaPipeFaceLandmarker",
    # misc
    "ImageBlend",
    "ImageFromBatch",
    "GetImageRangeFromBatch",
    "ImageBatchExtendWithOverlap",
    "ImageBatchJoinWithTransition",
    "VHS_LoadVideo",
]

lines = []
found, missing = [], []


def sig(name):
    d = info.get(name)
    if not d:
        missing.append(name)
        return
    found.append(name)
    inp = d.get("input", {})
    lines.append("")
    lines.append("--- %s ---" % name)
    oc = d.get("output")
    on = d.get("output_name")
    lines.append("  output: %s  names: %s" % (oc, on))
    lines.append("  category: %s" % d.get("category"))
    for sect in ("required", "optional"):
        s = inp.get(sect) or {}
        if not s:
            continue
        lines.append("  [%s]" % sect)
        for k, v in s.items():
            t = v[0] if isinstance(v, list) and v else v
            if isinstance(t, list):
                t = "ENUM%s" % (str(t[:12]),)
            extra = v[1] if isinstance(v, list) and len(v) > 1 and isinstance(v[1], dict) else {}
            bits = []
            if "default" in extra:
                bits.append("default=%s" % extra["default"])
            if "min" in extra:
                bits.append("min=%s" % extra["min"])
            if "max" in extra:
                bits.append("max=%s" % extra["max"])
            if extra.get("multiline"):
                bits.append("multiline")
            lines.append("    %-30s %-34s %s" % (k, t, " ".join(bits)))


for t in TARGETS:
    sig(t)

lines.append("")
lines.append("=" * 60)
lines.append("MISSING (%d): %s" % (len(missing), ", ".join(missing)))
lines.append("FOUND  (%d)" % len(found))

# Also dump the COMPLETE list of node names to a file for reference
with open(r"D:\ai_projects\ComfyUI\_all_nodes.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(sorted(info.keys())))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
