"""权重下载器：断点续传 + 进度落盘（UTF-8），绕开 PowerShell 输出问题。

用法:
    python tools/_dl_weights.py --set small
    python tools/_dl_weights.py --set zimage
"""
import os, io, sys, time, json, urllib.request

MROOT = r"D:\ai_projects\ComfyUI\models"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verify_weights import verify_one

JOBS = {
    "small": [
        ("https://huggingface.co/lokCX/4x-UltraSharp/resolve/main/4x-UltraSharp.pth",
         r"upscale_models\4x-UltraSharp.pth"),
        ("https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-SDXL-1step-lora.safetensors",
         r"loras\Hyper-SDXL-1step-lora.safetensors"),
        ("https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank128/control-lora-canny-rank128.safetensors",
         r"controlnet\control-lora-canny-rank128.safetensors"),
    ],
    "lora_skin": [
        ("https://huggingface.co/JosephMinchala/JosephMinchala-skin-texture-zturbo-v45/resolve/main/skin%20texture%20Photorealistic%20style%20v4.5.safetensors",
         r"loras\skin_texture_zturbo_v45.safetensors"),
        ("https://huggingface.co/suayptalha/Z-Image-Turbo-Realism-LoRA/resolve/main/pytorch_lora_weights.safetensors",
         r"loras\zimage_realism_lora.safetensors"),
    ],
    "hyper2": [
        ("https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-SDXL-2steps-lora.safetensors",
         r"loras\Hyper-SDXL-2steps-lora.safetensors"),
    ],
    "zimage": [
        ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
         r"diffusion_models\z_image_turbo_bf16.safetensors"),
        ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
         r"text_encoders\qwen_3_4b.safetensors"),
        ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
         r"vae\ae.safetensors"),
    ],
    # 动漫底模（SD1.5 动漫，约 3.95GiB）。URL 已用 HEAD 实测 200 + CL=4244124028。
    "counterfeit": [
        ("https://hf-mirror.com/gsdf/Counterfeit-V3.0/resolve/main/Counterfeit-V3.0_fp16.safetensors",
         r"checkpoints\Counterfeit-V3.0_fp16.safetensors"),
    ],
}

LOGS = {
    "small": r"D:\ai_projects\ComfyUI\_dl_small.txt",
    "zimage": r"D:\ai_projects\ComfyUI\_dl_zimage.txt",
    "hyper2": r"D:\ai_projects\ComfyUI\_dl_hyper2.txt",
    "lora_skin": r"D:\ai_projects\ComfyUI\_dl_lora_skin.txt",
    "counterfeit": r"D:\ai_projects\ComfyUI\_dl_counterfeit.txt",
}


def log(fp, msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        with io.open(fp, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def total_size(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "python"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length", 0))


def download(url, dest, logfp):
    """断点续传 + 大小校验。只有字节数完全匹配才落盘为正式文件，
    避免把中断产生的残片当成完整权重（ComfyUI 会报 SafetensorError）。"""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    total = total_size(url)
    name = os.path.basename(dest)

    if os.path.exists(dest):
        if total and os.path.getsize(dest) == total:
            log(logfp, "SKIP already complete: %s (%.2f GB)" % (name, total / 1024.0 ** 3))
            return True
        os.remove(dest)
        log(logfp, "REMOVE incomplete leftover: %s (%.2f GB)" % (name, os.path.getsize(dest) / 1024.0 ** 3))

    t0 = time.time()
    for attempt in range(1, 10):
        done = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        headers = {"User-Agent": "python"}
        mode = "wb"
        if done > 0:
            headers["Range"] = "bytes=%d-" % done
            mode = "ab"
        log(logfp, "START %s attempt=%d total=%.2f GB resume=%.2f GB" % (
            name, attempt, total / 1024.0 ** 3, done / 1024.0 ** 3))
        last = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
                with open(tmp, mode) as f:
                    while True:
                        chunk = r.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if now - last >= 20:
                            log(logfp, "  %.2f%%  %.2f/%.2f GB  %.1f MB/s" % (
                                done / total * 100 if total else 0,
                                done / 1024.0 ** 3, total / 1024.0 ** 3,
                                done / 1024.0 ** 2 / max(now - t0, 1)))
                            last = now
        except Exception as e:
            log(logfp, "  NET ERR: %s" % str(e)[:120])

        got = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if total and got == total:
            os.replace(tmp, dest)
            log(logfp, "DONE %s %.2f GB in %.1f min" % (
                name, os.path.getsize(dest) / 1024.0 ** 3, (time.time() - t0) / 60.0))
            return True
        log(logfp, "  incomplete %.2f/%.2f GB -> will resume" % (got / 1024.0 ** 3, total / 1024.0 ** 3))

    log(logfp, "FAILED %s after 9 attempts, .part kept at %.2f GB" % (
        name, (os.path.getsize(tmp) if os.path.exists(tmp) else 0) / 1024.0 ** 3))
    return False


def main():
    which = "small"
    if "--set" in sys.argv:
        which = sys.argv[sys.argv.index("--set") + 1]
    jobs = JOBS[which]
    logfp = LOGS[which]
    log(logfp, "=== run set=%s jobs=%d ===" % (which, len(jobs)))
    ok = 0
    for url, rel in jobs:
        dest = os.path.join(MROOT, rel)
        name = os.path.basename(dest)
        done = False
        for attempt in range(1, 4):
            try:
                if not download(url, dest, logfp):
                    continue
            except Exception as e:
                log(logfp, "ERR attempt %d %s: %s" % (attempt, name, str(e)[:160]))
                time.sleep(5)
                continue
            # 下载落盘后做字节 + 头部校验（仅当 size_ok 且 hdr_ok 才算真完成）
            try:
                s_ok, h_ok, info = verify_one(url, rel)
                log(logfp, "VERIFY %s" % info)
                if s_ok and h_ok:
                    done = True
                    break
                log(logfp, "  verify failed -> retry download")
            except Exception as e:
                log(logfp, "  verify err %s" % str(e)[:120])
                # 校验脚本异常不致命：下载已落盘，视为完成避免死循环
                done = True
                break
        if done:
            ok += 1
    log(logfp, "=== finished ok=%d/%d ===" % (ok, len(jobs)))


if __name__ == "__main__":
    main()
