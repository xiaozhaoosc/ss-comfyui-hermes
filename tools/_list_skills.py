import os, json, io, sys

out = []
roots = [
    r"C:\Users\kenzhao\.workbuddy\skills",
    r"C:\Users\kenzhao\.workbuddy\plugins\cache",
    r"D:\ai_projects\ComfyUI\.workbuddy\skills",
]
for r in roots:
    out.append("=== %s ===" % r)
    if not os.path.isdir(r):
        out.append("  (not exist)")
        continue
    try:
        for name in sorted(os.listdir(r)):
            p = os.path.join(r, name)
            if os.path.isdir(p):
                subs = []
                for dp, dn, fn in os.walk(p):
                    if "SKILL.md" in fn:
                        rel = os.path.relpath(os.path.join(dp, "SKILL.md"), p)
                        subs.append(rel)
                out.append("  %s/  skill_md=%d" % (name, len(subs)))
                for s in subs[:6]:
                    out.append("      %s" % s)
            else:
                out.append("  %s (file)" % name)
    except Exception as e:
        out.append("  ERR %s" % e)

targets = ["text-to-image-prompt", "video-editor", "sherpa-onnx-tts"]
out.append("")
out.append("=== search targets under .workbuddy ===")
base = r"C:\Users\kenzhao\.workbuddy"
for t in targets:
    hits = []
    for dp, dn, fn in os.walk(base):
        if t in dn:
            hits.append(os.path.join(dp, t))
        for f in fn:
            if t in f:
                hits.append(os.path.join(dp, f))
        if len(hits) > 20:
            break
    out.append("%s -> %s" % (t, hits if hits else "NOT FOUND"))

with io.open(r"D:\ai_projects\ComfyUI\_skills_list.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
