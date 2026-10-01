# 动漫时尚短片 · 10 姿势 128 BPM 极简白棚

**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_fashion_10pose.py`
**输出**：`D:\ai_projects\ComfyUI\output\fashion_10pose\`
**首帧参考**：`gemini_ken1/C02_PADDED.png`
**切片**：5 段 × ~2.6s × 63 帧（末帧链式衔接）

## 采样参数（组2 锐化）
- steps 34 / euler / simple / cfg 1.0
- shift_video 14.0 / shift_audio 3.5（4:1）
- 544×960 @ 24fps

## 风格
```
realistic cinematic fashion photography, ultra high detail, strong studio strobe
flash lighting, subtle atmospheric haze, glossy reflective floor, satin fabric
draped nearby, scattered loose proof-sheet papers on the floor, minimalist white
cyclorama studio with no visible seams, high contrast, film grain, glossy healthy
skin, rhythmic dynamic motion.
```

## 人物（@[char ref] 由 C02_PADDED 提供）
```
Use the same young East Asian woman from the reference image to fully define her
face, body, wardrobe, accessories and styling — do NOT introduce any new
accessories or change her look. Match the reference exactly. She has a statuesque
hourglass figure with nine-heads-tall proportion, long slender straight legs,
cinched waist flowing into softly rounded hips, graceful neck and clear collarbones,
poised upright upper body.
```

## 摄影机
```
The camera moves along a physically continuous path forward, accelerating quickly
between poses and decelerating sharply to a stop at the moment each pose locks.
Rhythmic pacing matched to 128 BPM.
```

## 音频
```
128 BPM electronic dance music, punchy studio strobe hits synced with the beat, no
vocals, modern fashion runway energy.
```

## 负面
```
anime, cartoon, 3D render, illustration, distorted face, deformed hands, extra
fingers, extra limbs, bad anatomy, melted limbs, blurry, watermark, text overlay,
oversharpened, dull skin, new accessories added, background objects copied from
reference, jerky robotic motion
```

## 分段（10 姿势映射到 5 段）

### SEG01 · 0-3s · 姿势1-2
```
Pose 1 (0:00-0:01.5): Medium close-up, centered front. She faces the camera, one
hand gently toying with a strand of hair by her ear, the camera pushing in slowly
with restraint.
Pose 2 (0:01.5-0:03.0): she turns to a three-quarter profile, chin slightly
lifted. The camera sweeps down in a fast arc and then holds on her eyes.
```

### SEG02 · 3-6s · 姿势3-5
```
Pose 3 (continuing): she lowers her gaze, both hands settling softly near her
collar and hair.
Pose 4 (0:03.0-0:04.5): she rotates to a strict left-side profile. The camera
sweeps past her cheek in a fast pass and then steadies in close.
Pose 5: she rotates one shoulder forward, the edge of her robe sharply rimmed by
side light.
```

### SEG03 · 6-9s · 姿势6-8
```
Pose 6 (0:04.5-0:06.0): she gently pinches a fold of her long robe at her waist,
then releases it.
Pose 7: she turns her mouth toward the camera, gaze looking back over her shoulder
at the camera. The camera drops quickly to torso level and then rises past her face
in close.
Pose 8 (0:06.0-0:07.5): she sits low onto the satin fabric, one knee raised.
```

### SEG04 · 9-12s · 姿势9-10
```
Pose 9: she extends one bare foot toward the camera, occupying the main
foreground. The camera rushes forward at ground level and locks on the dramatic
forced-perspective pose.
Pose 10 (0:07.5-0:09.0): she rises to a three-quarter side stance, one hand at her
collarbone, the other touching her hair, the long robe gliding lightly over her
thigh. The camera slides laterally across her waistline and then eases into a
stable portrait framing.
```

### SEG05 · 12-15s · 终姿势+收尾
```
she twists into a back three-quarter shoulder silhouette, then rotates slightly so
her jawline and the robe's neckline catch the same flash of light. The camera
sweeps from her shoulder toward her face in strong parallax, glides past her eyes
and along the robe's neckline, then arcs outward while descending. She lands in a
final dominant full-body pose, looking down at the camera, in total command.
```

## 中文精简（~50 字）
> 白棚极简，十连姿势一气呵成；闪光掠过她的锁骨与长袍，缎面与赤脚在镜头前起伏，128 BPM 节奏的加速与急停里，她最终以俯视定格压制全场。
