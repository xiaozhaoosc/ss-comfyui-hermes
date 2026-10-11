# -*- coding: utf-8 -*-
"""权重字节校验器：远端真实大小(HEAD) + safetensors 头解析。

可被其他脚本 import 复用：verify_one(url, relpath) -> (size_ok, hdr_ok, info)。
直接运行：python tools/_verify_weights.py  （校验 JOBS 列表里的全部文件，写 _verify_weights.txt）

说明：verify_one 的 size_ok 取「本地大小 == 远端 HEAD 的 Content-Length」，
hdr_ok 取「safetensors 头部可解析且含 tensor」。本机代理走环境变量 HTTP_PROXY，
裸 urllib 已自动沿用，无需硬编码端口。
"""
import os, io, json, struct, urllib.request

MROOT = r"D:\ai_projects\ComfyUI\models"

JOBS = [
    ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
     r"diffusion_models\z_image_turbo_bf16.safetensors"),
    ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
     r"text_encoders\qwen_3_4b.safetensors"),
    ("https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
     r"vae\ae.safetensors"),
    # 动漫底模（SD1.5 动漫，约 3.95GiB）。URL 已用 HEAD 实测 200 + CL=4244124028。
    ("https://hf-mirror.com/gsdf/Counterfeit-V3.0/resolve/main/Counterfeit-V3.0_fp16.safetensors",
     r"checkpoints\Counterfeit-V3.0_fp16.safetensors"),
]


def verify_one(url, relpath, mroot=MROOT):
    """校验单个权重：返回 (size_ok, hdr_ok, info_str)。

    size_ok: 本地大小 == 远端 HEAD 的 Content-Length（None 表示无法取远端大小）；
    hdr_ok : safetensors 头部可解析且含 tensor。
    """
    p = os.path.join(mroot, relpath)
    name = os.path.basename(p)
    if not os.path.exists(p):
        return (False, False, "%s : MISSING" % name)
    local = os.path.getsize(p)
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "python"})
        with urllib.request.urlopen(req, timeout=45) as r:
            remote = int(r.headers.get("Content-Length", 0))
    except Exception as e:
        remote = -1
        return (False, False, "%s : HEAD err %s" % (name, str(e)[:80]))
    size_ok = (remote == local) if remote > 0 else None
    hdr_ok = False
    hdr_info = ""
    try:
        with open(p, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            if 0 < n < 100 * 1024 * 1024:
                raw = f.read(n)
                meta = json.loads(raw.decode("utf-8"))
                keys = [k for k in meta if k != "__metadata__"]
                hdr_ok = len(keys) > 0
                hdr_info = "%d tensors" % len(keys)
                if "__metadata__" in meta:
                    hdr_info += ", fmt=%s" % str(meta["__metadata__"].get("format", "?"))[:20]
            else:
                hdr_info = "bad header len %d" % n
    except Exception as e:
        hdr_info = "ERR %s" % str(e)[:60]
    status = "OK" if size_ok else ("MISMATCH" if size_ok is False else "?")
    hstat = "OK" if hdr_ok else "FAIL"
    info = "%-38s local=%.2fGB remote=%.2fGB size=%s header=%s (%s)" % (
        name, local / 1024.0 ** 3, (remote / 1024.0 ** 3 if remote > 0 else -1),
        status, hstat, hdr_info)
    return (size_ok, hdr_ok, info)


def main():
    out = []
    for url, rel in JOBS:
        _, _, info = verify_one(url, rel)
        out.append(info)
    with io.open(r"D:\ai_projects\ComfyUI\_verify_weights.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("ok")


if __name__ == "__main__":
    main()
