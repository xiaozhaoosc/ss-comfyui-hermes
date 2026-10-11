# WF-3: ootd_dance_collage (多穿搭同框对比 · 分屏/四宫格) 测试提示词库

> **工作流定位**：多套不同 OOTD 穿搭（Look A / Look B 或四宫格）共享同一套舞蹈骨架与动作节奏，同屏并排（Side-by-Side）或分屏联动起舞。  
> **提示词编写原则**：聚焦于**两路/多路穿搭在色彩对比度、视觉重心平衡、材质互补性以及动作绝对同频**，适合电商多色款展示或风格反差对比。

---

## 提示词 1：【经典极致黑白撞色】极简曜石黑裁片西装 vs 珍珠白缎面晚礼裙

- **测试目标**：检验画面左半区（纯黑吸光、暗部细节）与右半区（纯白反光、高光细节）在同屏渲染时，动态范围是否平衡，两边的人物动作是否保持毫米级严格同频。
- **双 Look 穿搭配置**：
  - **左侧 Look A**：全黑高定羊毛裁片修身西装外套，内搭黑色深 V 抹胸与直筒垂坠西裤，黑色哑光尖头高跟鞋。
  - **右侧 Look B**：珍珠纯白真丝缎面露背晚礼服，侧开叉流动裙摆，银色纤细高跟鞋。
  - **统一背景与机位**：中央极简极灰无缝背景墙，柔和漫射顶光，两边无偏色。
- **中文综合描述**：
  > 极具视觉张力的黑白双子星分屏舞蹈。左侧身着曜石黑干练裁片西装，右侧身着珍珠白优雅缎面长裙。两位相同容貌的模特在相同的节拍与骨架驱动下并排起舞，抬手、转身、下摆飞扬完全同步，一刚一柔，黑白极度纯粹分明。
- **ComfyUI 英文 Positive Prompt (Look A / 左侧)**：
  ```text
  (masterpiece, best quality:1.2), dual dance split-screen left side, 1girl,
  (wearing obsidian black tailored sharp blazer suit:1.2), fine wool texture, deep V bralette, flowing wide-leg trousers, matte leather finish,
  synchronized fluid dance, clean neutral grey studio backdrop, balanced studio lighting, photorealistic, 8k
  ```
- **ComfyUI 英文 Positive Prompt (Look B / 右侧)**：
  ```text
  (masterpiece, best quality:1.2), dual dance split-screen right side, 1girl,
  (wearing pearl white pure silk satin evening slip dress:1.2), fluid liquid sheen, draped backline, high slit flowing hem,
  synchronized identical dance choreography, clean neutral grey studio backdrop, balanced studio lighting, photorealistic, 8k
  ```
- **通用 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), color bleed between sides, out-of-sync motion, asymmetrical lag, blown out white, crushed black shadows, deformed hands, blurry face, watermark
  ```
- **推荐配套参数**：单路 384x576 | CFG 7.0 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 2：【冷暖色彩学冲击】莫兰迪冷灰羊毛大衣 vs 暖橘珊瑚色修身针织裙

- **测试目标**：测试冷色调与暖色调在同屏中的色温隔离度，防止两边互相窜色或导致人物肤色偏蓝/偏黄。
- **双 Look 穿搭配置**：
  - **左侧 Look A**：莫兰迪冷灰及膝纯羊毛双排扣大衣，内搭冰蓝色高领打底，冷感高级职场风。
  - **右侧 Look B**：高饱和暖橘珊瑚色细坑条贴身连衣针织长裙，领口微露锁骨，元气温暖假日风。
  - **统一背景**：温润原木与混凝土拼接极简展厅，左右色温自然过渡。
- **中文综合描述**：
  > 冷暖色彩对比展示舞。左侧莫兰迪冷灰大衣沉稳高级，大衣下摆随动作带出利落折痕；右侧暖橘珊瑚色针织裙勾勒出曼妙身形，弹性面料随扭动呈现真实微小拉伸。两人动作同频律动，肤色均保持白皙通透。
- **ComfyUI 英文 Positive Prompt (Look A / 左侧)**：
  ```text
  (masterpiece, best quality:1.2), split-screen fashion comparison left side, 1girl,
  (wearing Morandi cool slate grey wool overcoat:1.2), ice blue turtleneck knit, sleek tailoring, crisp winter vibe, cool rim lighting,
  synchronized dance steps, hyperdetailed fabric weave, natural skin tones, 8k
  ```
- **ComfyUI 英文 Positive Prompt (Look B / 右侧)**：
  ```text
  (masterpiece, best quality:1.2), split-screen fashion comparison right side, 1girl,
  (wearing vibrant warm coral orange ribbed knit bodycon dress:1.2), form-fitting elastic fabric, warm radiant tones, cozy autumn vibe,
  synchronized dance steps, hyperdetailed fabric texture, natural skin tones, 8k
  ```
- **通用 Negative Prompt**：
  ```text
  (worst quality, low quality:1.3), color bleeding, cross-color distortion, yellowed whites, oversaturated, deformed anatomy, blurry, watermark
  ```
- **推荐配套参数**：单路 384x576 | CFG 6.8 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 3：【电商级同款不同色专柜画册】法式复古桔梗裙（波尔多红 vs 橄榄墨绿）

- **测试目标**：模拟真实服装电商品牌的“同款多色”上身对比展示，要求两边服装的版型、纽扣、褶皱位置完全一致，仅面料染料颜色产生纯正区别。
- **双 Look 穿搭配置**：
  - **左侧 Look A**：法式复古高腰桔梗裙（波尔多酒红色，复古优雅），胸前排扣与微泡泡袖。
  - **右侧 Look B**：同版型法式高腰桔梗裙（深橄榄墨绿色，低调复古），相同排扣与微泡泡袖。
  - **统一环境**：法式复古室内人字拼木地板，白纱窗帘柔光漫射，法式浪漫氛围。
- **中文综合描述**：
  > 电商专柜级双色联动展示。左边是浓郁优雅的波尔多红桔梗裙，右边是清冷典雅的深橄榄绿桔梗裙。除颜色外，两者的胸前复古贝壳排扣、抽绳腰带与裙摆垂坠弧度均保持严格一致。在同一支舞蹈中同频旋转，直观展现多色上身动态。
- **ComfyUI 英文 Positive Prompt (Look A / 左侧)**：
  ```text
  (masterpiece, best quality:1.2), commercial fashion catalog comparison, left side, 1girl,
  (wearing French retro A-line midi dress in deep Bordeaux wine red:1.2), high waistline, button-down front, puff sleeves, identical pattern to right side,
  seamless synchronized dance, herringbone wood floor interior, soft window daylight, 8k
  ```
- **ComfyUI 英文 Positive Prompt (Look B / 右侧)**：
  ```text
  (masterpiece, best quality:1.2), commercial fashion catalog comparison, right side, 1girl,
  (wearing French retro A-line midi dress in deep olive forest green:1.2), high waistline, button-down front, puff sleeves, identical pattern to left side,
  seamless synchronized dance, herringbone wood floor interior, soft window daylight, 8k
  ```
- **通用 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), mismatched pattern, inconsistent dress style, shape difference between sides, blurry buttons, bad hands, watermark
  ```
- **推荐配套参数**：单路 384x576 | CFG 7.0 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 4：【昼夜场景与反差角色】日间都市轻通勤 vs 夜幕深 V 奢华派对

- **测试目标**：测试同一人物在完全不同的光影环境（日间明朗办公室 vs 夜幕暗场闪光灯）下的同框协调性，考验环境光源与服装材质的反光匹配度。
- **双 Look 穿搭配置**：
  - **左侧 Look A**：日间通勤浅米色天丝亚麻西装套裙，内衬纯白 T 恤，清爽阳光感。
  - **右侧 Look B**：夜场派对黑色丝绒深 V 吊带短裙，腰间镶嵌细碎水钻链条，手持金色手包质感。
- **中文综合描述**：
  > “日与夜”双重身份分屏舞动。左侧沐浴在清晨日光明媚中，浅米色亚麻西装干练清爽；右侧沉浸在午夜聚光灯下，黑色丝绒吊带裙幽深奢华，水钻在暗色中熠熠生辉。两人舞步一模一样，如同白天与黑夜的自我对话。
- **ComfyUI 英文 Positive Prompt (Look A / 左侧)**：
  ```text
  (masterpiece, best quality:1.2), day and night duality split-screen left side, 1girl,
  (wearing bright day-time beige linen relaxed blazer and pleated skirt:1.2), clean white inner tee, bright morning sunbeams, crisp daylight, professional chic,
  synchronized dance choreography, natural skin, 8k uhd
  ```
- **ComfyUI 英文 Positive Prompt (Look B / 右侧)**：
  ```text
  (masterpiece, best quality:1.2), day and night duality split-screen right side, 1girl,
  (wearing midnight party black velvet plunging mini dress:1.2), rhinestone waist chain, glamorous nightlife spotlight, moody dark atmosphere with dramatic highlights,
  synchronized dance choreography, natural skin, 8k uhd
  ```
- **通用 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), uneven lighting bleed, noisy dark areas, washed out contrast, out-of-sync choreography, blurry, watermark
  ```
- **推荐配套参数**：单路 384x576 | CFG 7.2 | Steps 22 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 5：【极端厚度质感对比】轻薄贴身速干运动服 vs 蓬松加厚泰迪绒大衣

- **测试目标**：考验身体轮廓包裹度两个极端（极致贴身曲线 vs 超大蓬松廓形）在执行同一组舞蹈大幅度动作时，肢体比例是否失调、骨架约束是否依旧精准有效。
- **双 Look 穿搭配置**：
  - **左侧 Look A**：专业荧光雾霾蓝透气无缝速干运动背心与高腰瑜伽裤，凸显紧致肌肉线条与体态曲线。
  - **右侧 Look B**：蓬松加厚焦糖色羊羔毛泰迪熊长大衣，大翻领，搭配黑色打底裤，慵懒温暖廓形。
- **中文综合描述**：
  > 极具趣味的材质厚度对比分屏。左侧身着紧身雾霾蓝瑜伽运动套装，肌肉线条与骨骼运动清晰可见，动感十足；右侧身着蓬松厚实的焦糖色泰迪熊毛绒大衣，毛绒随动作轻微颤动，充满包裹感。同一套动作在紧绷与蓬松之间形成强烈反差。
- **ComfyUI 英文 Positive Prompt (Look A / 左侧)**：
  ```text
  (masterpiece, best quality:1.2), texture contrast split-screen left side, 1girl,
  (wearing athletic misty blue seamless sports bra and high-waist yoga leggings:1.2), form-fitting athletic wear, showing body contours and muscle tone, gym studio lighting,
  synchronized athletic dance, sharp focus, 8k
  ```
- **ComfyUI 英文 Positive Prompt (Look B / 右侧)**：
  ```text
  (masterpiece, best quality:1.2), texture contrast split-screen right side, 1girl,
  (wearing oversized fluffy caramel teddy bear fleece coat:1.2), shaggy faux fur texture, voluminous silhouette, cozy warmth,
  synchronized athletic dance, realistic fur bounce and motion, 8k
  ```
- **通用 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), distorted proportions, skinny limbs inside oversized coat, clipping through fabric, blurry fur, bad anatomy, watermark
  ```
- **推荐配套参数**：单路 384x576 | CFG 6.8 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧
