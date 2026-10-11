# -*- coding: utf-8 -*-
"""Shared ComfyUI API helper for prompt-compare generation."""
import json, os, time, uuid, urllib.request, urllib.error

HOST = "http://127.0.0.1:8188"
BASE = r"D:\ai_projects\ComfyUI"
OUT_ROOT = os.path.join(BASE, "output", "prompt_compare")

# ---- 默认出图后端（新增档位只需在此登记）----
DEFAULT_BACKEND = "zimage"
BACKENDS = {
    "zimage": "Z-Image Turbo bf16 — 8 步 / cfg1.0 / 1024px，默认档",
    "flux": "Flux.1 Dev（fp8 或 T8 abliterated GGUF）— 20 步，慢但氛围强",
    "sd15": "SD1.5 / SDXL 底模 — 30 步。本机可用底模：Juggernaut-XL_v9 / RealVisXL_V4.0 / v1-5",
    "qwen21": "Qwen-Image 2.1 GGUF Q4_K_M — 25 步 / cfg3.0，**负面提示词有效**",
}

# ⚠️ 本机设了 HTTP_PROXY，直接 urlopen 访问 127.0.0.1:8188 会被代理劫持成 502。
# 所有本地 HTTP 必须走这个绕代理的 opener。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def today_root(sub=None):
    """规范产物目录：output/YYYY-MM-DD_wb[/sub]。"""
    d = os.path.join(BASE, "output", time.strftime("%Y-%m-%d") + "_wb")
    return os.path.join(d, sub) if sub else d


def comfy_prefix(outdir, name):
    """生成 SaveImage 的 filename_prefix（相对 ComfyUI/output）。

    ⚠️ prefix 不带子目录时，PNG 会掉到 output/ 根目录，与 _run.json 分家。
    这里按 outdir 自动补上子目录，保证产物落在指定目录里。
    """
    try:
        rel = os.path.relpath(outdir, os.path.join(BASE, "output")).replace("\\", "/")
        if rel.startswith(".."):
            rel = ""
    except Exception:
        rel = ""
    rel = rel.strip("/")
    return ("%s/%s" % (rel, name)) if rel else name


def api_get(ep, timeout=30):
    r = _OPENER.open(HOST + ep, timeout=timeout)
    return json.loads(r.read().decode("utf-8", "replace"))


def api_post(ep, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(HOST + ep, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        r = _OPENER.open(req, timeout=timeout)
        return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def server_alive():
    """绕代理探测 ComfyUI 存活。注意 /system_stats 在本机会 500，别用它。"""
    try:
        api_get("/queue", timeout=10)
        return True
    except Exception:
        return False


def submit(prompt_graph, client_id=None):
    """Submit an API-format prompt. Returns (ok, prompt_id_or_error)."""
    cid = client_id or str(uuid.uuid4())
    payload = {"prompt": prompt_graph, "client_id": cid}
    st, resp = api_post("/prompt", payload)
    if st == 200 and isinstance(resp, dict) and resp.get("prompt_id"):
        return True, resp["prompt_id"]
    return False, resp


def wait(prompt_id, timeout=1800, interval=3):
    """Poll /history until the prompt completes. Returns (ok, history_entry)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            h = api_get("/history/" + prompt_id, timeout=30)
        except Exception:
            time.sleep(interval)
            continue
        if prompt_id in h:
            return True, h[prompt_id]
        time.sleep(interval)
    return False, "timeout after %ss" % timeout


def save_meta(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def collect_outputs(hist):
    """Extract saved image filenames from a history entry."""
    files = []
    outs = (hist or {}).get("outputs", {})
    for nid, o in outs.items():
        for key in ("images", "gifs", "videos"):
            for it in (o.get(key) or []):
                if isinstance(it, dict) and it.get("filename"):
                    files.append(it)
    return files
