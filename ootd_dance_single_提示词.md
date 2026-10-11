# WF-2: ootd_dance_single (单套定装长舞 · 连贯长镜头) 测试提示词库

> **工作流定位**：选定一套特定的高保真 OOTD 穿搭，让角色连贯跳完 10~15 秒（96帧）的长镜头舞蹈。段间通过 16 帧滑动窗口与 6 帧重叠进行平滑过渡，确保整条视频中服装细节不崩坏、脸部身份高度统一。  
> **提示词编写原则**：聚焦于**单套服装的版型剪裁、布料物理垂坠感、运动惯性下的褶皱变化以及全局光影一致性**。

---

## 提示词 1：【布料流体与超大摆动】绯红流苏高开叉曳地长裙

- **测试目标**：测试超长软质面料在持续大幅度旋转舞动时，裙摆的流体物理运动是否符合动力学规律，是否会出现布料撕裂、反向拉伸或粘连。
- **OOTD 穿搭配置**：
  - 核心服装：大红色真丝缎面高开叉曳地长礼服，裙摆边缘带有下坠红流苏，后背大露背交错细绑带。
  - 配饰与妆容：深红复古哑光唇妆，黑色极细一字带高跟鞋，珍珠流苏长耳环。
  - 场景光影：古典大剧院舞台暗场，正上方一束暖金色圆形聚光灯，地面带有微反光倒影。
- **中文综合描述**：
  > 顶级电影质感长镜头，红裙女子在聚光灯下独舞。深绯红色的真丝曳地长裙随着她连续的旋转与跳跃在空中画出层层叠叠的红色涟漪，下摆细密流苏随惯性激荡飞扬。聚光灯打在缎面上呈现流动的液体光泽，人物面容高贵冷艳，全程 12 秒动作连贯自然，无任何接缝跳变。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), cinematic long take, photorealistic full body shot, 1girl, 20yo Korean beauty, solo dancing elegantly,
  (wearing stunning crimson red silk satin evening gown:1.2), high side slit, flowing floor-length hemline with swinging tassels, delicate criss-cross back straps,
  fluid dance choreography, dramatic cloth physics, fabric flowing in the air, spinning motion,
  theatre stage backdrop, single warm golden spotlight from above, floor reflection, rim lighting, 8k resolution, raw photo, sharp facial details, consistent identity
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), deformed dress, cloth tearing, clipping, unnatural gravity, stiff fabric, bad hands, missing fingers, inconsistent face, jumps between frames, blurry, watermark
  ```
- **推荐配套参数**：CFG 7.0 | Steps 22 | Sampler: euler | 窗口: 16 帧 / 重叠 6 帧 (pyramid)

---

## 提示词 2：【硬挺面料与结构稳定】经典英伦双排扣风衣与马丁靴

- **测试目标**：检验厚实硬挺风衣面料在大幅度步伐、抬腿与手臂挥动时的折痕物理表现，以及衣领、金属排扣、腰带五金件在全片中是否能保持结构稳定不形变。
- **OOTD 穿搭配置**：
  - 核心服装：英伦经典浅卡其色加厚斜纹棉双排扣风衣，宽腰带系出高腰线，下身搭配黑色修身牛仔长裤与深褐厚底马丁靴。
  - 配饰与妆容：干练低马尾发型，自然清透通勤妆容，金属耳骨夹。
  - 场景光影：黄昏时分的都市现代玻璃广场，地面微湿带雨后反光，冷暖交融的斜阳漫射光。
- **中文综合描述**：
  > 现代都市长镜头舞蹈，身穿经典浅卡其双排扣风衣的干练女子随着节奏大步跳跃律动。厚实棉质风衣衣摆随步伐利落甩动，金属纽扣与腰带扣反射微光，衣领挺括有型。全片 12 秒风衣轮廓稳定扎实，动作干净利落，地面清晰倒映舞姿。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), seamless continuous dance take, photorealistic, 1girl, chic modern dancer,
  (wearing classic British beige double-breasted trench coat:1.2), structured cotton twill fabric, belted waistline, metallic buckles and buttons, black slim-fit denim, dark brown chunky combat boots,
  sharp choreography, realistic coat creases and dynamic flaring,
  urban modern plaza at dusk, wet pavement reflections, sunset amber backlight and cool ambient fill, highly detailed, 8k
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.3), rubbery clothes, morphing buttons, melted belt, distorted boots, bad anatomy, twitching, blurry edges, jitter, text
  ```
- **推荐配套参数**：CFG 6.8 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 6 帧

---

## 提示词 3：【强光折射与高光防闪烁】重工银色星钻人鱼礼服

- **测试目标**：专门针对长视频中最容易出现的“高频噪点闪烁（Boiling Texture）”与“塑料反光”，检验微小碎钻与银色鳞片在全片连续运动中的抗闪烁与高动态范围能力。
- **OOTD 穿搭配置**：
  - 核心服装：重工银灰色密镶碎钻鱼尾裙，修身立体剪裁，随着身体曲线贴合，背部半透深 V 设计。
  - 配饰与妆容：高级水光银眼妆，微卷锁骨发，钻石细手镯。
  - 场景光影：深蓝深邃暗夜星空演播厅，左右两侧冷白顶灯交错照射，点光源微散焦光斑。
- **中文综合描述**：
  > 极具奢华感的光影舞蹈长镜头。银色星钻人鱼裙紧贴女子优美的身段，伴随波浪般柔美的躯干扭动与手势舞动。裙身成千上万颗微小碎钻在多角度光照下呈现出星河般平滑自然的高光流转，无局部闪烁或白噪点，皮肤自然通透。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), breathtaking seamless long sequence, 1girl, solo dancer,
  (wearing luxurious silver sparkling mermaid dress:1.2), densely studded with micro-crystals and diamond sequins, form-fitting silhouette, shimmering fabric texture,
  smooth wave-like dance movements, steady light refraction without boiling,
  dark midnight blue studio backdrop, soft bokeh lights, dual rim studio spotlights, smooth specular highlights, photorealistic skin, 8k uhd
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), flickering artifacts, noisy glitter, chromatic aberration, plastic skin, distorted anatomy, overexposed hot spots, watermark
  ```
- **推荐配套参数**：CFG 7.2 | Steps 25 | Sampler: dpmpp_2m | 窗口: 16 帧 / 重叠 6 帧

---

## 提示词 4：【半透明微观层次】法式复古薄纱蕾丝芭蕾裙

- **测试目标**：检验双层/多层半透明薄纱的透光性、镂空蕾丝微观纹理与内层衬裙的层次堆叠感，在连续跳舞中是否能维持透视关系正确。
- **OOTD 穿搭配置**：
  - 核心服装：法式复古米白半透明双层欧根纱蕾丝裙，胸前刺绣花瓣暗纹，多层蓬松薄纱在腰间层叠。
  - 配饰与妆容：法式法式低盘发，裸粉色温润唇彩，丝带芭蕾平底鞋。
  - 场景光影：午后落地窗柔光大厅，逆光穿透薄纱产生丁达尔圣光效应，轻微空气微尘。
- **中文综合描述**：
  > 优雅浪漫的芭蕾长镜头。米白色轻盈薄纱蕾丝裙随跃起而轻柔蓬起，窗外柔和阳光从身后打来，清晰穿透外层半透明纱质，映出精巧的镂空蕾丝花纹与优雅身姿轮廓。动作如羽毛般轻盈，无任何卡顿。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), lyrical ballet dance long take, 1girl, graceful,
  (wearing vintage cream white semi-translucent tulle lace dress:1.2), layered organza skirt, delicate embroidered floral lace, ribbons, sheer fabric with light transmission,
  fluid balletic leaps and pirouettes, weightless floating cloth physics,
  sunlit grand hall with floor-to-ceiling windows, soft golden hour backlighting, subtle god rays, airy atmosphere, natural skin pores, 8k
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.3), opaque solid white blocks, lost transparency, messy threads, bad feet, malformed limbs, blurry lace, watermark
  ```
- **推荐配套参数**：CFG 6.8 | Steps 22 | Sampler: euler | 窗口: 16 帧 / 重叠 6 帧

---

## 提示词 5：【大动态晃动与肢体遮挡】美式高街棒球夹克与重磅阔腿裤

- **测试目标**：检验街舞（Hip-hop / 编舞动作）中频繁的大幅度手部横穿身体遮挡、下蹲与摆臂时，服装与身体碰撞检测是否准确，是否会发生肢体陷进衣服内部的穿模现象。
- **OOTD 穿搭配置**：
  - 核心服装：撞色拼接美式复古皮质袖棒球夹克（深绿衣身配米白皮袖），内搭白色紧身短背心，下身穿着重磅水洗灰色阔腿工装裤与复古球鞋。
  - 配饰与妆容：反戴黑色棒球帽，银色粗链项链，烟熏眼妆。
  - 场景光影：地下工业风车库，水泥立柱，昏黄顶管射灯，低视角机位仰拍。
- **中文综合描述**：
  > 街舞活力长镜头，女子在车库中央跳起节奏感极强的街舞。宽松拼色棒球夹克与重磅阔腿裤随着强劲的锁舞与律动大幅晃动，手部多次交叉横穿胸前与腰间，夹克开合自然，衣物碰撞折叠真实，无任何肢体穿模。
- **ComfyUI 英文 Positive Prompt**：
  ```text
  (masterpiece, best quality:1.2), dynamic hip-hop dance continuous shot, low angle, 1girl, confident energetic expression,
  (wearing oversized American vintage varsity jacket:1.2), forest green wool body with cream leather sleeves, white cropped tank top underneath, heavy washed grey wide-leg cargo pants, retro sneakers, backwards cap,
  popping and locking choreography, fast hand movements across body, natural cloth collisions without clipping,
  underground industrial concrete garage, overhead neon tube lights, gritty texture, raw photo, 8k
  ```
- **ComfyUI 英文 Negative Prompt**：
  ```text
  (worst quality, low quality:1.4), limb clipping through clothes, missing arms, tangled sleeves, distorted jacket, bad fingers, unnatural deformation, blurry motion, watermark
  ```
- **推荐配套参数**：CFG 7.0 | Steps 20 | Sampler: euler | 窗口: 16 帧 / 重叠 6 帧
