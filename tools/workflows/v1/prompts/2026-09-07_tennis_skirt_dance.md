# 网球裙扭腰卡点摇 · 校园风热舞 · 9:16 竖屏

**任务**：扭腰卡点摇（校园风热舞，流行街舞元素）
**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_tennis_skirt_dance.py`
**输出目录**：`D:\ai_projects\ComfyUI\output\tennis_skirt_dance\`
**参考人物**：`D:\ai_projects\ComfyUI\input\gemini_ken1\C02_PADDED.png`（系列同一张脸）
**切片**：3 段链式 × 124帧≈5.2s；后续段首帧=上段末帧

## 采样参数

| 项 | 值 |
|---|---|
| Steps | 34；Sampler euler/simple；CFG 1.0 |
| shift_video / shift_audio | 14.0 / 3.5 |
| Resolution | 544×960 @ 24fps；段长124帧≈5.2s，3段≈15.5s |
| 段数 | 3 段链式；SEG1 首帧=C02_PADDED |
| 音频 | 强节奏 EDM + 英文说唱 hook「sixteen sixteen all day」，无解说纯音乐 |

## 风格 / 人物 / 镜头 前缀

### STYLE
```
realistic cinematic photography, ultra high detail, bright sunny daylight, vibrant colorful
and fresh, medium saturation, shallow depth of field with blurred soft background, film
grain, glossy healthy skin, clean composition.
```

### CHARACTER（白Polo + 藏蓝百褶裙 + 深棕高马尾）
```
The same young East Asian woman as the reference image, same face and body, delicate
youthful features, fresh light makeup emphasizing the eye area and rosy lips,
porcelain-fair luminous skin, statuesque hourglass figure with nine-heads-tall proportion:
long slender legs, cinched waist flowing into softly rounded hips, graceful neck and clear
collarbones. Hair: deep-brown long hair tied up in a high ponytail, with a few soft
face-framing strands. Outfit: a white short-sleeve polo shirt with thin black piping on the
collar and cuffs, paired with a navy-blue pleated mini skirt, fresh vibrant campus-girl
style, clean and sporty.
```

### CAMERA
```
Fixed camera, eye-level, medium shot with occasional cuts to close-up, person centered in
frame with blurred background, camera mainly still while she moves, stepping and turning to
fill the frame, hard cuts on beats.
```

### MUSIC
```
High-energy driving electronic dance music with a strong beat and a repetitive English rap
hook like 'sixteen sixteen all day', punchy bass, perfect for beat-synced bopping, no speech
other than the song, pure instrumental vocal hook.
```

### NEGATIVE
```
anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra fingers,
extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened,
dull skin, jerky robotic movement
```

## 分段提示词

### SEG1 · 开场
```
A fresh vibrant campus girl starts a beat-synced waist-bopping dance: both hands lightly
stroke her chest then spread open to both sides while she twists her waist, ponytail and
navy pleated skirt swaying, confident smile, bright animated eyes. Sunny cheerful energy.
```

### SEG2 · 连续扭腰摆臀 + 前行
```
Continuing the same woman, same high ponytail, white polo and navy pleated skirt:
continuous rhythmic waist-twisting and hip pops synced tight to the beat, arms flowing in
wave-like sweeps, hair casually flicked as she steps lightly forward, skirt fluttering,
playful flirty-yet-vibrant smile, rhythmic and infectious.
```

### SEG3 · 双手合十致敬收尾
```
Continuing the same woman, same look: she finishes the routine — hands clasp together in
front of her chest, she gives a slight nod with a soft confident smile, holding the final
beat-synced pose, ponytail settling, bright sunny energy, a neat bow-like ending to the
dance.
```

## 中文提示词（完整版，可用于改用中文提交）

```
写实电影级摄影，超高细节，明亮阳光户外光，鲜艳清新、中等饱和度，浅景深背景虚化，胶片
颗粒，健康亮泽肌肤，干净构图。
【人物】与参考图同一年轻东亚女性，同脸同身形，清纯年轻、淡妆强调眼部与红润唇色，瓷白
透亮肌肤、九头身美人鱼身材：修长笔直双腿、收腰入圆润胯部、优雅脖颈与锁骨。发型：深棕
长发扎成高马尾，几缕碎发修饰面部。服装：白色短袖Polo衫（领口袖口黑色细边），搭配藏蓝
色百褶短裙，清新校园风、干净利落。
【镜头】平视固定机位，中景为主、偶尔切近景，人物居中、背景虚化突出主体，镜头基本不动，
靠她走位与转身丰富画面，硬切卡重拍。
【动作】开场：随节拍双手轻抚胸前、旋即向两侧展开，同时腰部扭动，马尾与藏蓝百褶裙随动，
自信微笑、眼神灵动，阳光清爽；中段：连续扭腰摆臀卡准拍点，手臂波浪状挥舞，轻撩头发并
轻盈向前走动，裙摆飘动，俏皮又活力的微笑，律动感染；结尾：双手合十置于胸前，微微点头
报以一个柔和自信的笑容，定格卡拍，马尾落定，阳光清爽地整套收尾。
【音频】强节奏动感电子舞曲，重复英文说唱 hook「sixteen sixteen all day」，鼓点强烈，适合
卡点摇，无解说纯音乐。
字幕标签：#扭腰卡点摇 #热门舞蹈
负面：动漫、卡通、3D渲染、插画、五官变形、手部畸形、多指多肢、解剖失常、肢体扭曲、
模糊、水印、文字叠层、过度锐化、皮肤干涩、僵硬机器人动作。
```

## 中文精简（~50 字）
> 白Polo藏蓝百褶裙，高马尾随节拍轻摆；抚胸展开、扭腰摆臀前行，双手合十点头定格，阳光校园感满分的卡点热舞。