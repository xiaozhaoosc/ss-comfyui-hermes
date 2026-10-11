# WF-1: ootd_dance_switch (卡点变装跳舞 · 一舞多穿) 测试提示词库

> **工作流定位**：在保持同一段舞蹈动作连续进行的前提下，视频按节拍分为 3 个区间，每隔 3~4 秒自动切换一套全新的 OOTD 穿搭，实现音乐卡点变装效果。  
> **提示词编写原则**：动作由 OpenPose/DWPose 控制器锁定，提示词聚焦于**服装反差跨度、面料质感变化、转场光影氛围**，避免包含具体的微观动作描述以防与骨架冲突。

---

## 提示词 1：【风格反差极限测试】甜酷学院风 ➔ 暗黑机能风 ➔ 奢华晚宴风

- **测试目标**：检验工作流在跨度极大（青春学生装 ➔ 硬核机能绑带 ➔ 高级丝绸长裙）的三套风格间卡点切换时，人物脸部一致性是否稳固，以及服装版型突变时是否有残影或融化现象。
- **阶段划分**：
  - **Look 1 (0~4s)**：美式复古学院风，灰白格纹百褶短裙，白色针织开衫与深蓝领带，明亮室内暖光。
  - **Look 2 (4~8s)**：暗黑赛博机能风，哑光黑色反光机能夹克，金属搭扣工装短裤与皮质腿环，冷蓝侧逆光。
  - **Look 3 (8~12s)**：高定奢华晚宴风，墨绿色深 V 露背丝绸吊带长裙，流光溢彩的金线刺绣，柔和暖金追光。
- **中文综合描述**：
  > 电影级写实画质，一位气质出众的年轻女子随着节奏欢快起舞。第 1 段身着美式学院复古百褶裙与针织衫，洋溢青春元气；卡点瞬间切换为黑色暗黑机能夹克与工装绑带，冷艳干练；最后卡点变装为高定墨绿丝绸晚礼服，裙摆优雅飘动。顶光与侧光交融，8k 超高清，真实皮肤纹理。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality, ultra-detailed:1.2), cinematic dance video, photorealistic, 1girl, 20yo Korean beauty, fluid dance choreography, dynamic outfit transformation,
  (segment 1: preppy retro pleated skirt, white knit cardigan, tie, warm soft indoor lighting:1.1),
  (segment 2: techwear cyberpunk black matte tactical jacket, straps, cool rim lighting:1.1),
  (segment 3: luxury emerald green satin evening gown, elegant gold embroidery, warm golden spotlight:1.1),
  volumetric lighting, 8k resolution, raw photo, highly detailed face and fabric texture
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (low quality, worst quality:1.4), blurry, deformed limbs, floating clothes, inconsistent face, bad anatomy, bad hands, mutated fingers, extra limbs, clothing glitch, artifacts, watermark, text
  ```
- **推荐配套参数**：CFG 7.0 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 2：【光影材质质感测试】复古法式碎花 ➔ 红色皮衣夹克 ➔ 银色闪烁亮片

- **测试目标**：检验自然棉麻布料 ➔ 高反光皮革 ➔ 动态碎钻亮片的面料物理质感还原度，重点观察光斑闪烁与噪点控制。
- **阶段划分**：
  - **Look 1 (0~4s)**：法式复古小碎花泡泡袖方领连衣裙，淡黄底色小雏菊，自然漫反射柔光。
  - **Look 2 (4~8s)**：美式街头复古亮面大红色机车皮衣，黑色修身打底，皮革光泽反射与金属拉链高光。
  - **Look 3 (8~12s)**：派对迪斯科全银色反光亮片吊带裙，随着旋转折射出彩虹色微小星芒。
- **中文综合描述**：
  > 一位时尚女性在聚光灯下连续跳舞，随着鼓点变装。由清新自然的法式法黄碎花裙，瞬间切换为极具力量感的大红色机车皮夹克，最后卡点变身为波光粼粼的银色亮片派对短裙。真实布料与皮革高光，极高动态范围。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), photorealistic, 1girl, solo dancing, smooth movement, fashion outfit transition,
  (look 1: French vintage floral square-neck puff-sleeve dress, soft ambient daylight:1.1),
  (look 2: vibrant crimson red shiny leather biker jacket, metallic zips, glossy reflections:1.1),
  (look 3: glamorous silver sparkling disco sequin cocktail dress, refracted glittering highlights:1.1),
  sharp focus, natural skin texture, realistic cloth physics, raytracing reflections, 8k uhd
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), plastic skin, overexposed, blown out highlights, deformed body, unnatural lighting, artifacts, blurry, bad proportions, watermark
  ```
- **推荐配套参数**：CFG 7.5 | Steps 22 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 3：【国风东方美学测试】新中式水墨旗袍 ➔ 敦煌绯红汉服 ➔ 现代极简改良盘扣唐装

- **测试目标**：测试古典丝绸、雪纺披帛飘动与暗纹刺绣在舞蹈旋转中的动态渲染能力。
- **阶段划分**：
  - **Look 1 (0~4s)**：新中式改良月白真丝旗袍，衣身带有淡雅水墨晕染竹叶，侧边开叉，温润古典。
  - **Look 2 (4~8s)**：敦煌飞天风绯红色重工披帛汉服，朱砂红与石青金边，飘带在空中盘旋舞动。
  - **Look 3 (8~12s)**：现代极简玄黑立领盘扣西装外套，内衬暗红织锦缎，刚柔并济的东方现代美。
- **中文综合描述**：
  > 充满东方神韵的现代古典变装舞蹈。身穿月白水墨真丝旗袍优雅起舞；音乐高潮处卡点变身为热烈飘逸的敦煌绯红飞天汉服，披帛飞扬；随后收束为利落帅气的玄黑盘扣改良西装。古典与现代交织，工笔画般精美。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), traditional Chinese aesthetics, modern neo-oriental dance, 1girl, graceful fluid dance,
  (segment 1: moonlight white pure silk modern qipao, subtle ink wash bamboo patterns, slit hemline:1.1),
  (segment 2: Dunhuang crimson red celestial hanfu, flowing flying ribbons, vermilion and gold embroidery:1.2),
  (segment 3: contemporary minimalist obsidian black tang suit jacket, mandarin collar, dark red brocade lining:1.1),
  cinematic atmospheric lighting, mist, cloth floating dynamics, 8k, elegant composition
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.3), chaotic ribbons, messy fabric, deformed hands, western castle, cartoon, illustration, bad anatomy, blur, watermark
  ```
- **推荐配套参数**：CFG 7.0 | Steps 20 | Sampler: dpmpp_2m | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 4：【都市潮流与场景穿越】极简灰白卫衣 ➔ 荧光撞色赛博工装 ➔ 优雅浅驼色羊绒风衣

- **测试目标**：考验生活休闲款到高对比度荧光潮牌、再到厚实羊绒垂坠感的层次转换，检验背景虚化与服装轮廓贴合度。
- **阶段划分**：
  - **Look 1 (0~4s)**：街头随性浅灰色连帽卫衣，黑色骑行短裤，慵懒日常感。
  - **Look 2 (4~8s)**：赛博潮流荧光绿拼黑多口袋工装套装，带反光条，街头涂鸦霓虹背景。
  - **Look 3 (8~12s)**：大牌高级浅驼色双面羊绒长大衣，内搭米白高领毛衣，秋季微风吹拂。
- **中文综合描述**：
  > 街头潮流卡点变装舞。从随性舒适的浅灰连帽卫衣，瞬间变身为充满科技感的荧光绿黑拼色工装，最后化身为优雅大气的浅驼色羊绒风衣，大衣下摆随转身飞扬。景深虚化自然，画面干净透亮。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), urban streetwear fashion, 1girl dancing energetically, sharp cuts on the beat,
  (look 1: casual heather grey oversized hoodie, black cycling shorts, clean white studio background:1.1),
  (look 2: cyber neon lime green and black techwear cargo set, reflective strips, glowing neon backdrop:1.1),
  (look 3: luxury soft camel cashmere long trench coat, cream turtleneck, flowing coat tails:1.1),
  natural dynamic poses, studio strobe lighting, crisp fabric seams, photorealistic 8k
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (low quality:1.4), flat lighting, pixelated, jagged lines, disfigured, blurry hands, oversaturated, glitchy edges, watermark
  ```
- **推荐配套参数**：CFG 6.8 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧

---

## 提示词 5：【四季流转与冷暖色温】粉白春日针织 ➔ 碧蓝夏日吊带 ➔ 焦糖冬日皮毛一体夹克

- **测试目标**：测试冷暖环境光随服装整体色调联动的能力，检验肤色在不同穿搭反光下的健康质感。
- **阶段划分**：
  - **Look 1 (0~4s)**：春日柔粉色短款镂空针织衫配白色百褶裙，樱花微风暖调。
  - **Look 2 (4~8s)**：夏日宝蓝渐变挂脖丝绸吊带背心配牛仔短裤，晴空烈日冷调光芒。
  - **Look 3 (8~12s)**：冬日厚重焦糖色麂皮皮毛一体夹克配修身皮裤，雪花微落温润木质暖光。
- **中文综合描述**：
  > 四季换装随律动变幻。春日粉白针织少女元气，夏日宝蓝吊带热情明艳，冬日焦糖色毛绒皮夹克温暖厚重。人物肤色红润透亮，各季节服装材质触感分明。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), four-seasons outfit transition, 1girl dance video, natural progression,
  (part 1: spring pastel blush pink cropped knit sweater, white pleated mini skirt, cherry blossom tones:1.1),
  (part 2: summer royal blue halter silk top, washed denim shorts, bright sunny radiance:1.1),
  (part 3: winter caramel suede shearling jacket with fluffy fur collar, leather pants, soft snow atmosphere:1.1),
  hyperrealistic skin pores, volumetric sunbeams, film grain, depth of field, 8k
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), muddy colors, unnatural skin tone, plasticky texture, extra limbs, bad eyes, watermark
  ```
- **推荐配套参数**：CFG 7.0 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 4 帧
