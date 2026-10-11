# 动漫时尚短片 · 10 姿势 128 BPM 极简白棚（动漫渲染版）

**任务**：动漫 2D 渲染时尚短片（角色由参考图定义，忽略原背景、不新增配饰）
**日期**：2026-09-07
**脚本**：`D:\ai_projects\ComfyUI\tools\h3_fashion_10pose_anime.py`
**输出目录**：`D:\ai_projects\ComfyUI\output\fashion_10pose_anime\`
**参考人物**：`D:\ai_projects\ComfyUI\input\gemini_ken1\C02_PADDED.png`
**切片**：5 段 × 72 帧（≈3s，末帧链式衔接），总长约 15s

## 采样参数（组2 锐化版）

| 项 | 值 |
|---|---|
| Steps | 34 |
| Sampler / Scheduler | euler / simple（flow matching 固定配置） |
| CFG | 1.0（H3 无 CFG，负面复用正面） |
| shift_video / shift_audio | 14.0 / 3.5（4:1） |
| Resolution | 544×960 @ 24fps |
| 段数 | 5 段链式；段1 首帧=C02_PADDED，后续段首帧=上段末帧 |
| 首段 seed | 20261008+i（i=段序） |
| 音频 | 128 BPM EDM（无 vocals，鼓点/闪光卡点） |

## 风格 / 人物 / 镜头 共用前缀

### STYLE（动漫渲染）
```
high-quality anime fashion short, 2D animated cel-shaded rendering, clean precise line
art, detailed anime facial features, glossy dynamic fashion illustration, minimalist
white cyclorama studio with no visible seams, strong studio strobe flash lighting,
subtle atmospheric haze, glossy reflective floor, a satin fabric draped nearby,
scattered loose proof-sheet papers on the floor, high contrast, film-like grain,
rhythmic dynamic motion.
```

### CHARACTER（沿用参考图，动漫化，不新增配饰）
```
Use the same young East Asian woman from the reference image drawn in anime style to fully
define her face, body, wardrobe, accessories and styling — do NOT introduce any new
accessories or change her look; match the reference exactly. She has a statuesque hourglass
figure with nine-heads-tall proportion, long slender straight legs, cinched waist flowing
into softly rounded hips, graceful neck and clear collarbones, poised upright upper body.
```

### CAMERA
```
The camera moves along a physically continuous path forward, accelerating quickly between
poses and decelerating sharply to a stop at the moment each pose locks. Rhythmic pacing
matched to 128 BPM.
```

### AUDIO
```
 128 BPM electronic dance music, punchy studio strobe hits synced with the beat, no vocals,
modern fashion runway energy.
```

### NEGATIVE（动漫版：反写实，不反动漫）
```
live-action photo, photorealistic, realistic human, CGI 3D render, off-model, line art and
color errors, schematic, distorted face, deformed hands, extra fingers, extra limbs, bad
anatomy, melted limbs, blurry, watermark, text overlay, dull flat colors, flat lighting,
background objects copied from reference, new accessories added, jerky robotic motion
```

## 分段动作 / 摄影机时间轴（5 段 × ~3s）

### SEG01 · 0-3s · 姿势1-2
```
Pose 1 (0:00-0:01.5): Medium close-up, centered front. She faces the camera, one hand
gently toying with a strand of hair by her ear, the camera pushing in slowly with restraint.
Pose 2 (0:01.5-0:03.0): she turns to a three-quarter profile, chin slightly lifted.
The camera sweeps down in a fast arc and then holds on her eyes.
```

### SEG02 · 3-6s · 姿势3-5
```
Pose 3 (continuing): she lowers her gaze, both hands settling softly near her collar and hair.
Pose 4 (0:03.0-0:04.5): she rotates to a strict left-side profile. The camera sweeps past
her cheek in a fast pass and then steadies in close.
Pose 5: she rotates one shoulder forward, the edge of her robe sharply rimmed by side light.
```

### SEG03 · 6-9s · 姿势6-8
```
Pose 6 (0:04.5-0:06.0): she gently pinches a fold of her long robe at her waist, then releases it.
Pose 7: she turns her mouth toward the camera, gaze looking back over her shoulder at the
camera. The camera drops quickly to torso level and then rises past her face in close.
Pose 8 (0:06.0-0:07.5): she sits low onto the satin fabric, one knee raised.
```

### SEG04 · 9-12s · 姿势9-10
```
Pose 9: she extends one bare foot toward the camera, occupying the main foreground. The
camera rushes forward at ground level and locks on the dramatic forced-perspective pose.
Pose 10 (0:07.5-0:09.0): she rises to a three-quarter side stance, one hand at her collarbone,
the other touching her hair, the long robe gliding lightly over her thigh. The camera slides
laterally across her waistline and then eases into a stable portrait framing.
```

### SEG05 · 12-15s · 延伸+结尾
```
Extension (0:09-0:11): without repeating earlier poses, she folds her body inward and closes
her eyes for one breath, then unfurls into a continuous upward stretch.
Extension (0:11-0:13): she twists into a back three-quarter shoulder silhouette, then rotates
slightly so her jawline and the robe's neckline catch the same flash of light.
Final (0:13-0:15): the camera sweeps from her shoulder toward her face in strong parallax,
glides past her eyes and along the robe's neckline, then arcs outward while descending. She
lands in a final dominant full-body pose, looking down at the camera, in total command.
```

## 中文提示词（完整版，可用于改用中文提交）

```
高质量动漫时尚短片，2D 赛璐珞着色渲染，干净精准的线条，精细动漫五官，亮泽动感的时尚
插画质感；极简白色无影棚、无可见接缝，强烈影棚闪光灯、淡淡薄雾、光泽倒影地面，旁边
垂着一块缎面布料，地板上散落着样张纸，高对比度、胶片级颗粒、富有节奏的动感。
用参考图里的同一年轻东亚女性按动漫风格完整定义她的脸、身材、服装、配饰和造型——不得
添加任何新配饰、不得改变她的外形，严格还原参考图。她拥有九头身比例的美人鱼身形、
修长笔直的腿、收腰流入圆润胯部、优雅脖颈与清晰锁骨、挺拔的上身。
摄影机沿物理连续路径前进，在两个姿势间快速加速、每个姿势定格的瞬间急刹停下，节奏严格
贴合 128 BPM。
动作与摄影机时间轴（约15秒，5段）：
· 0-1.5s 姿势1：中景正面居中，面向镜头，一只手轻拨耳边发丝，摄影机克制缓慢推进；
· 1.5-3s 姿势2：转向四分之三侧面、微抬下巴，摄影机快速向下弧线后停在眼部；
· 3-4.5s 姿势3、4：垂下视线，双手轻落领口与发际；旋转至严格左侧面，摄影机快速掠过
  脸颊后近距稳定；
· 4.5-6s 姿势5：向前转动一侧肩膀，长袍边缘被侧光清晰勾勒；
· 6-7.5s 姿势6、7、8：腰间轻抓长袍褶皱后松开；转嘴朝向镜头从肩上方回眸；坐低到缎面上，
  一头膝盖抬起；
· 7.5-9s 姿势9、10：一只赤脚伸向镜头占据前景，摄影机贴近地面高速前冲锁定强烈透视；起身
  四分之三侧身，一手放锁骨一手触头发，长袍轻掠大腿，摄影机横向滑过腰线渐稳成人像构图；
· 9-11s 延伸：不重复前述姿势，身体内收紧闭双眼呼吸一次，随后舒展向上伸展；
· 11-13s 延伸：扭转成背部四分之三肩部轮廓，略微转身让下颌线与领口捕捉闪光；
· 13-15s 结尾：摄影机从肩膀滑向面部强烈视差，掠过眼睛沿领口外弧形拉开降低，最终落入
  主导感全身姿势、低头俯视镜头收场。
音频：128 BPM 电子舞曲，鼓点与闪光卡点，纯音乐无人声。
负面：实拍照片、真人写实、CG 3D 渲染、崩画、线稿与上色错误、草稿感、五官变形、手部
畸形、多指、多肢、解剖失常、肢体扭曲、模糊、水印、文字叠层、颜色灰暗、光线平淡、
复刻参考图背景物体、新增配饰、僵硬的机器人式动作。
```

## 中文精简（~50 字）
> 白棚极简，十连姿势一气呵成；闪光掠过她的锁骨与长袍，缎面与赤脚在镜头前起伏，128 BPM 节奏的加速与急停里，她最终以俯视定格压制全场。