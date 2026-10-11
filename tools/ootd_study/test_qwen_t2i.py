#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 Qwen-Image-2.1 T2I 工作流生成单张参考图。"""
import json
import os
import sys
import time
import urllib.request
import uuid

ROOT = r"D:\ai_projects\ComfyUI"
WF_PATH = os.path.join(ROOT, "workflows", "v4", "qwen_image_2_1_t2i_v4.json")

with open(WF_PATH, "r", encoding="utf-8") as f:
    wf = json.load(f)

# 设置 9:16 竖屏全身图
wf["7"]["inputs"]["width"] = 768
wf["7"]["inputs"]["height"] = 1344

# 正向提示词：全新模特 + Look 1 燕麦色大衣
prompt = (
    "masterpiece, ultra-detailed, high fashion photography, "
    "a gorgeous 22yo French-Asian fashion model with shoulder-length wavy dark brown hair, "
    "natural gentle smile, frontal full body view, standing upright in clean modern minimalist studio, "
    "wearing an elegant oversized oatmeal cashmere wool coat, cream turtleneck, tailored trousers, "
    "hands relaxed at sides, empty hands, no smartphone, natural lighting, perfect anatomy"
)
wf["5"]["inputs"]["text"] = prompt
wf["6"]["inputs"]["text"] = (
    "worst quality, low quality, smartphone, cell phone, mobile phone, holding phone, selfie stick, "
    "deformed hands, extra fingers, bad anatomy, blurry"
)
wf["8"]["inputs"]["steps"] = 16
wf["8"]["inputs"]["seed"] = 42
wf["10"]["inputs"]["filename_prefix"] = "2026-10-04/test_look1"

req = urllib.request.Request(
    "http://127.0.0.1:8188/prompt",
    data=json.dumps({"prompt": wf, "client_id": str(uuid.uuid4())}).encode(),
    headers={"Content-Type": "application/json"}
)
res = json.loads(urllib.request.urlopen(req, timeout=10).read())
pid = res.get("prompt_id")
print(f"[test_qwen] 已提交测试生成 pid={pid}")

t0 = time.time()
while time.time() - t0 < 120:
    time.sleep(3)
    try:
        h = json.loads(urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=5).read())
        if pid in h:
            print(f"[test_qwen] 生成完毕！耗时={round(time.time() - t0, 1)}s")
            outputs = h[pid].get("outputs", {})
            print("[test_qwen] 输出信息:", outputs)
            break
    except Exception:
        pass
