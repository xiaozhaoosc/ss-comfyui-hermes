"""Z-Image Turbo 实测出图：提交工作流 -> 轮询 -> 校验产物。
必须绕代理。"""
import io, json, time, uuid, urllib.request, urllib.error, os, glob

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
BASE = "http://127.0.0.1:8188"
OUT = r"D:\ai_projects\ComfyUI\_zimage_test.txt"
LOG = []


def log(m):
    LOG.append(m)
    try:
        with io.open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(LOG))
    except Exception:
        pass


PROMPT = ("a photorealistic portrait of a young woman with dark hair, standing in a "
          "bamboo forest at dawn, soft rim light, shallow depth of field, 85mm lens, "
          "natural skin texture, cinematic color grading, highly detailed")

GRAPH = {
    "1": {"class_type": "UNETLoader",
          "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader",
          "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "qwen_image"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["2", 0]}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
    "6": {"class_type": "EmptySD3LatentImage",
          "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
    "7": {"class_type": "KSampler",
          "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                     "latent_image": ["6", 0], "seed": 20261010, "steps": 8, "cfg": 1.0,
                     "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    "9": {"class_type": "SaveImage",
          "inputs": {"images": ["8", 0], "filename_prefix": "zimage_test"}},
}

cid = str(uuid.uuid4())
body = json.dumps({"prompt": GRAPH, "client_id": cid}).encode("utf-8")
req = urllib.request.Request(BASE + "/prompt", data=body,
                             headers={"Content-Type": "application/json"})
log("提交工作流 ...")
t0 = time.time()
try:
    with OPENER.open(req, timeout=120) as r:
        res = json.loads(r.read().decode("utf-8", "replace"))
except urllib.error.HTTPError as e:
    detail = e.read().decode("utf-8", "replace")
    log("提交失败 HTTP %s" % e.code)
    log(detail[:3000])
    raise SystemExit(0)
except Exception as e:
    log("提交异常 %s: %s" % (type(e).__name__, str(e)[:300]))
    raise SystemExit(0)

pid = res.get("prompt_id")
log("已提交 prompt_id=%s" % pid)
log("node_errors=%s" % json.dumps(res.get("node_errors", {}), ensure_ascii=False)[:1500])

deadline = time.time() + 3600
last = 0
while time.time() < deadline:
    time.sleep(10)
    try:
        with OPENER.open(BASE + "/history/" + pid, timeout=30) as r:
            h = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        log("  轮询异常 %s" % str(e)[:120])
        continue
    if pid in h:
        rec = h[pid]
        st = rec.get("status", {})
        log("完成 status=%s 用时 %.1f 分钟" % (st.get("status_str"), (time.time() - t0) / 60.0))
        outs = rec.get("outputs", {})
        for node_id, o in outs.items():
            for img in o.get("images", []):
                log("  产物: %s (subfolder=%s type=%s)" % (
                    img.get("filename"), img.get("subfolder"), img.get("type")))
        msgs = st.get("messages", [])
        for m in msgs[-8:]:
            log("  msg: %s" % json.dumps(m, ensure_ascii=False)[:400])
        break
    if time.time() - last > 60:
        last = time.time()
        try:
            with OPENER.open(BASE + "/queue", timeout=20) as r:
                q = json.loads(r.read().decode("utf-8", "replace"))
            log("  仍在跑 ... running=%d pending=%d (%.1f min)" % (
                len(q.get("queue_running", [])), len(q.get("queue_pending", [])),
                (time.time() - t0) / 60.0))
        except Exception:
            pass
else:
    log("超时 60 分钟未完成")

# 找产物
log("")
log("=== 产物文件 ===")
cands = []
for pat in [r"D:\ai_projects\ComfyUI\output\zimage_test*.png",
            r"D:\ai_projects\ComfyUI\output\**\zimage_test*.png"]:
    cands += glob.glob(pat, recursive=True)
for p in sorted(set(cands)):
    log("  %s  %.2f MB  %s" % (p, os.path.getsize(p) / 1024.0 ** 2,
                               time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p)))))
if not cands:
    log("  (未找到产物)")
log("总耗时 %.1f 分钟" % ((time.time() - t0) / 60.0))
print("ok")
