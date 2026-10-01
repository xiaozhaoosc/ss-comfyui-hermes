# -*- coding: utf-8 -*-
"""Locate which custom node packs implement the H3*/MAINodes/PlagueKind nodes, and verify
whether they have real code (not stubs)."""
import os, json, urllib.request

BASE = r"D:\ai_projects\ComfyUI"
OUT = r"D:\ai_projects\ComfyUI\_probe3_result.txt"

# All H3-family + related node names we probed
NAMES = [
    "H3JerkHeatmap", "H3JerkOracle", "H3DriftControl", "H3DeltaColorCarry",
    "H3MotionComposite", "H3TimeSmear", "H3TimelineAnalyze", "H3TrajectoryBank",
    "H3TrajectoryLoad", "H3ClockRemap", "H3TrueClock", "H3PrefixFreezeMask",
    "H3ProtectPrefix", "H3ExactRecover", "H3AudioRecover", "H3SeamNormalize",
    "H3ModeSwitch", "H3MiniMaxCache", "H3LatentUpscale", "H3UpscaleSizeLD",
    "H3VideoFit", "H3TemporalInsert", "H3SLAAttention", "H3CapabilityProbe",
    "H3TimelineRender", "H3RepairPlan", "H3RepairSplice", "H3WindowPlan",
    "H3WindowPass", "H3WindowSeam", "H3WindowLoop", "H3WindowCrop",
    "H3WindowExpand", "H3WindowCollect", "H3SegmentCrop", "H3SegmentSplice",
    "H3Trim", "H3V2VInit", "H3MotionEditor", "H3DrawnPlan", "H3PlanEstimate",
    "H3PlanSettings", "H3InjectSchedule", "H3ExpertSchedule", "H3ProbeSchedule",
    "H3RecordStart", "H3RecordStop", "H3SceneColorStats", "H3LoadHoldMap",
    "H3ManualHoldMap", "H3SaveHoldMap", "H3LatentBank", "H3ConditioningBank",
    "H3ContactSheet", "H3ContactSheetDecode", "H3MidInsert", "H3TailContext",
    "H3DyRoPE", "H3AdaLNLoRAFix", "H3IndecisionOracle", "H3ExtensionPlan",
    "MMH3UltimateUpscale", "MiniMaxLowVRAMAttention",
    "MiniMaxH3MemoryEfficientSageAttentionPatch", "MiniMaxH3TokenCounter",
]

lines = []

# 1) map node name -> category (from object_info) to find the pack
req = urllib.request.Request("http://127.0.0.1:8188/object_info")
with urllib.request.urlopen(req, timeout=60) as r:
    info = json.loads(r.read().decode("utf-8"))

cats = {}
for n in NAMES:
    d = info.get(n)
    if d:
        cats.setdefault(d.get("category", "?"), []).append(n)

lines.append("=== node -> category (pack hint) ===")
for c in sorted(cats):
    lines.append("")
    lines.append("[%s]  (%d nodes)" % (c, len(cats[c])))
    for n in sorted(cats[c]):
        lines.append("   " + n)

# 2) find custom_nodes dirs whose py files mention these node names
lines.append("")
lines.append("=" * 70)
lines.append("=== custom_nodes packages referencing these node classes ===")
lines.append("=" * 70)

CN = os.path.join(BASE, "custom_nodes")
if os.path.isdir(CN):
    pkgs = sorted(os.listdir(CN))
    lines.append("custom_nodes entries: %d" % len(pkgs))

    # pick distinctive tokens
    TOKENS = ["H3JerkOracle", "H3TimelineAnalyze", "MMH3UltimateUpscale",
              "MiniMaxLowVRAMAttention", "H3SLAAttention", "H3DriftControl",
              "H3MotionComposite", "H3TrajectoryBank", "H3DeltaColorCarry"]

    for pkg in pkgs:
        pdir = os.path.join(CN, pkg)
        if not os.path.isdir(pdir):
            continue
        hits = set()
        py_count = 0
        for root, dirs, files in os.walk(pdir):
            dirs[:] = [d for d in dirs if d != ".git"]
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                py_count += 1
                fp = os.path.join(root, fn)
                try:
                    if os.path.getsize(fp) > 8_000_000:
                        continue
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                        txt = fh.read()
                except Exception:
                    continue
                for t in TOKENS:
                    if t in txt:
                        hits.add(t)
        if hits:
            lines.append("")
            lines.append("# %s  (py files: %d)" % (pkg, py_count))
            lines.append("    hits: %s" % ", ".join(sorted(hits)))
            lines.append("    path: %s" % pdir)
            # list top-level entries
            try:
                ents = sorted(os.listdir(pdir))
                lines.append("    entries: %s" % ", ".join(ents[:25]))
            except Exception:
                pass

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT, len(lines), "lines")
