import os, io, re, shutil

out = []
base = r"C:\Users\kenzhao\.workbuddy\skills"
skills = ["comfy-cartoon-avatar", "comfy-lineart-colorization", "comfy-realtime-doodle",
          "comfyui-imagegen", "comfyui-image-gen", "comfyui-upscaler"]

MODEL_PAT = re.compile(r"(safetensors|gguf|\.pth|\.bin|checkpoint|checkpoints/|models/|"
                       r"huggingface|civitai|下载|diffusion_models|text_encoders|vae|"
                       r"controlnet|unet|lora|ip-?adapter|instantid|hyper|sdxl|flux)", re.I)

out.append("=" * 72)
out.append("PART 1: 各空壳技能声明的模型需求")
for s in skills:
    d = os.path.join(base, s)
    out.append("")
    out.append("### %s" % s)
    if not os.path.isdir(d):
        out.append("  (not installed)")
        continue
    for dp, dn, fn in os.walk(d):
        for f in fn:
            if not f.lower().endswith(".md"):
                continue
            p = os.path.join(dp, f)
            try:
                txt = open(p, "rb").read().decode("utf-8", "replace")
            except Exception:
                continue
            for i, ln in enumerate(txt.splitlines(), 1):
                if MODEL_PAT.search(ln):
                    rel = os.path.relpath(p, d)
                    out.append("  %s:%d| %s" % (rel, i, ln.strip()[:220]))

out.append("")
out.append("=" * 72)
out.append("PART 2: 本机 models 目录现有权重（>=100MB）")
mroot = r"D:\ai_projects\ComfyUI\models"
if os.path.isdir(mroot):
    for sub in sorted(os.listdir(mroot)):
        sp = os.path.join(mroot, sub)
        if not os.path.isdir(sp):
            continue
        items = []
        try:
            for f in os.listdir(sp):
                fp = os.path.join(sp, f)
                if os.path.isfile(fp) and os.path.getsize(fp) >= 100 * 1024 * 1024:
                    items.append((f, os.path.getsize(fp) / (1024.0 ** 3)))
        except Exception as e:
            out.append("  %s ERR %s" % (sub, e))
            continue
        if items:
            out.append("  [%s]" % sub)
            for f, g in sorted(items, key=lambda x: -x[1]):
                out.append("      %-70s %.2f GB" % (f, g))
else:
    out.append("  models dir missing: %s" % mroot)

out.append("")
out.append("=" * 72)
out.append("PART 3: 磁盘剩余空间")
for drv in ["C:\\", "D:\\"]:
    try:
        t, u, f = shutil.disk_usage(drv)
        out.append("  %s total=%.0f GB used=%.0f GB free=%.0f GB" % (
            drv, t / 1024.0 ** 3, u / 1024.0 ** 3, f / 1024.0 ** 3))
    except Exception as e:
        out.append("  %s ERR %s" % (drv, e))

out.append("")
out.append("PART 4: 关键文件名是否已存在（模糊匹配）")
needles = ["sdxl", "sd_xl", "z_image", "z-image", "flux2", "flux_2", "klein",
           "ip-adapter", "ip_adapter", "hyper", "canny", "4x", "upscale"]
found = {}
for dp, dn, fn in os.walk(mroot):
    for f in fn:
        low = f.lower()
        for n in needles:
            if n in low:
                found.setdefault(n, []).append(os.path.relpath(os.path.join(dp, f), mroot))
for n in needles:
    out.append("  %-14s -> %s" % (n, found.get(n, ["NONE"])[:6]))

with io.open(r"D:\ai_projects\ComfyUI\_hollow_audit.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
