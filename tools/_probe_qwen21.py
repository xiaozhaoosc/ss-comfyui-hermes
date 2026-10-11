"""探测 Qwen-Image 2.1 与 Z-Image LoRA 在本机的可用性。绕代理。"""
import io, json, urllib.request

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = "http://127.0.0.1:8188"
out = []


def get(path, timeout=20):
    with OPENER.open(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def opts(node, field):
    try:
        d = get("/object_info/" + node)
        v = d[node]["input"]["required"][field][0]
        return v if isinstance(v, list) else list(v)
    except Exception as e:
        return ["<ERR %s>" % str(e)[:60]]


out.append("=== 服务 ===")
try:
    get("/queue")
    out.append("  ComfyUI alive")
except Exception as e:
    out.append("  DOWN: %s" % str(e)[:80])

out.append("")
out.append("=== Qwen-Image 2.1 需要的件 ===")
unets = opts("UnetLoaderGGUF", "unet_name") if True else []
try:
    unets = opts("UnetLoaderGGUF", "unet_name")
except Exception:
    unets = []
out.append("  UnetLoaderGGUF 里 qwen: %s" % [x for x in unets if "qwen" in x.lower()])
out.append("  (GGUF unet 共 %d 项: %s)" % (len(unets), unets[:8]))

try:
    unets2 = opts("UNETLoader", "unet_name")
    out.append("  UNETLoader 里 qwen: %s" % [x for x in unets2 if "qwen" in x.lower()])
except Exception as e:
    out.append("  UNETLoader err")

clips = opts("CLIPLoader", "clip_name")
out.append("  CLIPLoader 里 qwen/vl: %s" % [x for x in clips if "qwen" in x.lower() or "vl" in x.lower()])
out.append("  (全部 %d 项: %s)" % (len(clips), clips[:20]))

vaes = opts("VAELoader", "vae_name")
out.append("  VAELoader 里 qwen: %s" % [x for x in vaes if "qwen" in x.lower()])

out.append("")
out.append("=== Z-Image / 通用 LoRA ===")
loras = opts("LoraLoader", "lora_name")
out.append("  LoRA 总数 %d" % len(loras))
out.append("  含 zimg/z_image/zimage: %s" % [x for x in loras if any(k in x.lower() for k in ("zimg", "z_image", "zimage"))])
out.append("  含 skin/texture/detail: %s" % [x for x in loras if any(k in x.lower() for k in ("skin", "texture", "detail", "pore"))])

out.append("")
out.append("=== 采样辅助节点 ===")
for n in ["ModelSamplingAuraFlow", "ModelSamplingSD3", "LoraLoaderModelOnly"]:
    try:
        get("/object_info/" + n)
        out.append("  %-24s OK" % n)
    except Exception:
        out.append("  %-24s MISSING" % n)

with io.open(r"D:\ai_projects\ComfyUI\_probe_qwen21.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
