import os, io, json, shutil, time

MROOT = r"D:\ai_projects\ComfyUI\models"
SKB = r"C:\Users\kenzhao\.workbuddy\skills"
out = []


def log(m):
    out.append(m)


# 1) 把 control-lora-canny-rank128 改成工作流引用的名字 sai_xl_canny_128lora
src = os.path.join(MROOT, "controlnet", "control-lora-canny-rank128.safetensors")
dst = os.path.join(MROOT, "controlnet", "sai_xl_canny_128lora.safetensors")
if os.path.exists(src) and not os.path.exists(dst):
    shutil.move(src, dst)
    log("RENAME control-lora-canny-rank128.safetensors -> sai_xl_canny_128lora.safetensors")
elif os.path.exists(dst):
    log("OK already: %s (%.2f GB)" % (dst, os.path.getsize(dst) / 1024.0 ** 3))
else:
    log("WARN missing source: %s" % src)

# 2) 工作流里的底模名替换为本机已有 SDXL
LOCAL_SDXL = "RealVisXL_V4.0.safetensors"
ckpt_ok = os.path.exists(os.path.join(MROOT, "checkpoints", LOCAL_SDXL))
log("local sdxl checkpoint %s exists=%s" % (LOCAL_SDXL, ckpt_ok))

FIXES = [
    ("comfy-lineart-colorization", "dreamshaperXL_v21TurboDPMSDE.safetensors", LOCAL_SDXL),
    ("comfy-realtime-doodle", "sd_xl_base_1.0_0.9vae.safetensors", LOCAL_SDXL),
]

for skill, old, new in FIXES:
    d = os.path.join(SKB, skill)
    hits = 0
    for dp, dn, fn in os.walk(d):
        for f in fn:
            if not f.lower().endswith(".json"):
                continue
            p = os.path.join(dp, f)
            try:
                txt = open(p, "rb").read().decode("utf-8")
            except Exception:
                continue
            if old not in txt:
                continue
            bak = p + ".bak_" + time.strftime("%Y%m%d")
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
            txt2 = txt.replace(old, new)
            with io.open(p, "w", encoding="utf-8") as fh:
                fh.write(txt2)
            hits += txt.count(old)
            log("PATCH %s/%s : %s -> %s (%d 处)" % (skill, f, old, new, txt.count(old)))
    if hits == 0:
        log("NOCHANGE %s (未找到 %s)" % (skill, old))

    note = os.path.join(d, "LOCAL_ADAPT_NOTE.md")
    with io.open(note, "w", encoding="utf-8") as fh:
        fh.write("# 本机适配说明（%s）\n\n" % time.strftime("%Y-%m-%d %H:%M"))
        fh.write("- 工作流底模已改为本机已有权重：`%s`（models/checkpoints/）\n" % LOCAL_SDXL)
        fh.write("- 原始引用 `%s` 本机没有，未下载（体积 6GB+，已有等价 SDXL 可替代）\n" % old)
        fh.write("- 原 workflow.json 已备份为 `workflow.json.bak_*`\n")

# 3) 现状核对
CHECKS = [
    ("comfy-lineart-colorization", [
        ("checkpoints", LOCAL_SDXL), ("controlnet", "sai_xl_canny_128lora.safetensors"),
        ("vae", "sdxl_vae.safetensors")]),
    ("comfy-realtime-doodle", [
        ("checkpoints", LOCAL_SDXL), ("loras", "Hyper-SDXL-2steps-lora.safetensors")]),
    ("comfyui-upscaler", [("upscale_models", "4x-UltraSharp.pth")]),
]
log("")
log("=== 权重齐备性核对 ===")
for skill, items in CHECKS:
    for sub, name in items:
        p = os.path.join(MROOT, sub, name)
        ok = os.path.exists(p)
        gb = "%.2f GB" % (os.path.getsize(p) / 1024.0 ** 3) if ok else "-"
        log("  %-28s %-14s %-34s %s %s" % (skill, sub, name, "OK" if ok else "MISSING", gb))

with io.open(r"D:\ai_projects\ComfyUI\_fix_wf_names.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
