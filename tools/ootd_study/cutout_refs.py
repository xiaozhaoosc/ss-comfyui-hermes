#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键将 5 张 OOTD 去手机参考图提取为透明背景小人贴纸 (RGBA)。"""
import json
import os
import sys
import time
import urllib.request
import uuid

ROOT = r"D:\ai_projects\ComfyUI"
OUT = os.path.join(ROOT, "output", "2026-10-03", "ootd_multilook_nophone")
CUTOUT_DIR = os.path.join(OUT, "swap_cutout")
os.makedirs(CUTOUT_DIR, exist_ok=True)

# 构造一次性处理 5 张参考图的图层工作流
wf = {
    "10": {
        "class_type": "LoadBackgroundRemovalModel",
        "inputs": {"bg_removal_name": "BiRefNet-general.safetensors"}
    }
}

for k in range(1, 6):
    n_load = str(10 + k)
    n_rem = str(20 + k)
    n_join = str(30 + k)
    n_save = str(40 + k)
    wf[n_load] = {
        "class_type": "LoadImage",
        "inputs": {"image": f"ootd_multilook_nophone_look{k}.png"}
    }
    wf[n_rem] = {
        "class_type": "RemoveBackground",
        "inputs": {"bg_removal_model": ["10", 0], "image": [n_load, 0]}
    }
    wf[n_join] = {
        "class_type": "JoinImageWithAlpha",
        "inputs": {"image": [n_load, 0], "alpha": [n_rem, 0]}
    }
    wf[n_save] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": [n_join, 0],
            "filename_prefix": f"2026-10-03/ootd_multilook_nophone/swap_cutout/g{k}"
        }
    }

req = urllib.request.Request(
    "http://127.0.0.1:8188/prompt",
    data=json.dumps({"prompt": wf, "client_id": str(uuid.uuid4())}).encode(),
    headers={"Content-Type": "application/json"}
)
res = json.loads(urllib.request.urlopen(req, timeout=30).read())
pid = res.get("prompt_id")
print(f"[cutout] 已提交批处理抠像 pid={pid}")

# 等待完成
t0 = time.time()
while time.time() - t0 < 60:
    time.sleep(2)
    h_url = f"http://127.0.0.1:8188/history/{pid}"
    try:
        h = json.loads(urllib.request.urlopen(h_url, timeout=10).read())
        if pid in h:
            print(f"[cutout] 抠像完成，耗时={round(time.time() - t0, 1)}s")
            break
    except Exception as e:
        pass

# 检查产物
files = [f for f in os.listdir(CUTOUT_DIR) if f.endswith(".png")]
print(f"[cutout] 产物列表 ({len(files)} 张): {sorted(files)}")
