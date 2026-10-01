# 妖尾·艾露莎 Cosplay 变装 · 9:16 竖屏 短视频

**任务**：Cosplay 变装展示 + 女团律动舞蹈（日常少女 → 艾露莎战斗服）
**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_erza_cosplay.py`
**输出目录**：`D:\ai_projects\ComfyUI\output\erza_cosplay\`
**参考人物**：`D:\ai_projects\ComfyUI\input\gemini_ken1\C02_PADDED.png`（cosplayer 本体脸部；变身前后同一张脸）
**切片**：2 段链式（SEG1 变身 ~3s，SEG2 舞蹈 ~8s；段2 首帧=段1 末帧）

## 采样参数

| 项 | 值 |
|---|---|
| Steps | 34 |
| Sampler / Scheduler | euler / simple（flow matching 固定配置） |
| CFG | 1.0（H3 无 CFG，负面复用正面） |
| shift_video / shift_audio | 14.0 / 3.5（4:1） |
| Resolution | 544×960 @ 24fps；SEG1=72帧≈3s，SEG2=192帧≈8s |
| 段数 | 2 段链式；SEG1 首帧=C02_PADDED，SEG2 首帧=SEG1 末帧 |
| 首段 seed | 20261016+i |
| 音频 | K-pop 女团律动《Cry Cry》式节拍（ching ching…hook），纯音乐 |

## 风格 / 镜头 前缀

### STYLE
```
realistic cinematic photography, ultra high detail, bright clear lighting, medium
saturation, shallow depth of field, film grain, glossy healthy skin, centered
composition, fixed camera, eye-level, medium-to-close shot showing full body and
facial expression.
```

### CAMERA
```
Fixed camera, eye-level, centered composition, person in the middle of the frame, no
push-pull-pan-tilt, single continuous unbroken shot, no transitions except an in-scene
magic flash.
```

### AUDIO
```
Energetic K-pop girl-group dance track with a driving beat and a rhythmic 'ching ching
ching ching cry cry' hook, punchy bass, no vocals speech except the song; music only.
```

### NEGATIVE
```
anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra fingers,
extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened,
dull skin, jerky movement
```

## 变身前 / 后 人物

### 变身 · 前（日常少女）
```
The same young East Asian woman as the reference image (a cosplayer), same face and
body, delicate features, light sweet clean-girl makeup. Brown long straight hair
flowing down, wearing black thin-frame glasses. Casual outfit: a deep-blue
spaghetti-strap halter top with denim shorts. Casual, everyday look.
```

### 变身 · 后（妖尾·艾露莎）
```
She now wears the battle outfit of Erza Scarlet from 'Fairy Tail', an anime cosplay:
vivid red high ponytail with a small blue hair-tie accent, white strapless bustier
crop top, wine-red shorts with white binding straps around the waist, and blue
magic-circle tattoos/patterns on her arms. Confident, spirited and heroic vibe,
refined and dimensional makeup.
```

## 分段提示词

### SEG1 · 变身（~3s，72帧）
```
0-3 seconds: the girl stands centered facing the camera, calm and sweet with brown
straight hair and glasses, then she claps her hands together in a magic hand-seal
gesture in front of her chest and mouths a spell, a swirl of glowing magic light and
sparkles rises around her, a brilliant flash bursts — and in one transformation moment
she becomes <ERZA_AFTER> the flash settles and she stands in Erza's battle outfit, now
with red ponytail. Seamless magical transformation.
```

### SEG2 · 舞蹈（~8s，192帧）
```
3-11 seconds, continuing after the transformation: as Erza Scarlet she moves to the
beat with a light lively girl-group rhythm dance for about 8 seconds — confident hip
sway, sharp arm pops, side stepping and confident runway moves and poses synced to the
'ching ching ching ching cry cry' hook, bright smile, spirited heroic and dazzling,
dynamic but smooth and lively, ending on a bold confident final pose holding the
magic-seal hand gesture.
```

## 中文提示词（完整版，可用于改用中文提交）

```
写实电影级摄影，超高细节，明亮清晰光线，中等饱和度，浅景深，胶片颗粒，健康亮泽肌肤，
居中构图，平视固定机位，中景到近景展现全身与表情。
【变身前】与参考图同一年轻东亚女性（cosplayer）同脸同身材，清新甜美淡妆，棕色长直发
披散，戴黑色细框眼镜，深蓝色吊带上衣+牛仔短裤的休闲日常装。
【镜头】固定机位、平视、居中构图、人物始终在画面中央，无推拉摇移，一镜到底，仅场景内
魔法闪光作为转场。
【变身后】化身为《妖精的尾巴》艾露莎·斯卡雷特战斗服：鲜艳红色高马尾+蓝色小发绳点缀，
白色无肩带束胸短上衣，酒红色短裤、腰际白色绑带装饰，手臂有蓝色魔法阵纹身刺青，
自信飒爽英气，妆容精致立体。
【动作】开头：女生双手合十在胸前结魔法手势念咒语，周围升起发光魔法光与星尘，一道
耀眼闪光爆发——一瞬间完成变身成为艾露莎，红色高马尾亮相，闪光落定；随后 3-11 秒，
艾露莎随女团电子舞曲节拍做轻快律动舞蹈约 8 秒：自信扭胯、利落摆臂、横移步与自信走位
Pose，整齐卡住「ching ching ching ching cry cry」的节拍，全程甜美自信笑容、灵动眼神、
飒爽耀眼，动感流畅，最后以一个自信地再度结魔法手势的定格 Pose 收尾。
【音频】动感感染力的 K-pop 女团电子舞曲（《Cry Cry》风格），强烈律动、切分鼓点与
「ching ching cry cry」hook；纯音乐，无人声解说。
【字幕】画面左侧竖排显示「正宫娘娘 天生丽质」，画面中间偏下标注「妖尾-艾露莎」。
负面：动漫、卡通、3D渲染、插画、五官变形、手部畸形、多指、多肢、解剖失常、肢体扭曲、
模糊、水印、文字叠层、过度锐化、皮肤干涩、动作僵硬。
```

## 中文精简（~50 字）
> 棕发眼镜少女双手结印，闪光一瞬变身红色马尾的艾露莎；随「ching ching cry cry」节拍扭胯摆臂、走位定格，飒爽自信燃到收尾。