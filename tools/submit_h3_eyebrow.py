#!/usr/bin/env python3
"""单段提交「单边挑眉挑战」到本地 ComfyUI H3（含原生音频），竖屏 672x1152"""
import json, urllib.request, uuid

BASE_URL = "http://127.0.0.1:8188"

PROMPT = (
    "单边挑眉挑战，人物面部特写短视频，单一连续镜头，竖屏。"
    "长焦大特写，聚焦人物眼睛和眉毛区域，平视机位，居中偏上三分法构图，视觉重心在眉眼之间。"
    "妆容精致的年轻女郎，精致眼妆，天生自然弧度的野生眉，眼神专注略带俏皮，表情松弛自信带一丝俏皮。"
    "核心动作：单边挑眉挑战，交替单独挑动左右眉毛，眉毛利落上挑，展示出色的面部肌肉控制力，其中一次挑眉定格给镜头一个自信的眼神。"
    "背景配乐为节奏感强的电子舞曲，有明显鼓点和合成器旋律，动感时尚。"
    "画面下方叠加白色英文字幕：DO YOU LIKE MY 'EYEBROW'?"
    "真实皮肤质感，毛孔毛发细节真实，自然光，高清写实，镜头自然流畅，避免人物变形、手部异常、AI感、卡通感。字幕文字为英文。"
)

with open("workflows/v1/h3_t2va_audio_api.json", encoding="utf-8") as f:
    wf = json.load(f)

wf["6"]["inputs"]["prompt"] = PROMPT
wf["6"]["inputs"]["width"] = 672
wf["6"]["inputs"]["height"] = 1152
wf["6"]["inputs"]["length"] = 124
wf["7"]["inputs"]["seed"] = 20260907
wf["10"]["inputs"]["filename_prefix"] = "h3_eyebrow/seg01"
wf["11"]["inputs"]["filename_prefix"] = "h3_eyebrow/seg01"

payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
req = urllib.request.Request(f"{BASE_URL}/prompt", data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json"})
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    pid = resp.get("prompt_id")
    print(f"已提交 h3_eyebrow (672x1152, 124帧≈5.2s, seed=20260907) -> {pid}")
    with open("workflows/v1/h3_eyebrow_pid.json", "w", encoding="utf-8") as f:
        json.dump({"prompt_id": pid}, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"提交失败: {e}")