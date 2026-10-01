# 单边挑眉挑战展示 · 9:16 竖屏 11 秒

**任务**：人物微表情挑战（单边挑眉卡点展示）
**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_eyebrow_seg.py`
**输出目录**：`D:\ai_projects\ComfyUI\output\h3_eyebrow_seg\`
**成片**：`eyebrow_challenge_9x16_5seg.mp4`
**参考人物**：无（纯文生视频定义人物，无首帧参考图）

## 采样参数（组2 锐化版）

| 项 | 值 |
|---|---|
| Steps | 34 |
| Sampler / Scheduler | euler / simple（flow matching 固定配置） |
| CFG | 1.0（H3 无 CFG，负面复用正面） |
| shift_video / shift_audio | 14.0 / 3.5（4:1） |
| Resolution | 544×960 @ 24fps × 53 帧 ≈ 2.2s/段 |
| 段数 | 5 段链式（首段文生视频；后续段首帧=上段末帧） |
| 首段 seed | 20260911+i（i=段序） |
| 总时长 | ≈ 11s |
| 末段 | 叠加英文字幕 `DO YOU LIKE MY 'EYEBROW'?` |

## 风格 / 人物 / 镜头 共用前缀

### STYLE
```
hyper-realistic cinematic portrait photography, 4K HDR, extreme macro detail,
authentic skin texture with subtle pores and natural fine lines, realistic eyeball
refraction, natural eyebrow hairs visible individually, film-grade portrait
cinematography.
```

### CHARACTER
```
A young East Asian woman in her early 20s, a slender soft oval face, fair translucent
skin with subtle natural pores. Long black hair softly framing her face, combed back
revealing her forehead. Large peach-brown eyes with crisp iris texture, moist
eyeballs, long black lashes, delicate slightly smoky eyeshadow and fine upward
eyeliner. Fresh trendy NATURAL 'wild-brow' eyebrows with an elegant soft arc and
visible individual hair strokes, the signature focus of this clip. Soft pink glassy
glossy lips. Playful confident clean-girl vibe.
```

### CAMERA
```
Fixed camera, extreme close-up frontal facial portrait at 85-100mm lens equivalent,
her eyes and eyebrows near the upper-center third of the frame as the absolute focus,
eyes the visual center, shallow depth of field with creamy bokeh. Background: a soft
grey-blue interior, completely blurred out. Lighting: soft frontal beauty light, face
evenly lit, eyes catching natural rectangular catchlights, subtle highlight on the
nose bridge and brows. Only an extremely subtle natural push-in, no pans.
```

### NEGATIVE（不含字幕段时用）
```
anime, cartoon, 3D render, illustration, distorted face, asymmetrical eyes,
deformed hands, extra fingers, blurry, oversharpened, glitch, doll-like skin,
plastic texture, exaggerated wide-eyed overacting, heavy frown, jerky head movement,
both brows raising at once, watermark, text overlay, subtitles
```

## 分段动作（5 段 × 53 帧）

### SEG01 · 0-2s 右眉单挑
```
she looks directly into the camera with relaxed neutral expression, then smoothly cocks
only her RIGHT eyebrow up once — right brow lifts clean and single-sided, the left brow
stays still. Her gaze is focused and a touch playful, the corner of her mouth twitches
subtly up. A confident single-sided brow-raise challenge. Micro-expression only, no
overacting. Avoid: <NEGATIVE without text>`.
```

### SEG02 · 2-4s 左眉单挑
```
she lowers the right brow back to neutral, then in the same playful style cocks only her
LEFT eyebrow up once — left brow lifts clean and single-sided, right brow stays perfectly
still. Eyes still pinned to the camera with a teasing sparkle, a faint sly smile.
Single-sided brow-raise challenge. Micro-expression, restrained. Avoid: <NEGATIVE>.
```

### SEG03 · 4-6s 左右交替
```
she does a quick alternating eyebrow challenge — right brow lifts, left brow lifts, right
lifts again, quickly twitching each side in rhythm, both brows never rising together.
A lively playful beat to the movement, slight amused smile, eyes sparkling at the camera.
Micro-expression challenge, smooth not jerky. Avoid: <NEGATIVE>.
```

### SEG04 · 6-8s 俏皮眨眼
```
the brows settle back to natural. She gives the camera one playful deliberate wink with
her right eye while both brows lift a tiny encouraging degree, then returns to a calm
confident look, lips curving in an assured smile. Self-possessed and a little coy.
Micro-expression only. Avoid: <NEGATIVE>.
```

### SEG05 · 8-10s 定格+字幕
```
she holds a final confident single-sided brow-raise on her right eyebrow, locking eyes
straight into the camera with a poised slightly smug expression, face relaxed, brows
held. Below the frame, bold clean white English text is overlaid reading
'DO YOU LIKE MY \'EYEBROW\'?'. Hold the pose and the text steady. Micro-expression,
restrained. Avoid: <NEGATIVE with text / 去掉字幕负面约束，其余保留>.
```

## 中文提示词（完整版，可用于改用中文提交）

```
写实电影级人像摄影，4K HDR，极致质感与细节，真实的皮肤纹理毛孔与自然细纹，
眼球真实折射，根根分明的真实眉毛毛发，电影级人像摄影。
年轻的东亚女性、二十出头，鹅蛋脸、肤色白皙通透、皮肤毛孔细腻；黑色长发自然垂在
脸颊两侧，向后梳理露出额头。桃花色大眼睛、虹膜纹理清晰、眼球湿润有反光，长睫毛，
精致的微烟熏眼影与上挑细眼线。自然野生眉、眉形优雅柔软带自然弧度、可见根根毛发，
是本片视觉焦点。粉嫩玻璃唇。俏皮自信的清纯气质。
固定机位，85-100mm 等效焦距极近景正面面部特写，眉眼位于画面上中的焦点，眼睛为
视觉中心，浅景深奶油虚化；背景为灰色调室内完全虚化；柔和正面美人光，面部受光均匀，
眼中带矩形眼神光，鼻梁与眉骨有细腻高光；全片仅轻微自然推近，不摇镜。
动作（5段约11秒）：
· 0-2s 右眉单挑：正面平视神情放松，随后只把右眉干净挑高一次，左眉不动，眼神专注带
  一丝俏皮，嘴角微扬，自信的单侧挑眉挑战；
· 2-4s 左眉单挑：右眉回位，再只把左眉干净挑高一次，右眉完全不动，眼神带调皮光泽；
· 4-6s 左右交替：右眉挑、左眉挑、右眉再挑，快速交替有节奏感，两眉绝不同时上挑，
  嘴边带笑眼神发亮；
· 6-8s 俏皮眨眼：眉回落，朝镜头俏皮地单闭右眼一次，双眉微扬，随后回归淡定自信微笑；
· 8-10s 定格+字幕：以右眉单挑自信定格收尾，双眼直视镜头，表情松弛带点得意，画面
  下方叠加粗体白色英文字幕 "DO YOU LIKE MY 'EYEBROW'?"。
负面：动漫、卡通、3D渲染、插画、五官变形、双眼不对称、手部畸形、多指、模糊、过度
锐化、塑料感皮肤、夸张瞪眼表演、皱眉、头部抖动、两眉同时上挑、水印、文字叠层、字幕。
```

## 中文精简（~50 字）
> 她依次只挑右眉、只挑左眉，再快速交替；随后俏皮眨眼，最后单挑右眉自信定格收尾，画面亮出 "DO YOU LIKE MY 'EYEBROW'?"。