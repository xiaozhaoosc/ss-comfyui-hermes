# -*- coding: utf-8 -*-
"""Validate all v5 profile graphs server-side without executing them.

ComfyUI's /prompt validates node inputs and returns a structured error before
queuing. We exploit that: submit each graph, and if the response is a
validation error, report it; if it queues successfully, immediately interrupt
and clear so nothing actually runs.
"""
import io, json, os, sys, urllib.request, urllib.error

sys.path.insert(0, r"D:\ai_projects\ComfyUI\tools")
import h3_rope_common as C  # noqa
import run_h3_guard_v5 as V  # noqa

OUT = r"D:\ai_projects\ComfyUI\_validate_v5.txt"
lines = []

profiles = list(V.PROFILES.keys())
lines.append("validating %d profiles: %s" % (len(profiles), ", ".join(profiles)))
lines.append("")

ok_count = 0
for i, p in enumerate(profiles):
    prof = V.PROFILES[p]
    try:
        g = V.build_graph(
            p,
            video="shiling_dance_wave.mp4",
            char="characters/v3/C01_FACE_FRONT.png",
            bg=None,
            width=prof.get("width", 448),
            height=prof.get("height", 768),
            length=73, seed=42 + i, fps=24.0,
            prefix="h3_%s" % p,
        )
    except Exception as e:
        lines.append("[BUILD-FAIL] %-9s %r" % (p, e))
        import traceback
        lines.append(traceback.format_exc())
        continue

    # classify node types present
    types = sorted({n["class_type"] for n in g.values()})
    lines.append("=" * 70)
    lines.append("profile: %s   nodes=%d  types=%d" % (p, len(g), len(types)))
    lines.append("  " + ", ".join(types))

    body = json.dumps({"prompt": g}).encode("utf-8")
    req = urllib.request.Request(C.COMFY + "/prompt", data=body,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read().decode("utf-8"))
        pid = res.get("prompt_id")
        lines.append("  => QUEUED OK  prompt_id=%s  (validation passed)" % pid)
        ok_count += 1
        # immediately stop it: we only wanted validation
        try:
            C.interrupt_and_clear()
            lines.append("  => interrupted+cleared (validation only)")
        except Exception as e:
            lines.append("  => cleanup warn: %r" % (e,))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        lines.append("  => VALIDATION ERROR HTTP %s" % e.code)
        try:
            err = json.loads(raw)
            node_errors = err.get("node_errors") or {}
            if node_errors:
                for nid, ne in node_errors.items():
                    ct = g.get(nid, {}).get("class_type", "?")
                    lines.append("     node %s (%s):" % (nid, ct))
                    for msg in (ne.get("errors") or []):
                        lines.append("       - %s: %s" % (msg.get("type"), msg.get("details")))
            ml = err.get("error") or {}
            if ml:
                lines.append("     top-level: %s %s" % (ml.get("type"), ml.get("message")))
                lines.append("     details: %s" % str(ml.get("details"))[:600])
            if not node_errors and not ml:
                lines.append("     raw: " + raw[:1500])
        except Exception:
            lines.append("     raw: " + raw[:1500])
    except Exception as e:
        lines.append("  => TRANSPORT ERROR %r" % (e,))
    lines.append("")

lines.append("=" * 70)
lines.append("RESULT: %d/%d profiles passed server-side validation" % (ok_count, len(profiles)))
lines.append("(NOTE: success means the graph is structurally valid and all node inputs")
lines.append(" are spelled correctly. It does NOT prove the render is good — that")
lines.append(" needs a real run.)")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("WROTE", OUT)
print("passed %d/%d" % (ok_count, len(profiles)))
