import os, io, json

out = []
mp = r"C:\Users\kenzhao\.workbuddy\skills-marketplace\skills"
out.append("=== %s ===" % mp)
if os.path.isdir(mp):
    names = sorted(os.listdir(mp))
    out.append("count=%d" % len(names))
    for n in names:
        p = os.path.join(mp, n)
        kind = "dir" if os.path.isdir(p) else "file"
        out.append("  %s (%s)" % (n, kind))
else:
    out.append("(not exist)")

targets = ["text-to-image-prompt", "video-editor", "sherpa-onnx-tts", "tts", "prompt", "editor"]
out.append("")
out.append("=== fuzzy match ===")
if os.path.isdir(mp):
    for t in targets:
        hits = [n for n in names if t.lower() in n.lower()]
        out.append("%-24s -> %s" % (t, hits if hits else "none"))

with io.open(r"D:\ai_projects\ComfyUI\_market_list.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
