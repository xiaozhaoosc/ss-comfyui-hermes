import os, io

MROOT = r"D:\ai_projects\ComfyUI\models"
targets = [
    ("diffusion_models", "z_image_turbo_bf16.safetensors", 12309866400),
    ("text_encoders", "qwen_3_4b.safetensors", 8042776320),
    ("vae", "ae.safetensors", 335052800),
]
out = []
for sub, name, want in targets:
    p = os.path.join(MROOT, sub, name)
    part = p + ".part"
    if os.path.exists(p):
        got = os.path.getsize(p)
        out.append("%s/%s: %.2f GB / want %.2f GB -> %s" % (
            sub, name, got / 1024.0 ** 3, want / 1024.0 ** 3,
            "COMPLETE" if got == want else "INCOMPLETE"))
    else:
        out.append("%s/%s: (missing)" % (sub, name))
    if os.path.exists(part):
        out.append("   .part exists %.2f GB" % (os.path.getsize(part) / 1024.0 ** 3))

with io.open(r"D:\ai_projects\ComfyUI\_chk_dl.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
