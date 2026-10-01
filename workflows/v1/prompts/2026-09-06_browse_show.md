# 变装走秀 · A 白西装黑裙 → B 红色金花旗袍

**任务类型**：AI 变装走秀（双段独立 + 闪斩转场）
**日期**：2026-09-06
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_browse_show.py`
**输出目录**：`D:\ai_projects\ComfyUI\output\browse_show\`
**参考人物**：`D:\ai_projects\ComfyUI\input\gemini_ken1\C02_PADDED.png`

## 采样参数（组2 锐化版）

| 项 | 值 |
|---|---|
| Steps | 34 |
| Sampler / Scheduler | euler / simple（flow matching 固定配置） |
| CFG | 1.0（H3 无 CFG，负面复用正面） |
| shift_video / shift_audio | 14.0 / 3.5（严格 4:1 耦合） |
| Resolution | 544×960 @ 24fps × 124 帧 ≈ 5.17s/段 |
| 段数 | 2 段独立（无末帧链式） |
| 转场 | ffmpeg 闪斩 0.3s（黑 0.15s + 白 0.15s） |

## 风格（Style）

### A 套（清新明亮）
```
realistic cinematic photography, ultra high detail, fresh bright clean lighting,
cool modern color palette with soft highlights, shallow depth of field, film
grain, glossy healthy skin.
```

### B 套（浓郁暖调华丽）
```
realistic cinematic photography, ultra high detail, warm rich saturated lighting,
deep crimson and gold color palette with dramatic warm highlights, shallow depth
of field, film grain, glossy healthy skin.
```

## 人物底色（共用 Character Base）

```
The same young East Asian woman as the reference image, same face and body,
delicate elegant features, slim-shaped eyebrows, light smoky eye makeup, full
lips, porcelain-fair luminous skin. Long straight black hair flowing down her
back with silky smooth texture and perfect drape. She has a statuesque hourglass
figure with nine-heads-tall proportion: long slender straight legs, cinched
waist flowing into softly rounded hips, graceful swan-like neck, clear
collarbones, poised upright upper body. A simple gold pendant necklace sits
against her collarbone.
```

## 服装（Outfit）

### A 套 — 白色短款西装外套 + 黑色高开叉吊带裙
```
Outfit A: a crisp white cropped blazer jacket over a form-fitting black
spaghetti-strap slip dress with a daring high slit up one side revealing the
leg curve, black pointed high heels.
```

### B 套 — 红色旗袍式长裙 + 金色花纹
```
Outfit B: a floor-length red qipao-style gown adorned with intricate gold floral
embroidery, traditional mandarin collar with ornate gold trim, one side slit
high up to mid-thigh revealing the leg, elegant red silk clinging to every curve,
matching red or gold heels.
```

## 场景（Setting）

### A 套 — 现代白色 T 台
```
A bright modern fashion runway: white glossy floor, soft white lights, blurred
modern cityscape in the background, cool high-key atmosphere, narrow depth of
field creating bokeh.
```

### B 套 — 华丽东方红金 T 台
```
A dramatic warm-red Oriental runway: deep crimson curtains, golden lantern
accents, rich warm amber spotlight, blurred impression of a classical Chinese
palace interior in the background, glamorous cinematic depth.
```

## 镜头（Camera）

```
Fixed camera at eye-level, full body centered slightly right of frame following
the rule of thirds, enough background depth behind her to suggest runway depth.
```

## 走秀动作（Walk）

```
She walks confidently down the runway toward the camera with perfect runway
posture: chin up, shoulders relaxed back, hips swaying subtly with each step,
core engaged, arms swinging naturally at her sides or one hand lightly grazing
the dress slit, decisive steady strides on pointed heels. She smiles gently
with calm magnetic confidence, eyes locked forward, occasionally casting a
captivating sidelong glance at the camera with a hint of allure. Slow-mo feel
on leg reveal through the slit.
```

## 音频设计（Audio）

```
High-energy electronic dance music with a strong punchy beat, deep bass, sharp
synthesizer hits, tempo matching her stride, no vocals — pure driving EDM
runway music.
```

## 负面约束（Negative）

```
anime, cartoon, 3D render, illustration, distorted face, deformed hands,
extra fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark,
text overlay, oversharpened, dull skin, bent legs, broken heels
```

---

## 最终提交（Generator 拼接后的 Prompt 原文）

模型实际收到的两段完整 Prompt 是：`STYLE(A|B) + CHARACTER_BASE + OUTFIT(A|B) + SETTING(A|B) + CAMERA + WALK + AUDIO + " Avoid: " + NEG`。

参考脚本：`tools/h3_browse_show.py` 中的 `SEG_PROMPTS["A_outfit"]` 与 `SEG_PROMPTS["B_outfit"]`。
