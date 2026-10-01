# 超写实微表情演绎 · 9:16 竖屏 10 秒

**任务**：AI 微表情演绎（0-10s 五段节拍）
**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_micro_expression.py`
**输出**：`D:\ai_projects\ComfyUI\output\micro_expr\`
**首帧参考**：`gemini_ken1/C02_PADDED.png`

## 采样参数（组2 锐化版）
- Steps 34 / Sampler euler / Scheduler simple / CFG 1.0
- shift_video = 14.0, shift_audio = 3.5（4:1）
- Resolution 544×960 @ 24fps
- 每段 53 帧（≈2.2s），5 段 ≈ 10-11s 总长
- 首段首帧 C02_PADDED，后续段用前段末帧（链式衔接）

## 风格 / 人物 / 镜头 共用前缀

### STYLE
```
hyper-realistic cinematic portrait photography, 4K HDR, extreme macro detail,
authentic skin texture with subtle pores and natural fine lines, realistic eyeball
refraction with environment reflections, true tear-film physics, individual hair
strands visible, film-grade portrait cinematography.
```

### CHARACTER
```
The same young East Asian woman as the reference image, 20 years old, a slender
soft oval face, fair translucent porcelain skin with subtle natural pores. Long
black hair naturally draping on both sides of her face, the top combed back
revealing her full forehead. Large pale grey-blue eyes with crisp iris texture,
realistic moist eyeballs reflecting the environment, long lashes, soft pink
eyeshadow, fine long slightly upturned black eyeliner. Naturally soft eyebrows,
delicate slim nose bridge, small refined nose tip, plump pale-pink glassy
glossy lips. Pure and alluring K-beauty clean-girl vibe.
```

### CAMERA
```
Fixed camera, extreme close-up frontal facial portrait at 85-100mm lens equivalent,
her face nearly filling the frame, eyes as the absolute visual center, shallow
depth of field with creamy bokeh. Background: a soft grey-blue interior,
completely blurred out. Lighting: soft frontal beauty light plus window diffused
natural light, face evenly lit, eyes catching natural rectangular catchlights,
delicate highlights on the nose bridge and lips. Only an extremely subtle natural
push-in over the whole clip, no pans, no noticeable camera movement.
```

### NEGATIVE
```
anime, cartoon, 3D render, illustration, distorted face, asymmetrical eyes,
deformed hands, extra fingers, blurry, oversharpened, watermark, text overlay,
doll-like skin, plastic texture, exaggerated expression, wide-angle distortion,
heavy tears, overacting, jerky head movement
```

## 分段动作

### SEG01 · 0-2s 惊讶
```
she looks directly into the camera, her eyes widen slightly, lips part just a
touch, as if she has just heard something unexpected — a subtle startled,
caught-off-guard feeling. Her breath is calm and natural, eyeballs drift very
slightly, she blinks exactly once, head stays nearly still. Micro-expression only,
no overacting.
```

### SEG02 · 2-4s 失落
```
she slowly lowers her gaze, eyes drifting downward away from the camera, head
tipping down just barely with the gaze. Her lips slowly press closed, mood sinking
from startled into hurt and wounded. Her brows tighten imperceptibly inward, the
corner of her mouth shifts almost invisibly. Micro-expression, restrained,
absolutely no exaggerated frowning.
```

### SEG03 · 4-6s 眼眶湿润
```
she slowly lifts her eyes back to the camera, brows knitting the faintest degree,
wounded look deepening. Her eyes begin to glisten — a fine film of moisture
building on the eyeballs, as if fighting back tears. Subtle eyelid tremble, pupils
drifting slightly, her breath shallow and natural. Tears NOT yet falling, just the
pre-tear sheen.
```

### SEG04 · 6-8s 手托下巴
```
a hand (someone else's, elegant knuckles, natural skin tone) enters slowly from
the bottom-right of the frame and gently cradles her chin and right cheek, the
motion continuous and smooth, no sudden grab. She does not pull away, keeps
watching the camera, brows knit a micro-degree deeper, her gaze now visibly
fragile.
```

### SEG05 · 8-10s 忍泪定格
```
the hand keeps cradling her chin. Her eye rims grow visibly pink and moist, the
pale grey-blue irises forming delicate tear-light reflections, a tiny bead of
tears gathering under the lower lashes — but NOT freely crying. She tilts her eyes
up slightly meeting the camera directly, lips pressed tight — the held-back sob
look: hurt, vulnerable, restrained. Hold the pose.
```

## 中文精简提示词（~50 字）
> 她先是微愣，继而失落地垂下眼帘，再度抬眸时已泪光盈盈；一只手温柔托住她的下巴，她倔强地忍住眼泪，浅灰蓝色眼底星光碎成一片。
