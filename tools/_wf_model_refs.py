import os, io, json, re

base = r"C:\Users\kenzhao\.workbuddy\skills"
skills = ["comfy-cartoon-avatar", "comfy-lineart-colorization", "comfy-realtime-doodle"]
ext = re.compile(r"[\w\-\.\s\(\)]+\.(safetensors|ckpt|pth|bin|gguf|onnx)", re.I)

out = []
for s in skills:
    d = os.path.join(base, s)
    out.append("### %s" % s)
    if not os.path.isdir(d):
        out.append("  (missing)")
        continue
    files = []
    for dp, dn, fn in os.walk(d):
        for f in fn:
            files.append(os.path.join(dp, f))
    for f in sorted(files):
        if f.lower().endswith("models.txt"):
            out.append("  -- %s" % os.path.relpath(f, d))
            try:
                txt = open(f, "rb").read().decode("utf-8", "replace")
                for ln in txt.splitlines():
                    if ln.strip():
                        out.append("     %s" % ln.strip()[:160])
            except Exception as e:
                out.append("     ERR %s" % e)
    for f in sorted(files):
        if f.lower().endswith(".json"):
            try:
                j = json.load(open(f, "rb"))
            except Exception as e:
                continue
            hits = set()
            def walk(o):
                if isinstance(o, dict):
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
                elif isinstance(o, str):
                    for m in ext.finditer(o):
                        hits.add(m.group(0).strip())
            walk(j)
            if hits:
                out.append("  -- %s 引用的模型文件:" % os.path.relpath(f, d))
                for h in sorted(hits):
                    out.append("     %s" % h)
    out.append("")

with io.open(r"D:\ai_projects\ComfyUI\_wf_model_refs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
