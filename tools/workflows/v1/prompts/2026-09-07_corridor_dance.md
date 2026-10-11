# 走廊法式风情打卡舞 · 9:16 竖屏 5 秒

**任务**：舞蹈打卡 · 法式风情（校园走廊一镜到底）
**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\submit_h3_corridor.py`
**输出目录**：`D:\ai_projects\ComfyUI\output\h3_corridor\`
**成片**：`corridor_full.mp4`（等待队列生成后混音）
**参考人物**：`D:\ai_projects\ComfyUI\input\gemini_ken1\C02_PADDED.png`（沿用系列人物脸部）

## 采样参数（默认版）

| 项 | 值 |
|---|---|
| Steps | 20 |
| Sampler / Scheduler | euler / simple（flow matching 固定配置） |
| CFG | 1.0（H3 无 CFG，负面复用正面） |
| shift_video / shift_audio | 12.0 / 3.0 |
| Resolution | 672×1152 @ 24fps × 124 帧 ≈ 5.2s |
| 段数 | 单段（一镜到底） |
| seed | 20261001 |
| 音频 | H3 原生 EDM 电子舞曲（32kHz 立体声） |

## 风格 / 人物 / 镜头 共用前缀

### STYLE
```
realistic cinematic photography, ultra high detail, bright fresh clean daylight,
medium saturation, natural soft light with warm sunlight through windows casting on
the corridor floor, shallow depth of field, film grain, glossy healthy skin.
```

### CHARACTER
```
The same young East Asian woman as the reference image, same face and body, delicate
elegant features, slim-shaped eyebrows, refined light makeup emphasizing the eye
contour, full glossy lips, porcelain-fair luminous skin. Black long straight hair
flowing naturally over both shoulders. Outfit: a white fitted long-sleeve dress ending
at knee level accentuating the figure curve, paired with white casual sneakers, simple
pure with French-elegant everyday chic.
```

### CAMERA
```
Setting: a bright school corridor with natural depth perspective, the young woman
standing slightly left of center forming a natural frame between the two corridor
walls, sunlight streaming through windows onto the floor. Fixed camera at eye-level,
medium shot showing her full body and part of the background, single continuous
unbroken shot, no camera moves, no transitions.
```

### NEGATIVE
```
anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra fingers,
extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened,
dull skin, jerky movement
```

## 舞蹈动作（单段一镜到底）

```
Dance, French-style check-in dance (popular dance steps fused with a relaxed French
vibe): she beams a bright sweet confident smile, eyes sparkling lively.
· Opening: both hands clasped into fists raised at her chest, gently swaying
  left-right to the beat.
· Second: right arm lifts upward, left arm stretches outward, her body turns and steps
  forward.
· Middle: alternating arms sweep arcs in front of her body while her feet step back
  and forth.
· Ending: both fists return near her cheeks, body sways softly, finishing the smooth
  dance. Energetic and graceful, full of vitality.
```

## 音频设计

```
Background music: a cheerful upbeat energetic EDM with a strong driving beat; music
only, no vocals, no speech.
```

## 中文提示词（完整版，可用于改用中文提交）

```
写实电影级摄影，超高细节，明亮清新日光，中等饱和度，柔和自然光，阳光透过窗户洒在
走廊地面上，浅景深，胶片颗粒，健康亮泽肌肤。
与参考图同一年轻东亚女性，同脸同身材，精致五官、细眉、强调眼部轮廓的淡妆、饱满双唇、
白皙发光肌肤。黑色长直发自然披散双肩。白色修身长袖连衣裙至膝，凸显曲线，配白色休闲
板鞋，简约清纯法式日常优雅。
场景：明亮校园走廊，自然纵深透视，女生站在画面中央偏左，两侧墙壁形成自然框架构图，
阳光透过窗落在走廊地面。平视固定机位，中景展现全身及部分背景，一镜到底、无运镜、无转场。
法式风情打卡舞（流行舞步+法式慵懒）：全程甜美自信的笑容，眼神灵动。
· 开头：双手握拳举于胸前，随节拍左右轻摆；
· 第一段：右手上举、左手外展，身体转动并向前迈步；
· 中间：双手在身前交替划弧，配合脚步前后移动；
· 结尾：双手再次握拳靠近脸颊，身体轻扭，流畅收尾。活力轻盈。
背景音乐：欢快动感的电子舞曲，强烈律动；纯音乐无人声。
负面：动漫、卡通、3D渲染、插画、五官变形、手部畸形、多指、多肢、解剖失常、肢体扭曲、
模糊、水印、文字叠层、过度锐化、皮肤干涩、动作僵硬。
```

## 中文精简（~50 字）
> 阳光洒进走廊，白裙少女随电子舞曲单手叉腰又握拳近颊，转身、挥手、弧线步法一气呵成，笑容甜到结束。