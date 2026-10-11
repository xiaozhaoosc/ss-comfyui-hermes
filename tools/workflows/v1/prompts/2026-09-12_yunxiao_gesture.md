# 云霄·古风手势舞 — H3 生成方案（2026-09-12）

## 方案摘要

| 项 | 值 |
|---|---|
| 画风 | 真人写实 |
| 段数 | 4 |
| 每段帧数 | 90, 90, 90, 90 |
| 总时长 | 15.00s |
| 画幅 | 544×960 |
| 采样 | euler/simple cfg=1.0 steps=34 shift=14.0:3.5 |
| 首帧锚定 | 无（纯 t2va） |
| 音频 | H3 原生同源生成 |
| 输出目录 | 2026-09-12/yunxiao_gesture |

## 公共模块（全片共用）

```
Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, cinematic night lighting with a violet-blue color grade, mystical and dreamy fairy atmosphere, realistic skin texture, realistic hair strands, realistic silk and gauze fabric physics, shallow depth of field, subtle film grain.

Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, long straight violet-purple hair reaching her waist with wispy air bangs and softly curled ends, elegant ancient-Chinese makeup with slender thin brows, violet eyeshadow, long lashes and matte red lips, a gorgeous black hair crown with sharp spike ornaments on top of her head, a slim collarbone necklace, a black wrist guard on her left wrist.

Costume: a pale lavender deep-V cross-collar hanfu with silk sleeves, a matching sheer gauze shawl draped over her arms, a wide black belt decorated with golden patterns cinching her waist, and a slit skirt that reveals her leg when she moves.

Setting: night in an ancient Chinese garden, deep blue-violet night sky, faint mist drifting close to the ground, distant silhouetted trees, soft moonlight rimming her hair and shoulders, a quiet exotic and romantic atmosphere.
```

## 分段

### 段 1（90 帧 ≈ 3.75s）

- CAMERA: `Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition with her in the middle of the frame, no camera movement, no pull or push, no cuts, the wh`
- MOTION: `Action: she presses both palms together in front of her chest, then slowly separates her hands and lifts them upward until her fingertips point toward each other above her head, sleeves sliding down her forearms, her body swaying softly to the rhythm.`
- AUDIO: `Audio: a light catchy Chinese female pop song, a young woman singing in Mandarin the hook line "亲爱的，你是否还记得", soft airy voice over an easy mid-tempo pop beat with plucked strings and light electronic p`
- 微表情锚点: She smiles gently and keeps her gaze lively and sweet, chin slightly lifted, eyes on the camera.

### 段 2（90 帧 ≈ 3.75s）

- CAMERA: `Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts.`
- MOTION: `Action: her hands roll in a smooth wave in front of her chest, wrists loose, then her right hand sweeps outward to the side while her left hand comes up to support her chin, her head tilting slightly.`
- AUDIO: `Audio: the same female Mandarin pop song continues smoothly, her vocal melody riding the light beat, guzheng and synth accents behind it, sweet and dreamy, no other speech.`
- 微表情锚点: Her eyes stay bright and a little flirtatious, a small smile on her lips, a quick soft blink as she tilts her head.

### 段 3（90 帧 ≈ 3.75s）

- CAMERA: `Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts.`
- MOTION: `Action: both hands cross in front of her chest, then open outward to the two sides with palms facing out, the gauze shawl spreading with the movement, her waist twisting gently.`
- AUDIO: `Audio: the song keeps its gentle groove, the female vocal carrying the chorus, soft percussion and strings, warm and romantic night mood, no other speech.`
- 微表情锚点: Her expression stays confident and charming with a soft smile, chin level, eyes holding the camera.

### 段 4（90 帧 ≈ 3.75s）

- CAMERA: `Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts.`
- MOTION: `Action: her hands draw back toward her chest with fingers curled like soft claws, then close into loose fists that rise up to the sides of her cheeks while she twists her upper body slightly to the beat.`
- AUDIO: `Audio: the same female Mandarin pop song reaches its final sweet phrase and ends on a soft sustained note with the beat tapering out, no other speech.`
- 微表情锚点: Her eyes sparkle, ending with a sweet bright smile facing the camera, chin tucked a little, mouth corners lifted.

## 每段完整 prompt（可直接投喂）

**段 %d**
```
Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, cinematic night lighting with a violet-blue color grade, mystical and dreamy fairy atmosphere, realistic skin texture, realistic hair strands, realistic silk and gauze fabric physics, shallow depth of field, subtle film grain. Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, long straight violet-purple hair reaching her waist with wispy air bangs and softly curled ends, elegant ancient-Chinese makeup with slender thin brows, violet eyeshadow, long lashes and matte red lips, a gorgeous black hair crown with sharp spike ornaments on top of her head, a slim collarbone necklace, a black wrist guard on her left wrist. Costume: a pale lavender deep-V cross-collar hanfu with silk sleeves, a matching sheer gauze shawl draped over her arms, a wide black belt decorated with golden patterns cinching her waist, and a slit skirt that reveals her leg when she moves. Setting: night in an ancient Chinese garden, deep blue-violet night sky, faint mist drifting close to the ground, distant silhouetted trees, soft moonlight rimming her hair and shoulders, a quiet exotic and romantic atmosphere. Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition with her in the middle of the frame, no camera movement, no pull or push, no cuts, the whole take is continuous. Action: she presses both palms together in front of her chest, then slowly separates her hands and lifts them upward until her fingertips point toward each other above her head, sleeves sliding down her forearms, her body swaying softly to the rhythm. She smiles gently and keeps her gaze lively and sweet, chin slightly lifted, eyes on the camera. Audio: a light catchy Chinese female pop song, a young woman singing in Mandarin the hook line "亲爱的，你是否还记得", soft airy voice over an easy mid-tempo pop beat with plucked strings and light electronic percussion, romantic and sweet, no other voices. Avoid: outfit change, face change distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change.
```

**段 %d**
```
Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, cinematic night lighting with a violet-blue color grade, mystical and dreamy fairy atmosphere, realistic skin texture, realistic hair strands, realistic silk and gauze fabric physics, shallow depth of field, subtle film grain. Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, long straight violet-purple hair reaching her waist with wispy air bangs and softly curled ends, elegant ancient-Chinese makeup with slender thin brows, violet eyeshadow, long lashes and matte red lips, a gorgeous black hair crown with sharp spike ornaments on top of her head, a slim collarbone necklace, a black wrist guard on her left wrist. Costume: a pale lavender deep-V cross-collar hanfu with silk sleeves, a matching sheer gauze shawl draped over her arms, a wide black belt decorated with golden patterns cinching her waist, and a slit skirt that reveals her leg when she moves. Setting: night in an ancient Chinese garden, deep blue-violet night sky, faint mist drifting close to the ground, distant silhouetted trees, soft moonlight rimming her hair and shoulders, a quiet exotic and romantic atmosphere. Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts. Action: her hands roll in a smooth wave in front of her chest, wrists loose, then her right hand sweeps outward to the side while her left hand comes up to support her chin, her head tilting slightly. Her eyes stay bright and a little flirtatious, a small smile on her lips, a quick soft blink as she tilts her head. Audio: the same female Mandarin pop song continues smoothly, her vocal melody riding the light beat, guzheng and synth accents behind it, sweet and dreamy, no other speech. Avoid: outfit change, face change distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change.
```

**段 %d**
```
Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, cinematic night lighting with a violet-blue color grade, mystical and dreamy fairy atmosphere, realistic skin texture, realistic hair strands, realistic silk and gauze fabric physics, shallow depth of field, subtle film grain. Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, long straight violet-purple hair reaching her waist with wispy air bangs and softly curled ends, elegant ancient-Chinese makeup with slender thin brows, violet eyeshadow, long lashes and matte red lips, a gorgeous black hair crown with sharp spike ornaments on top of her head, a slim collarbone necklace, a black wrist guard on her left wrist. Costume: a pale lavender deep-V cross-collar hanfu with silk sleeves, a matching sheer gauze shawl draped over her arms, a wide black belt decorated with golden patterns cinching her waist, and a slit skirt that reveals her leg when she moves. Setting: night in an ancient Chinese garden, deep blue-violet night sky, faint mist drifting close to the ground, distant silhouetted trees, soft moonlight rimming her hair and shoulders, a quiet exotic and romantic atmosphere. Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts. Action: both hands cross in front of her chest, then open outward to the two sides with palms facing out, the gauze shawl spreading with the movement, her waist twisting gently. Her expression stays confident and charming with a soft smile, chin level, eyes holding the camera. Audio: the song keeps its gentle groove, the female vocal carrying the chorus, soft percussion and strings, warm and romantic night mood, no other speech. Avoid: outfit change, face change distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change.
```

**段 %d**
```
Style: photorealistic live-action cosplay cinematography, real human actress, ultra high detail, cinematic night lighting with a violet-blue color grade, mystical and dreamy fairy atmosphere, realistic skin texture, realistic hair strands, realistic silk and gauze fabric physics, shallow depth of field, subtle film grain. Character: a young East Asian woman in her early twenties, delicate oval face, fair luminous skin, long straight violet-purple hair reaching her waist with wispy air bangs and softly curled ends, elegant ancient-Chinese makeup with slender thin brows, violet eyeshadow, long lashes and matte red lips, a gorgeous black hair crown with sharp spike ornaments on top of her head, a slim collarbone necklace, a black wrist guard on her left wrist. Costume: a pale lavender deep-V cross-collar hanfu with silk sleeves, a matching sheer gauze shawl draped over her arms, a wide black belt decorated with golden patterns cinching her waist, and a slit skirt that reveals her leg when she moves. Setting: night in an ancient Chinese garden, deep blue-violet night sky, faint mist drifting close to the ground, distant silhouetted trees, soft moonlight rimming her hair and shoulders, a quiet exotic and romantic atmosphere. Camera: fixed camera, eye level, medium shot framing her upper body and part of her legs, centered composition, no camera movement and no cuts. Action: her hands draw back toward her chest with fingers curled like soft claws, then close into loose fists that rise up to the sides of her cheeks while she twists her upper body slightly to the beat. Her eyes sparkle, ending with a sweet bright smile facing the camera, chin tucked a little, mouth corners lifted. Audio: the same female Mandarin pop song reaches its final sweet phrase and ends on a soft sustained note with the beat tapering out, no other speech. Avoid: outfit change, face change distorted face, deformed hands, extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay, oversharpened, plastic skin, outfit change, face change.
```

## 后期清单（H3 生成不了，需 ffmpeg/剪映）

- 字幕 / 文案标签 / 平台水印
- 卡点剪辑与二次变速
- 转场特效（叠化/闪白/闪黑/缩放）
- 若需替换成指定商用 BGM：以 `-audio.mp4` 为画面源重新混音
