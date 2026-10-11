# 溪畔苹果·丰满东方女孩 — 保留体型/表情生成记录

> 日期:2026-09-09 | 类型:图生图(img2img,低 denoise 保体型构图)
> 参考图:hermes cache img_a3ba228782c5 → `ComfyUI/input/ref_instream_apples_plump.png`
> 结果:✅ `ComfyUI/output/2026-09-09/instream_plump_00001_.png`(GLM-4V 目检通过:丰满体型/抓拍表情/服装/场景全中)

## 生成参数
- 模型:flux1-dev-fp8 (UNETLoader) + t5xxl_fp8 + clip_l (DualCLIPLoader, flux) + flux-vae-bf16
- Lora:hinaFluxDevAsianMix_v12 (0.9/0.9,亚洲面孔)
- 采样:euler/simple,steps=22,**denoise=0.45**(关键:低 denoise 保留参考图体型/姿态/表情基调)
- FluxGuidance 3.5,cfg=1.0,1024×768(lanczos),seed=42
- 工作流 json:`zen_probe/img2img_instream_apples.json`

## 用户原版提示词 ① 叙事版(物理级,全景镜头叙事)
```
A candid, detailed environmental photograph captured from an ultra-low water-level perspective in a crystal-clear shallow mountain stream. The central figure is a young East Asian woman, around 20s, with dark hair loosely pinned into a messy high bun with soft bangs and floral pins. She is in an authentic candid moment, kneeling and crouching barefoot on mossy river stones.
Her body mass and volume are distinctly represented: a (plump body, heavy breasts, deep cleavage, soft natural skin folds, realistic body fat distribution:1.3) with (thick thighs, ample legs:1.2), emphasizing a realistic, fleshy, plump physique rather than a slim standard. Her facial micro-expression is specific: (parted lips, slightly flushed cheeks, soft focused gaze looking down at her hands, relaxed facial muscles, candid micro-expression:1.2), a tender and focused joy, not just a simple smile.
She wears a cream-colored sheer textured ribbed lace long-sleeve blouse with a low neckline and a pastel floral ruffled mini skirt, the fabric naturally accentuating her heavy body shape:1.2 and appearing slightly damp. Her hands are submerged in the water, playfully catching floating crisp red and yellow apples on the surface, surrounded by floating pink flower petals and mossy grey stones.
To the left, on a large boulder, a rustic hand-woven wicker basket overflows with apples. Background elements include dense verdant forest foliage, blooming pink wild blossoms, stream rapids cascading into a small waterfall, and a traditional wooden mountain chalet with warm internal amber lights. The lighting is soft diffused spring daylight, with gentle specular highlights on wet skin and stones. 35mm f/2.2 lens, photorealistic:1.2, highly detailed skin texture, raw photographic quality.
```

## 用户原版提示词 ② Tag 版(WebUI/权重微调)
```
(masterpiece, photorealistic:1.2), 1girl, young east asian woman, candid moment, hands submerged in stream water, crouching naturally, barefoot, mossy river stones,
(plump body, heavy breasts, deep cleavage, soft natural skin folds, realistic body fat distribution:1.3), (thick thighs, ample legs:1.2), specific body volume and mass, tight sheer lace top accentuating body shape,
(parted lips, slightly flushed cheeks, soft focused gaze looking down, relaxed facial muscles, candid micro-expression:1.2), tender concentration,
cream lace ribbed blouse, low neckline, floral ruffled mini skirt, slightly damp clothes, loose high bun, floral hairpin,
(floating red apples in clear water:1.3), floating pink flower petals, rustic wicker basket with apples on mossy rock,
dense green forest, blooming pink bushes, stream rapids, distant wooden cabin with warm amber lights,
(ultra-low camera angle, water-level shot:1.3), 35mm f/2.2 lens, shallow depth of field,
natural diffused lighting, soft dappled sunlight, cinematic film color grading, authentic raw photographic texture, visible skin pores.
```

## 用户原版提示词 ③ Negative
```
(worst quality, low quality:1.4), (plastic skin, oversmoothed skin:1.3), porcelain doll face, doll-like symmetry, perfect symmetry, heavy makeup, artificial lighting, sterile background, exaggerated glamour poses, stiff poses, (CGI, 3D render, digital painting:1.2), oversaturated, (standard slim figure:1.3), (standardized model body:1.2), deformed hands, floating objects, unnatural water reflection, modern objects, sunglasses.
```

## FLUX 实际提交版(剥离 SD 权重语法,叙事保留)
Candid environmental photograph, a young East Asian woman in her early 20s kneeling barefoot on mossy river stones in a crystal-clear shallow mountain stream, shot from an ultra-low water-level perspective. Dark hair in a loose messy high bun with soft bangs and small floral pins. She has a plump, voluptuous full body, heavy breasts with deep cleavage, soft natural skin folds, realistic body fat distribution, thick thighs and ample full legs. Parted lips, slightly flushed cheeks, soft focused gaze looking down at her hands, relaxed facial muscles, candid spontaneous micro-expression, tender focused joy. She wears a cream-colored sheer textured ribbed lace long-sleeve blouse with a low neckline and a pastel floral ruffled mini skirt, the slightly damp fabric naturally accentuating her full heavy figure. Her hands are submerged in the water, playfully catching floating crisp red and yellow apples on the surface, surrounded by floating pink flower petals and mossy grey stones. To the left on a large boulder, a rustic hand-woven wicker basket overflowing with apples. Background: dense verdant forest foliage, blooming pink wild blossoms, stream rapids cascading into a small waterfall, traditional wooden mountain chalet with warm amber inner lights. Soft diffused spring daylight, gentle specular highlights on wet skin and stones, 35mm f/2.2 lens, shallow depth of field, photorealistic, highly detailed skin texture with visible pores, raw photographic quality, cinematic film color grading, masterpiece

> ⚠️ FLUX 说明:FLUX 的 T5 编码**不支持** `(word:1.3)` 加权语法与 negative prompt(CFG=1 蒸馏模型),权重语法会被当字面文本。此处已剥离;体型/表情强调靠形容词堆叠+img2img 低 denoise 锁定参考图实现。