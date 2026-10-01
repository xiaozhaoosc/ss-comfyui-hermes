# 室内性感慢摇舞蹈 · Heels/Urban 慵懒都市风 · 9:16 竖屏

**任务**：室内性感慢摇舞蹈（撩拨 → 扭腰摆臂 → 高潮定格）
**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_indoor_heels_dance.py`
**输出目录**：`D:\ai_projects\ComfyUI\output\indoor_heels_dance\`
**参考人物**：`D:\ai_projects\ComfyUI\input\gemini_ken1\C02_PADDED.png`（系列同一张脸）
**切片**：3 段链式 × 124帧≈5.2s；后续段首帧=上段末帧

## 采样参数

| 项 | 值 |
|---|---|
| Steps | 34；Sampler euler/simple；CFG 1.0 |
| shift_video / shift_audio | 14.0 / 3.5 |
| Resolution | 544×960 @ 24fps；段长124帧≈5.2s，3段≈15.5s |
| 段数 | 3 段链式；SEG1 首帧=C02_PADDED |
| 音频 | 日系 EDM，明快舞曲 + 日语女声「watashi ga misete ageru kiss」，纯音乐卡点 |

## 风格 / 人物 / 镜头 前缀

### STYLE
```
realistic cinematic photography, ultra high detail, professional studio mood lighting,
soft warm indoor glow, high contrast, shallow depth of field, film grain, glossy healthy
skin, cinematic color grade.
```

### CHARACTER（深棕长卷发 + 黑蕾丝裙 + 黑丝 + 银色手链）
```
The same young East Asian woman as the reference image, same face and body, delicate
elegant features, porcelain-fair luminous skin, statuesque hourglass figure with
nine-heads-tall proportion: long slender legs, cinched waist flowing into softly rounded
hips, graceful neck and clear collarbones, poised upright upper body. Hair: deep-brown
long loose wavy curls naturally draped over her shoulders, alluring and elegant. Makeup:
refined bold makeup — crisp eyeliner, full red lips, dimensional contour. Outfit: a
form-fitting black spaghetti-strap lace slip dress with subtle floral-dot details and
wavy lace trim, hugging and seductive. Black high heels with black sheer thin stockings
that elongate her legs. A slim silver metal bracelet on her left wrist.
```

### CAMERA
```
Fixed camera, eye-level, medium shot with occasional moments to full body and face,
rule-of-thirds composition with her centered slightly right of frame, a sofa and floor
lamp creating rich background layers, single continuous unbroken shot.
```

### MUSIC
```
Upbeat driving Japanese EDM with a bright synth melody and a seductive laid-back vibe,
with a clear Japanese female vocal line 'watashi ga misete ageru kiss' ('I'll show you a
kiss') interspersed; punchy beat, teasing atmosphere.
```

### NEGATIVE
```
anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra fingers,
extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened,
dull skin, jerky robotic movement, stiff posture
```

## 分段提示词

### SEG1 · 开场撩拨
```
A confident alluring girl begins a slow seductive dance: she stands smoothly, hands
crossing over her chest then trailing down, one hand running through her deep-brown wavy
hair, a teasing glance at the camera, subtle swaying of her hips, black dress and sliver
bracelet catching warm light. Lazy, confident, inviting.
```

### SEG2 · 扭腰摆臂中段
```
Continuing the same woman, same deep-brown wavy hair and black lace dress: she flows into
fluid waist-twisting and hip pulses synced to the beat, arms swaying and sweeping softly,
fingertips gently brushing her cheek and collarbone, stepping small rhythmic steps, body
undulating with the Japanese EDM, each move elegant and teasing.
```

### SEG3 · 高潮定格
```
Continuing the same woman, same look: the climax of the slow-shake — a smooth slow bob and
sway with arms tracing her silhouette, then a coy hand gesture toward the camera with
index finger pointing, slight tilt of the head, eyes half-lidded enjoying the music,
holding a confident alluring final heel-pose, dress and curls in motion, moody warm light.
```

## 中文提示词（完整版，可用于改用中文提交）

```
写实电影级摄影，超高细节，专业影棚情绪布光，柔和暖色室内光，高对比，浅景深，胶片颗粒，
健康亮泽肌肤，电影感调色。
【人物】与参考图同一年轻东亚女性，同脸同身形，清丽五官、瓷白透亮肌肤、九头身美人鱼
身材：修长笔直双腿、收腰入圆润胯部、优雅脖颈与锁骨、挺拔上身。发型：深棕色长卷发自然
披散肩头，妩媚优雅。妆容：精致浓妆——清晰眼线、饱满红唇、立体修容。服装：黑色吊带
蕾丝吊带裙、带细碎花纹点缀与波浪状蕾丝衣边，修身性感；黑色高跟+黑色薄款丝袜拉长腿部；
左手腕一条简约银色金属手链。
【镜头】平视固定机位，中景为主、偶尔推近全身与脸，三分法构图人物居画面中央偏右，沙发
与落地灯构成丰富背景层次，一镜到底无转场。
【动作】开场：自信魅惑地站定，双手交叉抚胸然后缓缓下滑，一手撩过深棕卷发，勾人地瞥向
镜头，腰肢轻摆，黑裙与银色手链在暖光中微光闪烁，慵懒自信撩人；中段：随节拍流畅扭腰、
胯部小幅律动，手臂轻柔摆动、指尖轻触脸颊与锁骨，小步律动，随日系电音起伏，每一动都
优雅撩人；高潮：慢摇收尾——缓慢律动与摆臂勾勒身形，随后向镜头比出一个食指指向的俏皮
手势，轻歪头，半阖双眼享受音乐，定格一个自信又魅惑的高跟 Pose，裙摆与卷发借光摆动。
【音频】明快动感的日系电子舞曲（EDM），明亮合成器旋律、慵懒略带挑逗的氛围，穿插清晰
日语女声「私が見せてあげる キス（我来给你看，亲吻）」，卡点节奏。
字幕标签：#美女 #慢摇 #舞蹈 #黑丝
负面：动漫、卡通、3D渲染、插画、五官变形、手部畸形、多指多肢、解剖失常、肢体扭曲、
模糊、水印、文字叠层、过度锐化、皮肤干涩、僵硬机器人动作。
```

## 中文精简（~50 字）
> 深棕卷发、黑蕾丝短裙与黑丝，晕黄暖光里慵懒慢摇；抚胸撩发、扭腰摆臂，指致镜头时半阖眼定格，日系电音里性感撩人收尾。