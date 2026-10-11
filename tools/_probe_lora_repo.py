import io, json, urllib.request

REPOS = [
    "JosephMinchala/JosephMinchala-skin-texture-zturbo-v45",
    "suayptalha/Z-Image-Turbo-Realism-LoRA",
]
out = []
for repo in REPOS:
    out.append("=== %s ===" % repo)
    try:
        url = "https://huggingface.co/api/models/" + repo
        req = urllib.request.Request(url, headers={"User-Agent": "python"})
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        for f in d.get("siblings", []):
            name = f.get("rfilename")
            if name and (name.endswith(".safetensors") or name.endswith(".bin")):
                out.append("   %s" % name)
        out.append("   (共 %d 个文件)" % len(d.get("siblings", [])))
    except Exception as e:
        out.append("   ERR %s: %s" % (type(e).__name__, str(e)[:140]))
    out.append("")

with io.open(r"D:\ai_projects\ComfyUI\_probe_lora_repo.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
