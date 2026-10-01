#!/usr/bin/env python3
"""v03 首末帧 GLM-4V-Flash 质量检查（串行+重试防 SSL EOF）"""
import base64, json, urllib.request, time, sys

KEY = "f2649c2b4bef47b099bf63a63ce135e4.kpn7Es4gyg3dawQk"
URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
BASE = r"D:/ai_projects/ComfyUI/output/LTX23_ootd/frames_v03"

def ask(img_path, q):
    b64 = base64.b64encode(open(img_path, "rb").read()).decode()
    payload = {
        "model": "glm-4v-flash",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": q},
        ]}],
        "max_tokens": 300,
    }
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    for attempt in range(3):
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
            return r["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  attempt{attempt+1} fail: {type(e).__name__} {str(e)[:80]}")
            time.sleep(3)
    return "FAILED"

print("=== v03 首帧 f_01 ===")
print(ask(f"{BASE}/f_01.png", "这是AI生成视频的一帧。请评估:1)人脸是否自然无崩坏(五官比例、眼睛、嘴);2)画质如何。用简短中文回答。"))
time.sleep(2)
print("=== v03 末帧 f_05 ===")
print(ask(f"{BASE}/f_05.png", "这是AI生成视频接近结尾的一帧。请重点评估:1)人脸是否崩坏(五官比例、眼睛、嘴、皮肤);2)是否有明显的变形或伪影。用简短中文回答。"))
