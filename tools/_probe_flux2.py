import io, urllib.request

urls = [
    ("flux-2-klein-9b-fp8 (BFL, gated?)", "https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/main/flux-2-klein-9b-fp8.safetensors"),
    ("qwen_3_8b_fp8mixed TE", "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors"),
    ("flux2-vae", "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors"),
    ("ip-adapter-faceid-plusv2_sdxl", "https://huggingface.co/h94/IP-Adapter-FaceID/resolve/main/ip-adapter-faceid-plusv2_sdxl.bin"),
]
out = []
for label, u in urls:
    try:
        req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "python"})
        with urllib.request.urlopen(req, timeout=45) as r:
            cl = r.headers.get("Content-Length")
            gb = ("%.2f GB" % (int(cl) / 1024.0 ** 3)) if cl else "?"
            out.append("OK   %-34s %-10s status=%s" % (label, gb, r.status))
    except Exception as e:
        out.append("FAIL %-34s %s: %s" % (label, type(e).__name__, str(e)[:160]))

with io.open(r"D:\ai_projects\ComfyUI\_probe_flux2.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
