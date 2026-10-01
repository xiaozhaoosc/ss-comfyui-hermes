# -*- coding: utf-8 -*-
"""Shared ComfyUI API helper for prompt-compare generation."""
import json, os, time, uuid, urllib.request, urllib.error

HOST = "http://127.0.0.1:8188"
BASE = r"D:\ai_projects\ComfyUI"
OUT_ROOT = os.path.join(BASE, "output", "prompt_compare")


def api_get(ep, timeout=30):
    r = urllib.request.urlopen(HOST + ep, timeout=timeout)
    return json.loads(r.read().decode("utf-8", "replace"))


def api_post(ep, payload, timeout=60):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(HOST + ep, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


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
