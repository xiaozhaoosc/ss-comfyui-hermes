#!/usr/bin/env python3
"""走秀视频 - H3 文生视频+原生音频，微信竖屏 9:16，672x1152
首帧参考图：C02_PADDED.png（锚定人物身份），全身造型+走秀动作由提示词生成
"""
import json, urllib.request, uuid, time

BASE_URL = "http://127.0.0.1:8188"
REF_IMG = "gemini_ken1/C02_PADDED.png"

PROMPT = (
    "realistic cinematic photography, ultra high detail, fresh bright clean lighting, cool modern "
    "color palette with soft highlights, shallow depth of field, film grain, glossy healthy skin. "
    "The same young East Asian woman as the reference image, same face and body, delicate elegant "
    "features, slim-shaped eyebrows, light smoky eye makeup, full lips, porcelain-fair luminous skin. "
    "Long straight black hair flowing down her back with silky smooth texture and perfect drape. "
    "She has a statuesque hourglass figure with nine-heads-tall proportion: long slender straight legs, "
    "cinched waist flowing into softly rounded hips, graceful swan-like neck, clear collarbones, "
    "poised upright upper body. A simple gold pendant necklace sits against her collarbone. "
    "Outfit A: a crisp white cropped blazer jacket over a form-fitting black spaghetti-strap slip dress "
    "with a daring high slit up one side revealing the leg curve, black pointed high heels. "
    "A bright modern fashion runway: white glossy floor, soft white lights, blurred modern cityscape "
    "in the background, cool high-key atmosphere, narrow depth of field creating bokeh. "
    "Fixed camera at eye-level, full body centered slightly right of frame following the rule of thirds, "
    "enough background depth behind her to suggest runway depth. She walks confidently down the runway "
    "toward the camera with perfect runway posture: chin up, shoulders relaxed back, hips swaying subtly "
    "with each step, core engaged, arms swinging naturally at her sides or one hand lightly grazing the "
    "dress slit, decisive steady strides on pointed heels. She smiles gently with calm magnetic confidence, "
    "eyes locked forward, occasionally casting a captivating sidelong glance at the camera with a hint "
    "of allure. Slow-mo feel on leg reveal through the slit. "
    "High-energy electronic dance music with a strong punchy beat, deep bass, sharp synthesizer hits, "
    "tempo matching her stride, no vocals — pure driving EDM runway music. "
    "Vertical 9:16 clip, single continuous unbroken shot. "
    "Avoid: anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra fingers, "
    "extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, dull skin, "
    "bent legs, broken heels"
)

with open("workflows/v1/h3_t2va_audio_api.json", encoding="utf-8") as f:
    wf = json.load(f)

# 引用首帧参考图到 MiniMaxH3ImageToVideo
ref_node_id = "100"
while ref_node_id in wf:
    ref_node_id = str(int(ref_node_id) + 1)
wf[ref_node_id] = {"class_type": "LoadImage", "inputs": {"image": REF_IMG}}
wf["6"]["inputs"]["first_frame"] = [ref_node_id, 0]

wf["6"]["inputs"]["prompt"] = PROMPT
wf["6"]["inputs"]["width"] = 672
wf["6"]["inputs"]["height"] = 1152
wf["6"]["inputs"]["length"] = 124
wf["7"]["inputs"]["seed"] = 20260928
wf["10"]["inputs"]["filename_prefix"] = "h3_runway/runway"
wf["11"]["inputs"]["filename_prefix"] = "h3_runway/runway"

payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
req = urllib.request.Request(f"{BASE_URL}/prompt", data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json"})
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    pid = resp.get("prompt_id")
    print(f"已提交 h3_runway (672x1152, 124帧≈5.2s, 首帧={REF_IMG}, seed=20260928) -> {pid}")
    with open("workflows/v1/h3_runway_pid.json", "w", encoding="utf-8") as f:
        json.dump({"prompt_id": pid}, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"提交失败: {e}")