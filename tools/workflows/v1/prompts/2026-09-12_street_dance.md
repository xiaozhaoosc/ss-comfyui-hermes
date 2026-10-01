# 自信女生的活力街舞 — H3 生成方案（2026-09-12）

## 方案摘要

| 项 | 值 |
|---|---|
| 画风 | 真人写实 |
| 段数 | 3 |
| 每段帧数 | 124, 124, 124 |
| 总时长 | 15.50s |
| 画幅 | 544×960 |
| 采样 | euler/simple cfg=1.0 steps=34 shift=14.0:3.5 |
| 首帧锚定 | gemini_ken1/C02_PADDED.png |
| 音频 | H3 原生同源生成 |
| 输出目录 | 2026-09-12/street_dance |

## 公共模块（全片共用）

```
Style: realistic street-dance performance shot on a standard lens, medium shot at eye level, fixed camera, centered composition, bright and fresh color grading, medium saturation, clean crisp image, shallow depth of field, subtle film grain, realistic skin texture.

Character: the same young East Asian woman as the reference image, identical face and body, delicate features, refined light makeup with defined eye area and natural nude-pink lips, fair luminous skin, black long hair pulled up into a neat high bun with a few soft strands loose at her temples, no jewelry, no accessories.

Outfit: a fitted purple short-sleeve t-shirt with a slightly cropped hem and a gray high-waisted bodycon mini skirt that hugs her hips and ends at mid-thigh, the purple cotton fabric stretching with her movement, a slim defined waist, hot-girl casual street-dance styling, black ankle socks and white low-top sneakers.

Setting: a bright clean indoor space with a plain light wall behind her and a smooth floor under her feet, soft even daylight from the front, no props, no other people, the background softly blurred so she stays the single visual focus.
```

## 分段

### 段 1（124 帧 ≈ 5.17s）

- CAMERA: `Camera: fixed camera, eye level, medium shot on a standard lens, she stays centered in the frame with her whole body from the head down to the sneakers inside the frame, the camera does not move, no c`
- MOTION: `Action: hip-hop freestyle groove. She starts on the beat with a light bounce in her knees, her shoulders loose, both hands rolling in a smooth wave in front of her chest, one hand after the other, her hips swinging gently in counter-rotation to her chest; then`
- AUDIO: `Audio: high-energy electronic dance music, dense punchy drum pattern on a steady fast four-on-the-floor beat, driving bass line, bright synth stabs, purely instrumental with no vocals and no speech; t`
- 微表情锚点: She smiles the whole time and keeps her eyes locked on the camera with calm confidence, chin relaxed, the corners of her mouth lifted.

### 段 2（124 帧 ≈ 5.17s）

- CAMERA: `Camera: fixed camera, eye level, medium shot on a standard lens, she stays centered in the frame with her whole body inside the frame, the camera does not move and there are no cuts.`
- MOTION: `Action: the groove continues without a break and grows bigger — her right arm shoots forward and snaps back to her chest, her left arm sweeps out behind her, her weight bounces from one foot to the other with small quick steps in place, her torso twisting and `
- AUDIO: `Audio: the same energetic electronic dance track keeps rolling with a dense beat and bass groove, instrumental only, no vocals; her body stays locked to the drums.`
- 微表情锚点: Her expression stays bright, smiling, chin up, eyes on the camera, a quick blink on the accent beat.

### 段 3（124 帧 ≈ 5.17s）

- CAMERA: `Camera: fixed camera, eye level, medium shot on a standard lens, centered composition, the camera does not move and there are no cuts.`
- MOTION: `Action: she pushes the tempo harder — both arms pump up and down in alternating waves above shoulder height, her body rocking front and back with quick footwork in place, hips circling once, then she lands the last beat with a confident finishing pose, feet ap`
- AUDIO: `Audio: the dance track drives to its peak with louder drums and a short snappy fill on the final beat, still instrumental, no vocals, then cuts off cleanly at the end.`
- 微表情锚点: She finishes facing the camera with a big genuine smile, eyes crinkling slightly, chin lifted with quiet pride.

## 每段完整 prompt（可直接投喂）

**段 %d**
```
Style: realistic street-dance performance shot on a standard lens, medium shot at eye level, fixed camera, centered composition, bright and fresh color grading, medium saturation, clean crisp image, shallow depth of field, subtle film grain, realistic skin texture. Character: the same young East Asian woman as the reference image, identical face and body, delicate features, refined light makeup with defined eye area and natural nude-pink lips, fair luminous skin, black long hair pulled up into a neat high bun with a few soft strands loose at her temples, no jewelry, no accessories. Outfit: a fitted purple short-sleeve t-shirt with a slightly cropped hem and a gray high-waisted bodycon mini skirt that hugs her hips and ends at mid-thigh, the purple cotton fabric stretching with her movement, a slim defined waist, hot-girl casual street-dance styling, black ankle socks and white low-top sneakers. Setting: a bright clean indoor space with a plain light wall behind her and a smooth floor under her feet, soft even daylight from the front, no props, no other people, the background softly blurred so she stays the single visual focus. Camera: fixed camera, eye level, medium shot on a standard lens, she stays centered in the frame with her whole body from the head down to the sneakers inside the frame, the camera does not move, no cuts except a hard cut at the start. Action: hip-hop freestyle groove. She starts on the beat with a light bounce in her knees, her shoulders loose, both hands rolling in a smooth wave in front of her chest, one hand after the other, her hips swinging gently in counter-rotation to her chest; then her arms open outward and her head nods slightly to the rhythm. She smiles the whole time and keeps her eyes locked on the camera with calm confidence, chin relaxed, the corners of her mouth lifted. Audio: high-energy electronic dance music, dense punchy drum pattern on a steady fast four-on-the-floor beat, driving bass line, bright synth stabs, purely instrumental with no vocals and no speech; the movement hits the beat. Avoid: changing outfit, changing face, wobbling background distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change.
```

**段 %d**
```
Style: realistic street-dance performance shot on a standard lens, medium shot at eye level, fixed camera, centered composition, bright and fresh color grading, medium saturation, clean crisp image, shallow depth of field, subtle film grain, realistic skin texture. Character: the same young East Asian woman as the reference image, identical face and body, delicate features, refined light makeup with defined eye area and natural nude-pink lips, fair luminous skin, black long hair pulled up into a neat high bun with a few soft strands loose at her temples, no jewelry, no accessories. Outfit: a fitted purple short-sleeve t-shirt with a slightly cropped hem and a gray high-waisted bodycon mini skirt that hugs her hips and ends at mid-thigh, the purple cotton fabric stretching with her movement, a slim defined waist, hot-girl casual street-dance styling, black ankle socks and white low-top sneakers. Setting: a bright clean indoor space with a plain light wall behind her and a smooth floor under her feet, soft even daylight from the front, no props, no other people, the background softly blurred so she stays the single visual focus. Camera: fixed camera, eye level, medium shot on a standard lens, she stays centered in the frame with her whole body inside the frame, the camera does not move and there are no cuts. Action: the groove continues without a break and grows bigger — her right arm shoots forward and snaps back to her chest, her left arm sweeps out behind her, her weight bounces from one foot to the other with small quick steps in place, her torso twisting and dipping, the purple t-shirt and the gray skirt following the motion, her bun staying neat while loose strands swing. Her expression stays bright, smiling, chin up, eyes on the camera, a quick blink on the accent beat. Audio: the same energetic electronic dance track keeps rolling with a dense beat and bass groove, instrumental only, no vocals; her body stays locked to the drums. Avoid: changing outfit, changing face, wobbling background distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change.
```

**段 %d**
```
Style: realistic street-dance performance shot on a standard lens, medium shot at eye level, fixed camera, centered composition, bright and fresh color grading, medium saturation, clean crisp image, shallow depth of field, subtle film grain, realistic skin texture. Character: the same young East Asian woman as the reference image, identical face and body, delicate features, refined light makeup with defined eye area and natural nude-pink lips, fair luminous skin, black long hair pulled up into a neat high bun with a few soft strands loose at her temples, no jewelry, no accessories. Outfit: a fitted purple short-sleeve t-shirt with a slightly cropped hem and a gray high-waisted bodycon mini skirt that hugs her hips and ends at mid-thigh, the purple cotton fabric stretching with her movement, a slim defined waist, hot-girl casual street-dance styling, black ankle socks and white low-top sneakers. Setting: a bright clean indoor space with a plain light wall behind her and a smooth floor under her feet, soft even daylight from the front, no props, no other people, the background softly blurred so she stays the single visual focus. Camera: fixed camera, eye level, medium shot on a standard lens, centered composition, the camera does not move and there are no cuts. Action: she pushes the tempo harder — both arms pump up and down in alternating waves above shoulder height, her body rocking front and back with quick footwork in place, hips circling once, then she lands the last beat with a confident finishing pose, feet apart, one hand on her hip, the other arm hanging loose, chest lifted. She finishes facing the camera with a big genuine smile, eyes crinkling slightly, chin lifted with quiet pride. Audio: the dance track drives to its peak with louder drums and a short snappy fill on the final beat, still instrumental, no vocals, then cuts off cleanly at the end. Avoid: changing outfit, changing face, wobbling background distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change.
```

## 后期清单（H3 生成不了，需 ffmpeg/剪映）

- 字幕 / 文案标签 / 平台水印
- 卡点剪辑与二次变速
- 转场特效（叠化/闪白/闪黑/缩放）
- 若需替换成指定商用 BGM：以 `-audio.mp4` 为画面源重新混音
