#!/usr/bin/env python3
"""走廊法式风情打卡舞 - H3 文生视频+原生音频，竖屏 9:16，672x1152
首帧参考图：C02_PADDED.png（沿用系列人物脸部）
scene: 校园走廊一镜到底，中景平视固定机位，法式慵懒打卡舞
"""
import json, urllib.request, uuid

BASE_URL = "http://127.0.0.1:8188"
REF_IMG = "gemini_ken1/C02_PADDED.png"

PROMPT = (
    "realistic cinematic photography, ultra high detail, bright fresh clean daylight, medium "
    "saturation, natural soft light with warm sunlight through windows casting on the corridor "
    "floor, shallow depth of field, film grain, glossy healthy skin. "
    "The same young East Asian woman as the reference image, same face and body, delicate elegant "
    "features, slim-shaped eyebrows, refined light makeup emphasizing the eye contour, full "
    "glossy lips, porcelain-fair luminous skin. Black long straight hair flowing naturally over "
    "both shoulders. Outfit: a white fitted long-sleeve dress ending at knee level accentuating "
    "the figure curve, paired with white casual sneakers, simple pure with French-elegant "
    "everyday chic. "
    "Setting: a bright school corridor with natural depth perspective, the young woman standing "
    "slightly left of center forming a natural frame between the two corridor walls, sunlight "
    "streaming through windows onto the floor. Fixed camera at eye-level, medium shot showing "
    "her full body and part of the background, single continuous unbroken shot, no camera moves, "
    "no transitions. "
    "Dance, French-style check-in dance (popular dance steps fused with a relaxed French vibe): "
    "she beams a bright sweet confident smile, eyes sparkling lively. Opening: both hands "
    "clasped into fists raised at her chest, gently swaying left-right to the beat. Second: "
    "right arm lifts upward, left arm stretches outward, her body turns and steps forward. "
    "Middle: alternating arms sweep arcs in front of her body while her feet step back and forth. "
    "Ending: both fists return near her cheeks, body sways softly, finishing the smooth dance. "
    "Energetic and graceful, full of vitality. "
    "Background music: a cheerful upbeat energetic EDM with a strong driving beat; music only, "
    "no vocals, no speech. "
    "Vertical 9:16 clip, single continuous shot. "
    "Avoid: anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra "
    "fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, "
    "oversharpened, dull skin, jerky movement"
)

with open("workflows/v1/h3_t2va_audio_api.json", encoding="utf-8") as f:
    wf = json.load(f)

ref_node_id = "100"
while ref_node_id in wf:
    ref_node_id = str(int(ref_node_id) + 1)
wf[ref_node_id] = {"class_type": "LoadImage", "inputs": {"image": REF_IMG}}
wf["6"]["inputs"]["first_frame"] = [ref_node_id, 0]

wf["6"]["inputs"]["prompt"] = PROMPT
wf["6"]["inputs"]["width"] = 672
wf["6"]["inputs"]["height"] = 1152
wf["6"]["inputs"]["length"] = 124
wf["7"]["inputs"]["seed"] = 20261001
wf["10"]["inputs"]["filename_prefix"] = "h3_corridor/corridor"
wf["11"]["inputs"]["filename_prefix"] = "h3_corridor/corridor"

payload = {"prompt": wf, "client_id": str(uuid.uuid4())}
req = urllib.request.Request(f"{BASE_URL}/prompt", data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json"})
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    pid = resp.get("prompt_id")
    print(f"已提交 h3_corridor (672x1152, 124帧≈5.2s, 首帧={REF_IMG}, seed=20261001) -> {pid}")
    with open("workflows/v1/h3_corridor_pid.json", "w", encoding="utf-8") as f:
        json.dump({"prompt_id": pid}, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"提交失败: {e}")