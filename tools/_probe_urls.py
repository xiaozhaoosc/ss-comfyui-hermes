import io, urllib.request

urls = [
    ("4x-UltraSharp (upscaler)", "https://huggingface.co/lokCX/4x-UltraSharp/resolve/main/4x-UltraSharp.pth"),
    ("RealESRGAN_x4plus (upscaler)", "https://huggingface.co/lllyasviel/misc/resolve/main/RealESRGAN_x4plus.pth"),
    ("Hyper-SDXL-1step-lora (doodle)", "https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-SDXL-1step-lora.safetensors"),
    ("SDXL Canny ControlLoRA r128 (lineart)", "https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank128/control-lora-canny-rank128.safetensors"),
    ("Z-Image Turbo DiT", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors"),
    ("Z-Image Turbo TE qwen_3_4b", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors"),
    ("Z-Image Turbo VAE ae", "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors"),
    ("Flux2 Klein 9B fp8 (guess1)", "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux2-klein-9b-fp8.safetensors"),
    ("Flux2 Klein 9B bf16 (guess2)", "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux2-klein-9b.safetensors"),
]

out = []
for label, u in urls:
    try:
        req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "python"})
        with urllib.request.urlopen(req, timeout=40) as r:
            cl = r.headers.get("Content-Length")
            gb = ("%.2f GB" % (int(cl) / 1024.0 ** 3)) if cl else "?"
            out.append("OK   %-42s %-12s status=%s final=%s" % (label, gb, r.status, r.geturl()[:110]))
    except Exception as e:
        out.append("FAIL %-42s %s: %s" % (label, type(e).__name__, str(e)[:140]))

with io.open(r"D:\ai_projects\ComfyUI\_url_probe.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
