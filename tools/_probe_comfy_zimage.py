"""探测 ComfyUI 是否可用 + 是否支持 Z-Image 工作流所需的节点/权重。
必须绕代理（本机 HTTP_PROXY 会劫持 127.0.0.1:8188 返回 502）。"""
import io, json, urllib.request

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = "http://127.0.0.1:8188"
out = []


def get(path, timeout=15):
    with OPENER.open(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


out.append("=== 1) 服务存活 ===")
alive = False
for path in ["/queue", "/object_info/KSampler"]:
    try:
        d = get(path)
        out.append("  %s -> OK" % path)
        alive = True
    except Exception as e:
        out.append("  %s -> FAIL %s: %s" % (path, type(e).__name__, str(e)[:100]))
out.append("  alive=%s" % alive)

if alive:
    out.append("")
    out.append("=== 2) 关键节点是否存在 ===")
    for node in ["UNETLoader", "CLIPLoader", "VAELoader", "KSampler", "CLIPTextEncode",
                 "VAEDecode", "SaveImage", "EmptySD3LatentImage", "EmptyLatentImage",
                 "ModelSamplingAuraFlow", "ModelSamplingSD3"]:
        try:
            get("/object_info/" + node)
            out.append("  %-26s OK" % node)
        except Exception as e:
            out.append("  %-26s MISSING (%s)" % (node, str(e)[:50]))

    out.append("")
    out.append("=== 3) 权重是否被 ComfyUI 看见 ===")
    try:
        d = get("/object_info/UNETLoader")
        opts = d["UNETLoader"]["input"]["required"]["unet_name"][0]
        hits = [x for x in opts if "z_image" in x.lower() or "z-image" in x.lower()]
        out.append("  UNETLoader 里 z_image 相关: %s" % (hits if hits else "NONE"))
        out.append("  (unet 列表共 %d 项，样本: %s)" % (len(opts), opts[:5]))
    except Exception as e:
        out.append("  UNETLoader err %s" % str(e)[:90])
    try:
        d = get("/object_info/CLIPLoader")
        t = d["CLIPLoader"]["input"]["required"]["type"][0]
        out.append("  CLIPLoader type 可选值: %s" % t)
        try:
            opts = d["CLIPLoader"]["input"]["required"]["clip_name"][0]
            out.append("  CLIPLoader 里 qwen_3_4b: %s" % [x for x in opts if "qwen_3_4b" in x.lower()])
        except Exception:
            pass
    except Exception as e:
        out.append("  CLIPLoader err %s" % str(e)[:90])
    try:
        d = get("/object_info/VAELoader")
        opts = d["VAELoader"]["input"]["required"]["vae_name"][0]
        out.append("  VAELoader 里 ae.safetensors: %s" % [x for x in opts if x.lower().startswith("ae.")])
    except Exception as e:
        out.append("  VAELoader err %s" % str(e)[:90])

with io.open(r"D:\ai_projects\ComfyUI\_probe_comfy_zimage.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("ok")
