# 动作克隆（Motion Clone / Motion Transfer）方案调研文档

> 面向初学者级开发者。目标读者读完本文后，能理解整体原理，并按本文给出的步骤在本机复现一套「动作克隆」流水线。
>
> 文档语言：中文为主，技术术语、命令、模型文件名保留英文。

---

## 1. 总览与目标

### 1.1 我们要做什么

**一句话目标**：给一张**新人物图 / 新角色**，再给一段**参考视频（比如一支舞蹈）**，让这个新角色**精确复刻**参考视频里的舞蹈 / 动作，生成一段新的视频。

举例：
- 素材 A：一张你不认识的人的照片（或 AI 生成的角色图）。
- 素材 B：一段网红舞蹈视频（原视频里是另一个人）。
- 输出：**素材 A 里的人物** 跳 **素材 B 里的那支舞**，动作节奏、姿势、手臂与腿部姿势都跟着原视频走。

### 1.2 关键难点：为什么不能"一句话搞定"

如果只是把参考视频丢给视频生成模型并写一句"让这个人跳这段舞"，是**做不到帧级复刻**的。原因是视频生成模型（文生视频 / 图生视频）本质是"根据语义描述自由发挥"，它：
- 会自己"脑补"动作幅度、节奏、身体朝向，导致相似但不精确；
- 无法保证第 37 帧抬左手、第 52 帧转身 180° 这种**逐帧精确**对应；
- 一遇到节奏快、自旋、大幅度舞动，输出容易糊掉或人物变形。

**要精确复刻，必须把"动作信息"从原视频里显式提取出来，再作为强约束喂给下游生成器。** 这就引出了本文的核心架构：**双轨**。

### 1.3 为什么需要「语义 + 骨架」双轨

| 轨道 | 提取什么 | 解决什么问题 | 产物 |
| --- | --- | --- | --- |
| 轨道一：LLM 语义解析 | 场景 / 服饰 / 光影 / 镜头运动的**文字描述** | 让下游生成器知道"画面长什么样、什么风格、什么画质" | 英文 Prompt |
| 轨道二：Pose 骨架提取 | 人体各关节的**逐帧精确坐标** | 让下游生成器知道"每一帧身体摆成什么样" | OpenPose 骨架图 / 骨架视频 / JSON |

两条轨道**缺一不可**：
- 只有语义、没有骨架 → 动作只能"大概像"，不精确（即 1.2 的问题）。
- 只有骨架、没有语义 → 动作对了，但画面可能是粗糙的骨架色块风、画质差、背景全丢。

**双轨合并**：把「语义 Prompt」填进视频生成模型的正向提示词，把「骨架序列」通过 ControlNet 注入，两者共同约束生成结果。

---

## 2. 双轨架构详解

整体数据流：

```
参考视频
   │
   ├──► 抽关键帧 ──► 视觉大模型(LLM) ──► 英文 Prompt (prompt.json / prompt.txt)
   │                                              │
   │                                              ▼
   └──► 逐帧 Pose 推理 ──► 平滑 ──► 骨架渲染 ──► OpenPose 骨架序列 (pose_frames/ + pose.mp4)
                                                  │
                                                  ▼
                              下游视频生成器（正向 Prompt + OpenPose ControlNet）
                                                  │
                                                  ▼
                                        新角色复刻动作的视频
```

### 2.1 轨道一：LLM 语义解析

**目的**：把原视频里的"非动作"信息翻译成下游生成器能读懂的英文 Prompt。

**步骤**：
1. **抽关键帧**：从参考视频中按固定间隔（例如每 1 秒 1 帧，或按场景变化）抽出一小组代表性帧，保存到 `keyframes/`。
   - 不要抽太多帧，视觉大模型推理很慢；通常 8~16 张足够描述整段视频的场景与风格。
2. **交给视觉大模型描述**：把关键帧喂给视觉大模型（本机可用模型见第 7 节），让它输出：
   - 场景 / 背景（scene, background）
   - 人物服饰（clothing, outfit）
   - 光影 / 色调（lighting, color tone）
   - 镜头运动（camera movement，如固定机位、推拉、环绕）
   - 画面风格与画质（style, quality）
3. **产出下游 Prompt**：把上面的描述整理成一段结构化英文 Prompt，写入 `prompt.json`（结构化字段）和 `prompt.txt`（可直接粘贴的一段话）。
   - 注意：**这一段 Prompt 描述"画面"，不描述"动作"。动作由骨架轨道负责。**

**为什么用英文 Prompt**：主流图像 / 视频生成模型（SD 系、AnimateDiff 等）对英文提示词的响应更稳定、更精准。

### 2.2 轨道二：Pose 骨架提取

**目的**：把"每一帧身体摆成什么样"变成机器可读、且能被 ControlNet 直接消费的**骨架图**。

**步骤**：
1. **逐帧推理关键点**：对参考视频的每一帧，运行姿态估计模型，输出人体关键点坐标。
   - 常见的关键点数量：**17 点**（COCO 标准人体骨架，YOLOv8-Pose 常用）或 **18 点**（OpenPose BODY_18）。
   - 若后端支持，还会额外输出**手部 21×2 点**和**脸部 68/70 点**（DWPose 支持）。
2. **平滑（去抖）**：原始关键点会抖动（见第 4 节），需要用滤波（如卡尔曼滤波）平滑坐标序列。
3. **渲染骨架图**：把关键点坐标画成 OpenPose 风格的彩色骨架（彩色圆点 + 连线，"彩色小棒人"），逐帧保存到 `pose_frames/`，并合成为骨架视频 `pose.mp4`。
4. **落盘 JSON**：把平滑后的关键点坐标存成 `keypoints.json`，方便调试和复用。
5. **作为 ControlNet 的 control image**：`pose_frames/` 里的每一张骨架 PNG，就是 OpenPose ControlNet 的输入图。骨架视频 `pose.mp4` 则对齐下游视频生成的逐帧条件。

### 2.3 为什么 LLM 不能替代 Pose（重点）

这是初学者最容易误解的地方，务必理解：

- **LLM 懂"语义"，不懂"欧几里得空间的精确坐标"**。你让它"描述一个人在跳舞"，它能写出漂亮的文字；但你让它输出"第 37 帧左手腕在画面 (412, 288) 像素、肘部角度 143°"，它做不到，也给不准。
- **文字描述是"离散的、模糊的"，动作是"连续的、逐帧的"**。一段 10 秒 30fps 的舞蹈有 300 帧，每一帧的姿势都需要精确对应。用文字描述 300 帧的姿势，既不现实，也不可能精确。
- **纯文字无法做到 frame-by-frame 复刻**。LLM 出来的 Prompt 只能约束"风格和语义倾向"，而 ControlNet 骨架图才能提供"帧级几何约束"。
- 结论：**LLM 负责"像不像那个场景"，Pose 负责"动作对不对"。二者是互补，不是替代。**

---

## 3. 姿态后端选型对比

本机候选姿态后端有三个：**DWPose**、**YOLOv8-Pose**、**MediaPipe**。对比如下：

| 维度 | DWPose | YOLOv8-Pose | MediaPipe |
| --- | --- | --- | --- |
| 关键点数量 | 18 点（BODY_18）+ 手 21×2 + 脸 68 | 17 点（COCO） | 33 点（Pose 模型，另有 Holistic 可含手/脸） |
| 是否含手部/脸部关键点 | **是**（自带手 + 脸，精度高） | 否（仅 17 点身体） | 可选（Holistic 模式含手/脸，但集成相对麻烦） |
| 抖动（jittering）表现 | 较好，配合平滑后稳定 | 一般，快速运动抖动较明显 | 一般，遮挡时易跳点 |
| 显存/算力占用 | 中等（onnxruntime-gpu 推理，占一部分显存） | 较低（轻量，速度快） | 很低（CPU 也可跑，但 GPU 更快） |
| 本机权重是否齐备 | **是**，权重已存在本机 | 否，需首次下载权重 | 依赖 pip 包自带模型，首次运行会下载 |
| 输出是否可直接被 OpenPose ControlNet 消费 | **是**，输出即 OpenPose 格式 | 需自行转成 OpenPose 18 点格式 | 需自行转换坐标格式 |

### 默认选型结论

**首选 DWPose**，理由：
1. 本机 `custom_nodes/comfyui_controlnet_aux` 下的 `yzd-v/DWPose` 权重**已齐备**，无需下载即可用。
2. 它**包含手部与脸部关键点**，对手势丰富的舞蹈动作更友好。
3. 它的输出**本身就是 OpenPose 格式**，能被 OpenPose ControlNet 直接消费，省去格式转换。
4. 精度**高于 YOLOv8-Pose 的 17 点**（尤其在手部、脸部、遮挡场景下差异明显）。

**备选：YOLOv8-Pose**（轻量方案）：
- 本机已安装 `ultralytics` 8.4.58，代码层面可直接调用。
- 但**需首次下载权重**（如 `yolov8n-pose.pt`）。
- 只有 17 点、无手脸关键点，输出需转换才能给 OpenPose ControlNet。

**MediaPipe** 作为兜底：CPU 也能跑，适合快速验证，但格式转换与集成成本较高，不作为首选。

---

## 4. 遮挡与转身鲁棒性

### 4.1 成因：为什么舞者一动就"抽风"

2D 单目姿态估计（从单张图推断 3D 人体）在以下场景极易出错，这是**原理性缺陷，不是 bug**：

- **舞者背对镜头**：模型主要靠"看脸/看正面"来区分左右，背对时**会把左右手搞反**。
- **手被身体遮挡**：关键点缺乏视觉证据，模型会**猜测**，导致关键点跳到错误位置。
- **快速自旋 / 大动作**：帧间位移大，逐帧独立推理导致**高频抖动（jittering）**——同一只手在相邻帧来回小幅乱跳。
- **检测目标逐帧"闪烁"**：某些帧检测到人、某些帧漏检，导致骨架时有时无。

### 4.2 缓解手段（每条都点名具体做法）

| 手段 | 具体做法 | 解决什么 |
| --- | --- | --- |
| 卡尔曼滤波平滑 | 对每个关键点的 (x, y) 序列跑卡尔曼滤波（本项目已装 `filterpy`），用运动模型预测 + 观测校正，输出平滑轨迹 | 抑制逐帧高频抖动 |
| 置信度阈值丢弃 | 对每个关键点设一个置信度阈值（如 0.3），低于阈值的关键点标记为"不可信"，不参与渲染 | 避免把错误的关键点画进骨架 |
| 跨帧 ID 关联 | 用简单 IOU 追踪或 ReID（行人重识别）把相邻帧的同一个人关联起来，保证骨架绑定到同一个人 | 解决"逐帧闪烁"、目标跳变 |
| 左右手后处理交换判定 | 结合"肩—肘—腕"的几何关系、画面中人体朝向判断，在检测到转身时对左右手关键点做交换，纠正左右反判 | 缓解背对镜头时左右手搞反 |
| 时间窗口中值滤波 | 在时间维上对每个关键点取滑动窗口（如 ±3 帧）的中位数 | 去除单帧的突发跳点（脉冲噪声） |

### 4.3 这些手段的局限

- **卡尔曼滤波**：假设运动平滑；遇到真实的**急停、瞬移、快节奏定格**动作，平滑反而会"拖尾"、丢失真实动作。
- **置信度阈值**：阈值太低 → 脏点留下；阈值太高 → 遮挡时关键点大量丢失，骨架断裂。
- **ID 关联 / IOU 追踪**：快速大位移 + 多人同框时，IOU 会失效、ID 会串；ReID 又重又慢。
- **左右手交换判定**：转身是**渐变**过程，判定本身就可能误判，边界帧尤其容易出错。
- **中值滤波**：窗口太大会把真实的手部快速小动作滤掉。

**结论**：这些手段都是"缓解"而非"根治"。真正的解法是**用带手/脸、鲁棒性更强的后端（DWPose）+ 多手段叠加**，并接受"极端镜头下仍会有瑕疵"。

---

## 5. 下游渲染三路线对比

把双轨产物（Prompt + 骨架）变成最终视频，有多条候选路线。下表为本机**实测结论**（"本机可用性"一列已由推测改为实测）：

| 路线 | 方案 | 优点 | 缺点 | 本机可用性（实测结论） |
| --- | --- | --- | --- | --- |
| A | ComfyUI + AnimateDiff + ControlNet(OpenPose) | 全本地、免费、可控性强、可精细调参 | 需要自己搭工作流、对显存有要求、效果依赖调参 | **已实测可用**：3 个模型已补齐、节点已启用；重启后 `/object_info` 实测 `ADE_*` 节点 143 个（与离线预测 143 完全吻合），AnimateDiff + ControlNet(OpenPose) 冒烟 `status_str=success`、`completed=true`，耗时约 83.9 秒（详见本节与第 9 节实测记录） |
| B | 商业视频模型（Runway Gen-3、Kling 等） | 上手快、画质高、省算力 | 收费、需联网、动作复刻精度与可控性受限 | 需联网 + 账号，本机无本地依赖 |
| C | Live3D / 虚拟主播（VSeeFace、Warudo） | 实时驱动、可互动、适合直播虚拟主播 | 需要 VRM 模型、需 3D 化或坐标映射、非"出片"方案 | **本次未纳入（第三方软件 + OSC）**：属第三方 Windows 软件 + OSC 实时推流，非 ComfyUI 节点/模型范畴，留作后续独立 spec |
| D | ComfyUI + Wan2.2 Animate 14B（**本次主线，本机已实现**） | 全本地、免费、骨架 + 角色图直接驱动、动作复刻精度高 | 单次渲染慢（49 帧约 40.7 分钟）、显存吃紧需 `--lowvram`、与其它 GPU 任务不可并发 | **可用**：已实测 `status_str=success`、`completed=true`，提交与运行期均未 OOM |
| MimicMotion | ComfyUI + MimicMotion（参考角色图 + 驱动视频 → 动作克隆） | 全本地、免费、直接克隆驱动视频的动作与姿态 | 单次渲染慢（16 帧约 6.2 分钟）、需预下载合并 UNet 与 SVD 组件 | **已实测可用**：冒烟 `status_str=success`、`completed=true`（见本节 MimicMotion 小节与第 9 节实测记录） |

### 选型速查：三条路线怎么选

上面的对比表只回答了「每条路线长什么样」，这一小节回答「你到底该选哪条」。先把三条路线的**实测画像**摆在一起（全部取自本机实测，未做任何外推）：

| 维度 | AnimateDiff + ControlNet(OpenPose) | MimicMotion | Wan2.2 Animate 14B（Move） |
| --- | --- | --- | --- |
| 吃进去的输入 | **OpenPose 骨架序列**（可由上一阶段 `pose_extract.py` 产出） | 参考角色图 + **原始驱动视频**（必须在像素上能跑出姿态） | 参考角色图 + **原始驱动视频**（`internal` 模式）；`ours` 模式**也可只吃骨架**（见下方判据 1） |
| 是否需要前置步骤 | **需要先做骨架提取**（219 帧 DWPose 约 365 秒） | 不需要 | 不需要（`ours` 模式则需先有 `keypoints.json`） |
| 姿态从哪来 | 你提供的骨架 | 节点内部跑 DWPose | 节点内部跑 DWPose（分别产出 `face_video` 与 `pose_video`）；`ours` 模式可改用你的骨架重绘这两路 |
| 模型体量 | 约 7.4 GB（SD1.5 底模 4.27 + 运动模块 1.67 + OpenPose ControlNet 1.45） | 约 4.5 GB（UNet 3.05 + SVD 组件 1.46） | **17.55 GB**（最重） |
| 实测出片 | 16 帧 → **16 帧 / 8 fps / 512×768**，耗时 **83.9 秒** | 16 帧 → **16 帧 / 12 fps / 576×576**，耗时 **372.0 秒** | 基线 49 帧 @512×512 约 **40.7 分钟**；本轮 13 帧约 **37.8 分钟** |
| 画风倾向 | **写实/动漫均可**（SD1.5 生态，可换底模/LoRA 做风格化） | 写实向（SVD 系） | 写实向（官方 Wan2.2 Animate） |
| 身份一致性机制 | 靠提示词（+ 可选 LoRA），**无专门的身份锚点** | 参考图的图像嵌入（image embedding） | 参考图 + CLIP Vision + **专门的 `face_video` 通道** |
| 原生音频 | **无** | 无（`VHS_VideoCombine` 有可选 `audio` 输入但当前未接） | **有**（`CreateVideo` 会把驱动视频的音频一起合成） |
| 输出画幅怎么定 | 由 `--width/--height` 直接指定 | **跟随参考图**（参考图是正方形 → 输出 576×576） | 由 `width/height` 指定，**必须为 16 的倍数** |
| 长度限制 | 单窗口 16 帧；更长需 context options 或分段 | 用 `context_size`(16)/`context_overlap`(6) 分窗口，可做更长 | `length` 必须满足 **`length % 4 == 1`**（如 9/17/25/33/41/49）；输出帧数 = `4×latent+1` |

**一条关键的时间认知（必须写清，否则会误判路线快慢）**：Wan2.2 Animate 那 37.8 分钟里**绝大部分是 17.55GB FP8 模型的加载开销**，不是扩散推理。证据是同一会话里紧接着跑第二个任务时，`/history` 的 `execution_cached` 显示模型加载节点 `1~9` 全部命中缓存，**同一链路只花了 31.5 秒**。→ 所以：**Wan2.2 Animate 的「首次」成本高，「连续第二次」成本很低。** 决策时要按「你是跑一条还是跑一批」来权衡。

#### 怎么选（按优先级从上到下）

1. **你手上只有骨架、没有原始驱动视频** → 优先 **AnimateDiff + ControlNet**（它就是为骨架设计的，直接吃 `pose.mp4` / `pose_frames/`）。
   - **补充（容易误解，务必分清）**：**Wan2.2 Animate 其实也能只吃骨架**——它的 `ours` 模式就是拿 `keypoints.json` 重绘出的两路控制视频替换内置 DWPose 支路的（`pose_video` 来自身体+双手，`face_video` 来自仅脸），已实测跑通；只是仍要给它一个 `--video`（仅用于取音频与 fps，不参与姿态）。
   - **MimicMotion 则必须吃真实视频**：它是在**像素上**跑 DWPose 的，喂进去一张骨架图会检测失败。
2. **你要动漫/风格化画风** → **AnimateDiff + ControlNet**（SD1.5 生态可换底模与 LoRA；两条 Wan 系都是写实向）。
3. **你要「就是同一个人」——身份 + 表情都要像，还要保留原视频音频** → **Wan2.2 Animate 14B**。
4. **想最快看到效果、不想做任何前置准备** → **MimicMotion**（无需前置步骤，16 帧约 6.2 分钟）。
5. **要跑一批（同一会话连续多条）** → **Wan2.2 Animate**（模型加载被摊薄后单条极快）。
6. **时间/显存最省、且能接受先花几分钟提骨架** → **AnimateDiff + ControlNet**（模型 7.4GB，16 帧 84 秒）。
7. **要更长时长** → MimicMotion（context 窗口）或 Wan2.2 Animate（原生 `continue_motion` 分段）；AnimateDiff 单窗口 16 帧需额外 context options。

#### 给初学者的推荐默认路径

先用 **MimicMotion** 跑通一遍（最省事、不用前置、6 分钟左右出片），确认「参考图 + 驱动视频」这套输入与输出契约都对；再按上面 1~3 条的分歧点切到 AnimateDiff（要风格化/只有骨架）或 Wan2.2 Animate（要身份+表情+音频）。

#### 注意事项

- **三条路线不要并发**：16GB 单实例，Wan 系模型很重，并发会显存打满。
- **三条路线的 UI 工作流都已在侧边栏就绪**：`animatediff_openpose_sd15_ui`、`mimicmotion_ui`、`wan22_animate_move_ui`。
- AnimateDiff 那条要先有骨架：跑 `pose_extract.py` 得到 `pose.mp4` / `pose_frames/` 作为 ControlNet 控制信号。
- MimicMotion 的输出画幅跟随参考图；若参考图是正方形就会出正方形成片（想竖屏就换竖构图参考图，或把参考图缩放节点的 `keep_proportion` 改成 `false`）。

### 路线 A：ComfyUI + AnimateDiff + ControlNet(OpenPose)

**本机可用性（实测结论）：已实测可用**。模型已补齐 + 节点已启用，重启后 `/object_info` 实测 `ADE_*` 节点 **143 个**，且 AnimateDiff + ControlNet(OpenPose) 冒烟跑通（`status_str=success`、`completed=true`，耗时约 83.9 秒）。本次已完成重启与真实冒烟，证据见第 9 节「AnimateDiff + ControlNet 路线实测（2026-10-02）」。

本次已补齐 3 个模型（文件名 + 目录 + 字节数）：

| 模型 | 目录 | 字节数 | 来源 |
| --- | --- | --- | --- |
| `v1-5-pruned-emaonly.safetensors` | `models/checkpoints/` | 4,265,146,304（4.27 GB） | `stable-diffusion-v1-5/stable-diffusion-v1-5` |
| `v3_sd15_mm.ckpt` | `models/animatediff_models/` | 1,673,262,583（1.67 GB） | `guoyww/animatediff` |
| `control_v11p_sd15_openpose.pth` | `models/controlnet/` | 1,445,235,707（1.45 GB） | `lllyasviel/ControlNet-v1-1` |

> 注：`models/animatediff_models/` 目录此前**不存在**，本次新建。

**节点启用**：
- `custom_nodes/ComfyUI-AnimateDiff-Evolved.disabled` 已改名为 `custom_nodes/ComfyUI-AnimateDiff-Evolved`（**仅去后缀改名，可逆**）；改名前后递归文件数均为 **109**、目录内容零改动。
- **离线验证**（在独立子进程里做）：import 成功，共 **145 个节点 schema，其中 `ADE_*` 143 个**，含 `ADE_LoadAnimateDiffModel`、`ADE_AnimateDiffLoaderWithContext`、`ADE_AnimateDiffCombine`。
- **避坑**：该版本用的是新版 V3 `comfy_entrypoint` API，**不存在模块级 `NODE_CLASS_MAPPINGS`**，验证需通过 `comfy_entrypoint()` → `get_node_list()` → `define_schema().node_id`。

**重启核验（已完成）**：ComfyUI **只在启动时**扫描 `custom_nodes`，因此节点必须重启后才会在运行期生效。本次已用项目自带启动器 `start_comfyui.bat` 重启，重启后 `GET /object_info` **实测 `ADE_*` 节点正好 143 个**，与重启前的离线预测完全吻合；关键节点 `ADE_LoadAnimateDiffModel`、`ADE_AnimateDiffLoaderGen1`、`ADE_AnimateDiffLoaderWithContext`、`ADE_AnimateDiffCombine`、`ADE_AnimateDiffSamplingSettings`、`ADE_StandardUniformContextOptions` 均在册。证据详见第 9 节「AnimateDiff + ControlNet 路线实测（2026-10-02）」。

> **环境认知（避免以后困惑）**：本机 `venv\Scripts\python.exe` 是**重定向桩**，它会派生出 anaconda 解释器作为**子进程**去跑真正的服务。因此 `Get-CimInstance Win32_Process` 会看到**两个**参数完全相同的 python 进程，**真正监听 8188 的是 anaconda 那个子进程**（重启前 PID 26004，重启后 PID 35100）。杀进程时两个都要处理。

**落地步骤**：
1. 确认 ComfyUI 已重启、`ADE_*` 节点在 `/object_info` 中可见（本次已完成）。
2. 在 ComfyUI 中搭建工作流。**AnimateDiff v3 用的是 Gen2 接口**，实际跑通的节点链为：
   `CheckpointLoaderSimple`(v1-5-pruned-emaonly) → `CLIPTextEncode`×2；`ADE_LoadAnimateDiffModel`(v3_sd15_mm.ckpt) → `ADE_ApplyAnimateDiffModelSimple` → `ADE_UseEvolvedSampling`；`ControlNetLoader`(control_v11p_sd15_openpose) → `ControlNetApplyAdvanced`；`VHS_LoadVideo` → `ImageScale(center)` → `EmptyLatentImage` → `KSampler` → `VAEDecode` → `VHS_VideoCombine`。
   - SD1.5 底模选 `v1-5-pruned-emaonly.safetensors`。
   - 正向提示词：填入轨道一产出的 **Prompt**。
   - 控制输入：把轨道二产出的**骨架序列**（骨架视频 `pose.mp4`）接入 **OpenPose ControlNet**（`control_v11p_sd15_openpose.pth`），经 `ImageScale(crop=center)` 缩放到目标分辨率后送入 `ControlNetApplyAdvanced`。
   - **实现坑（避免后来者踩坑）**：`ADE_AnimateDiffLoaderGen1` 与 `ADE_AnimateDiffLoaderWithContext` **只接受 `model_name`(COMBO)，没有 MOTION_MODEL 输入槽**，无法消费 `ADE_LoadAnimateDiffModel` 的输出，会产生孤立节点；因此必须改用 Gen2 的 `ADE_ApplyAnimateDiffModelSimple` + `ADE_UseEvolvedSampling` 这条链。
3. 采样出片，检查动作是否跟随骨架、画面是否符合 Prompt 描述。

### 路线 B：商业视频模型的图生视频 / 动作参考 / 运动画笔

**落地步骤**：
1. 上传**新人物图**作为首帧 / 参考图（image-to-video）。
2. 上传**参考视频**（部分模型支持"动作参考 / Motion Reference"），或使用"运动画笔 / Motion Brush"手动圈出需要运动的区域。
3. 把轨道一产出的 **Prompt** 填进文本提示，生成视频。
4. 注意：商业模型的动作复刻精度**不如本地 ControlNet 骨架约束**，适合作为快速对比方案。

### 路线 C：Live3D / 虚拟主播（VSeeFace、Warudo）

> **不在本次范围**：它不是 ComfyUI 节点或模型，而是第三方 Windows 软件（VSeeFace、Warudo）配合 OSC 实时推流，与「补齐节点模型」不是同类工作，留作后续独立 spec。以下为方案描述，保持原样。

**落地步骤**：
1. 准备一个 **VRM 模型**（虚拟形象）。
2. 把 2D 关键点坐标映射成驱动信号；若要走 3D，可先做 2D→3D 升维（或直接用 3D 姿态模型）。
3. 通过 **OSC 协议**把驱动信号发送给 VSeeFace / Warudo，实时驱动 VRM 模型跳舞。
4. 这是**实时互动**方案，不是"出片"方案，但适合直播虚拟主播场景。

### 路线 D：Wan2.2 Animate 14B —— 已验证可跑（本次主线）

本机当前**唯一实测可跑**的本地渲染路线。冒烟实测数据如下（均取自本次运行）：

- `prompt_id = e081b7ee-d7f6-41a6-9e31-653934b24d49`，`status_str = success`，`completed = true`。
- 耗时：`1790899021663 → 1790901466239 = 2444.6 秒 ≈ 40.7 分钟`（**49 帧 @512×512，4 步**）。
- 产物：`output/2026-10-02/wan22_animate/move_smoke_00001_.mp4`（0.44MB）。
- **提交与运行期均未 OOM**；ComfyUI 以 `--lowvram` 启动（**这一点是关键前提**，17.5GB 的 FP8 模型才能在本机 16GB 卡上跑）。
- 模型 6 件齐全：
  - `diffusion_models/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors`（17.55GB）
  - `text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`
  - `clip_vision/clip_vision_h.safetensors`
  - `vae/wan_2.1_vae.safetensors`
  - `loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`
  - `loras/WanAnimate_relight_lora_fp16.safetensors`
- 工作流：`workflows/wan22_animate/wan22_animate_14b_move_api.json`（**21 节点 / 18 种 class_type**，与 `/object_info` 比对**零缺失**）。

**代码约束（避坑）**：`WanAnimateToVideo` 要求 `width` / `height` 为 **16 的整数倍**、`length` 满足 **`length % 4 == 1`**（可用值如 9 / 17 / 25 / 33 / 41 / 49）。

### MimicMotion —— 已实测可用

- `custom_nodes/ComfyUI-MimicMotionWrapper` **已启用**，且 `custom_nodes/ComfyUI-MimicMotionWrapper/models/` 下有 `mimic_motion_pose_net.safetensors`（0.4MB）与 DWPose torchscript。
- 本次已补齐主 UNet 与 SVD 组件：

| 文件 | 目录 | 字节数 |
| --- | --- | --- |
| `MimicMotionMergedUnet_1-1-fp16.safetensors` | `models/mimicmotion/` | 3,049,435,868（3.05 GB） |
| `vae/diffusion_pytorch_model.fp16.safetensors` | `models/diffusers/stable-video-diffusion-img2vid-xt-1-1/` | 195,531,910 |
| `image_encoder/model.fp16.safetensors` | `models/diffusers/stable-video-diffusion-img2vid-xt-1-1/` | 1,264,217,240 |

  （`models/diffusers/stable-video-diffusion-img2vid-xt-1-1/` 下共 **7 个文件（不含 unet）**，另含 `model_index.json`、`vae/config.json`、`image_encoder/config.json`、`scheduler/scheduler_config.json`、`feature_extractor/preprocessor_config.json`。）

- 来源：主 UNet 取自 `Kijai/MimicMotion_pruned`。
- **重要坑**：官方的 `stabilityai/stable-video-diffusion-img2vid-xt-1-1` 是 **401 gated**（需 token）；本机改用**非 gated** 的 `vdo/stable-video-diffusion-img2vid-xt-1-1`——这正是 MimicMotion 节点自身指定的镜像。
- 冒烟实测见第 9 节「渲染路线模型补齐实测（2026-10-02）」。

### 本机当前可用项（事实记录）

- `custom_nodes/ComfyUI-MimicMotionWrapper` **已启用**，主 UNet 与 SVD 组件已补齐，**已实测可用**（见上一小节）。
- `custom_nodes/ComfyUI-AnimateDiff-Evolved` **已启用**（去掉 `.disabled` 后缀），重启后 `/object_info` 实测 `ADE_*` 节点 143 个，**已实测可用**（见路线 A 与第 9 节 AnimateDiff 实测）。
- `custom_nodes/ComfyUI-VideoHelperSuite` **已启用**（用于视频读写、帧合成等）。

### 骨架产物如何接入 ControlNet

本仓库产出的骨架序列 `pose_frames/`（逐帧 PNG）**可直接作为 OpenPose ControlNet 的 control image 输入**。也可以先由 VideoHelperSuite 把 `pose_frames/` 合成为 `pose.mp4`，在需要视频形式条件的场景下使用。

### 本机已实现的渲染调用方式

路线 D（Wan2.2 Animate 14B）已封装为 `tools/motion_clone/render_wan_animate.py`，两种模式的可复制命令如下。

**internal 模式**（默认，工作流内部自己做 DWPose 预处理）：

```powershell
& "d:\ai_projects\ComfyUI\venv\Scripts\python.exe" "d:\ai_projects\ComfyUI\tools\motion_clone\render_wan_animate.py" `
  --pose-mode internal --length 49 `
  --ref-image "<新角色图>" --video "<参考舞蹈视频>" `
  --project-dir "output\<日期>\motion_clone\<项目名>"
```

**ours 模式**（用上一阶段 `keypoints.json` 重绘的骨架替换工作流内置 DWPose 支路）：

```powershell
& "d:\ai_projects\ComfyUI\venv\Scripts\python.exe" "d:\ai_projects\ComfyUI\tools\motion_clone\render_wan_animate.py" `
  --pose-mode ours --length 49 `
  --ref-image "<新角色图>" --video "<参考舞蹈视频>" `
  --project-dir "output\<日期>\motion_clone\<项目名>"
```

参数与产物说明：

- 加 `--dry-run` 可只做注入与校验、**不提交**（推荐先干跑）。
- `--length` / `--width` / `--height` / `--steps` / `--seed` / `--frame-offset` 可覆盖默认值（默认 **49 / 512 / 512 / 4 / 20261002 / 0**）。
- 产物落在 `output/<日期>/motion_clone_render/<项目名>/`：成片 `<前缀>_00001_.mp4`、提交记录 `render_submit.json`，ours 模式另有两路控制视频 `control/pose_*.mp4` 与 `control/face_*.mp4`。
- **结果查询方式**：脚本提交后只打印 `prompt_id` 与预计完成时间，**不轮询**；稍后手动查询一次即可：

```powershell
Invoke-RestMethod "http://127.0.0.1:8188/history/<prompt_id>" | ConvertTo-Json -Depth 6
```

- 提醒：单次渲染约 **40 分钟（49 帧）**，期间不要与其它 GPU 任务并发（16GB 单实例）。

**补齐渲染路线缺失模型**（先干跑看计划，再实际下载；支持断点续传，重跑即续传）：

```powershell
# 补齐渲染路线缺失模型（先干跑看计划，再实际下载；支持断点续传，重跑即续传）
& "d:\ai_projects\ComfyUI\venv\Scripts\python.exe" "d:\ai_projects\ComfyUI\tools\motion_clone\download_route_models.py" --dry-run
```

**MimicMotion 渲染**（参考角色图 + 驱动视频 → 动作克隆视频）：

```powershell
# MimicMotion 渲染（参考角色图 + 驱动视频 → 动作克隆视频）
& "...python.exe" "...\render_mimicmotion.py" `
  --ref-image "<参考角色图>" --video "<驱动视频>" `
  --length 16 --width 576 --height 1024
```

本次新增的脚本与工作流说明：

- 补模型脚本 `tools/motion_clone/download_route_models.py`：支持 `--dry-run`（只列计划）、`--only`、断点续传、hf-mirror 优先 → huggingface.co 回退。
- MimicMotion 提交脚本 `tools/motion_clone/render_mimicmotion.py`；API 格式工作流 `workflows/mimicmotion/mimic_motion_api.json`（**9 节点 / 8 类**，与 `/object_info` 比对零缺失）。
- **UI（画布）格式工作流**：`workflows/mimicmotion/mimic_motion_ui.json`，同时已放到 `user/default/workflows/mimicmotion_ui.json`，**打开 ComfyUI 在左侧「工作流」侧边栏即可直接点开**（9 节点 / 10 连线，带中文标题）。
  - 与 API 版的**唯一差别是两处输入值**：API 版留占位串（`INSTREAM_REF_IMAGE` / `INSTREAM_DRIVING_VIDEO`）供 `render_mimicmotion.py` 注入；UI 版**已预填可选的真实示例**（`video_wan2_2_14B_animate_reference_image.png` 与 `video_wan2_2_14B_animate_original_video.mp4`），因此打开后可直接跑，无需先改输入。输出前缀也改为 `motion_clone_render/mimicmotion_ui`（CLI 跑时会自动按日期落盘，UI 手工跑则落在该分组下）。
  - 生成方式同 AnimateDiff：`tools/api2canvas.py` 转换 + 加中文标题 + 自适应视野。
  - 已做**保真度校验**：UI 图 10 条连线逐条回查 API 图，节点类型与连线两端（节点+槽位）全部一致，结构零错误。
  - 已做**浏览器真机验证**：侧边栏可见、加载出 9 节点、9 个中文标题全部识别、无任何报错；且预填值确认生效——参考图缩略图与驱动视频首帧预览都实际加载出来了（网络请求命中 `/api/view?...` 与 `/api/vhs/queryvideo?...`）。
- MimicMotion 产物落在 `output/<日期>/motion_clone_render/<项目名>_mimicmotion/`：成片 `mimicmotion_00001.mp4` + 提交记录 `render_submit.json`；加 `--dry-run` 可只校验不提交。
- 结果查询同 Wan 路线：脚本只打印 `prompt_id` 与预计完成时间、**不轮询**，稍后手动查一次：

```powershell
Invoke-RestMethod "http://127.0.0.1:8188/history/<prompt_id>" | ConvertTo-Json -Depth 6
```

**AnimateDiff + ControlNet(OpenPose) 渲染**（用上一阶段的骨架视频驱动 SD1.5 出片，**需 ComfyUI 已重启并加载 `ADE_*` 节点**）：

```powershell
# AnimateDiff + ControlNet(OpenPose) 动作迁移：用上一阶段的骨架视频驱动 SD1.5 出片
& "d:\ai_projects\ComfyUI\venv\Scripts\python.exe" "d:\ai_projects\ComfyUI\tools\motion_clone\render_animatediff.py" `
  --pose-video "output\<日期>\motion_clone\<项目名>\pose.mp4" `
  --length 16 --width 512 --height 768
```

参数与产物说明：

- 加 `--dry-run` 可只校验不提交。
- 可调：`--length`（默认 16，建议 4 的倍数）、`--width`/`--height`（默认 512/768）、`--steps`（20）、`--cfg`（7.5）、`--seed`（42）、`--motion-model`、`--ckpt`。
- 产物落在 `output/<日期>/motion_clone_render/<项目名>_animatediff/`：成片 `<前缀>_00001.mp4` + 提交记录 `render_submit.json`。
- 结果查询：脚本只打印 `prompt_id` 与预计完成时间、**不轮询**，稍后手动查一次：

```powershell
Invoke-RestMethod "http://127.0.0.1:8188/history/<prompt_id>" | ConvertTo-Json -Depth 6
```

本次新增的脚本与工作流（AnimateDiff 侧）：

- 提交脚本 `tools/motion_clone/render_animatediff.py`；API 格式工作流 `workflows/animatediff/animatediff_openpose_sd15_api.json`。
- **UI（画布）格式工作流**：`workflows/animatediff/animatediff_openpose_sd15_ui.json`，同时已放到 `user/default/workflows/animatediff_openpose_sd15_ui.json`，因此**打开 ComfyUI 后在左侧「工作流」侧边栏里就能直接看到并点开**（14 节点 / 17 连线，节点带中文标题，已适应视野）。
  - 生成方式：用仓库自带的 `tools/api2canvas.py` 把 API 格式转成画布格式：
    ```powershell
    & "d:\ai_projects\ComfyUI\venv\Scripts\python.exe" "d:\ai_projects\ComfyUI\tools\api2canvas.py" `
      "workflows\animatediff\animatediff_openpose_sd15_api.json" `
      -o "workflows\animatediff\animatediff_openpose_sd15_ui.json"
    ```
  - 该转换器本次修了两处**真 bug**：① 节点尺寸原写成字典 `{"0":340,"1":h}`，画布格式要求数组 `[宽, 高]`；② VHS 系列节点的前端 widget 序列与 `/object_info` 的 optional 列表**不一致**——`VHS_VideoCombine` 的 `widgets_values` 必须是**字典**（不是数组），`VHS_LoadVideo` 必须是**固定 8 项**且末项为 `force_size`（默认 `"Disabled"`，而 `/object_info` 里的 `meta_batch`/`vae`/`format` 前端并不渲染）。按 `/object_info` 直译会让值错位塞到错误的 widget 上。
  - 生成后做过**保真度校验**：把 UI 图的 17 条连线逐条回查 API 图，节点类型、连线两端（节点+槽位）全部一致；并已**在浏览器里实际加载确认**：侧边栏可找到、加载出 14 节点、14 个中文标题全部识别、无任何报错、控件值正确实例化。
- 控制信号可直接取自上一阶段骨架产物（如 `output/2026-10-02/motion_clone/xinniang_seg3/pose.mp4`），实现「语义/骨架 → 渲染」两条流水线打通。
- **枚举坑**：`VHS_LoadVideo` 的 `video` 下拉枚举是**扁平非递归**的（实测 22 项，无一含 `/`），子目录里的文件不会出现在 UI 下拉里；但 `POST /prompt` 对**实际存在的路径**是宽松的，传子目录相对路径可以正常通过校验并执行。所以脚本把骨架视频复制到 `input/motion_clone_animdiff_<时间戳>/` 是可行的，但你在 UI 里手动选文件时看不到它。

---

## 6. 16GB 显存分时调度策略

### 6.1 现状与矛盾

- 本机显卡显存 **16GB**。
- 去护栏 Qwen 视觉大模型（`RVN-Qwen3.8-27B-Heretic-GSQ-RCO-IQ3_S-mtp.gguf`，约 **11.41GB**）体积巨大。
- Pose 推理（`onnxruntime-gpu`）**也要占用显存**（DWPose 权重如 `yolox_l.onnx` 约 207MB、`dw-ll_ucoco_384.onnx` 约 128MB，加上推理时的中间张量）。

**结论：两者不要并发运行。** 11.41GB 的 LLM 已经吃掉大半显存，再叠加 onnxruntime-gpu 的显存占用，极易把 16GB 打满。

### 6.2 推荐执行顺序（分时调度）

```
第一阶段：语义提取
  启动视觉大模型 → 抽关键帧 → 生成 Prompt → 大模型进程退出（释放显存）
        │
        ▼
第二阶段：骨架提取
  启动 onnxruntime-gpu → 逐帧 Pose 推理 → 平滑 → 渲染骨架 → 落盘
```

**具体做法**：
1. **先跑语义提取**：加载 Qwen 视觉大模型，完成关键帧描述，产出 `prompt.json` / `prompt.txt`。
2. **让进程退出**：大模型所在的进程**完全退出**，把显存还给系统。
3. **再跑骨架提取**：此时显存空闲，再启动 onnxruntime-gpu 做 Pose 推理。

### 6.3 为什么要这样（本项目已记录的教训）

**同时运行会显存打满**，导致任务**卡死在模型初始化阶段**——表现为进程长时间无响应、既不报错也不继续，因为显存分配请求一直无法满足。

因此必须"**先大模型、后 Pose**"，**串行、分时**，而不是并发。

---

## 7. 本地环境依赖清单

> 以下均为**已核验事实**，直接引用，请勿臆改版本号。

### 7.1 Python 解释器

```
d:\ai_projects\ComfyUI\venv\Scripts\python.exe
```

### 7.2 关键依赖包（已安装）

| 包名 | 版本 |
| --- | --- |
| `ultralytics` | 8.4.58 |
| `filterpy` | 1.4.5 |
| `mediapipe` | 0.10.35 |
| `onnxruntime-gpu` | 1.26.0 |
| `opencv-python` | 4.11.0.86 |
| `llama_cpp_python` | 0.3.49 |

### 7.3 DWPose 权重目录

```
custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/
├── yolox_l.onnx
└── dw-ll_ucoco_384.onnx
```

（已核验：两个文件均存在，`yolox_l.onnx` ≈ 207MB，`dw-ll_ucoco_384.onnx` ≈ 128MB。）

### 7.4 视觉大模型

```
models/text_encoders/RVN-Qwen3.8-27B-Heretic-GSQ-RCO-IQ3_S-mtp.gguf   （11.41GB，主模型）
models/text_encoders/mmproj-Qwen3.8-27B-BF16.gguf                     （0.87GB，多模态投影）
```

### 7.5 关于 models 目录（重要）

`models` 目录是一个 **Junction（目录联接）**：

```
d:\ai_projects\ComfyUI\models  →  D:\OLLAMA_MODELS\models
```

- 它指向外部真实目录，**只读引用即可，不要复制**该目录内容（体积巨大，且复制会造成数据冗余）。

---

## 8. 配套脚本说明

> 以下 3 个脚本**均已实现并端到端跑通**（验证数据见第 9 节「实测记录」）。本节说明各自已实现的能力、CLI 关键参数与落盘产物。

### 8.1 `tools/motion_clone/smooth_kalman.py`

**职责（已实现）**：卡尔曼平滑模块。用常速（CV）模型对每个关键点跨帧的 `(x, y)` 轨迹做时序平滑，在保留运动趋势的同时抑制抖动。被 `pose_extract.py` 以 `from smooth_kalman import smooth_sequence` 导入复用。

**对外接口**：
- `smooth_track(track, conf_thresh=0.3, process_noise=1e-2, measurement_noise=1e-1)`：平滑单条关键点轨迹。
- `smooth_sequence(frames_keypoints, ...)`：平滑整段多帧关键点序列，平滑前后帧数与每帧关键点个数保持不变。

**CLI**：无 argparse 参数；直接 `python smooth_kalman.py` 会运行内置自检（合成正弦轨迹 + 高斯噪声，打印平滑前后抖动方差对比）。

**产物**：作为模块无独立落盘产物，平滑结果由调用方 `pose_extract.py` 写入 `keypoints.json`。

### 8.2 `tools/motion_clone/pose_extract.py`

**职责（已实现）**：骨架提取主脚本。

**输入**：参考视频。

**流程**：逐帧 Pose 推理（默认 DWPose）→ 卡尔曼平滑 → 渲染 OpenPose 风格骨架 → 落盘。

**CLI 关键参数**：
- `--video`（必填）：参考视频路径。
- `--outdir`（默认 `output/<日期>/motion_clone/<视频名>/`）：输出目录。
- `--backend {dwpose,yolov8}`（默认 `dwpose`）：姿态后端；`dwpose` 权重本机已齐备，输出 body18 + 左右手21 + 脸70。
- `--no-smooth`：关闭关键点平滑（用于对照）。
- `--conf-thresh`（默认 `0.3`）：关键点置信度阈值。
- `--max-frames`（默认 `0`）：限制处理帧数，`0` 表示全部帧。
- `--yolov8-weights`（默认 `yolov8n-pose.pt`）：yolov8 后端权重名。
- `--no-video`：只出帧序列与 JSON，不合成骨架视频。

**产物**：
- `pose_frames/`：逐帧骨架 PNG（`frame_XXXXXX.png`）
- `pose.mp4`：骨架视频（帧率跟随源视频）
- `keypoints.json`：平滑后的关键点坐标（OpenPose-18 布局）

### 8.3 `tools/motion_clone/semantic_prompt.py`

**职责（已实现）**：语义提示词提取脚本。

**输入**：参考视频。

**流程**：均匀抽取关键帧 → 调用本机去护栏视觉大模型（Qwen3.8-27B + mmproj）描述 → 剥离 think 推理段并整理成英文 Prompt。

**CLI 关键参数**：
- `--video`（必填）：参考视频路径。
- `--frames`（默认 `4`）：均匀抽取的关键帧数量。
- `--outdir`（默认 `output/<日期>/motion_clone/<视频名>/`）：输出目录。
- `--n-ctx`（默认 `8192`）：上下文长度。
- `--max-tokens`（默认 `2048`）：单次生成最大 token 数（需为思考段留预算）。
- `--model` / `--mmproj`：覆盖默认主模型 / 多模态投影路径。
- `--dry-run`：只抽帧与校验模型文件，不加载模型、不推理。
- `--self-test`：运行内置离线自检（用例 A/B1/B2/C/D + 空清洗回退）。

**产物**：
- `keyframes/`：抽取的关键帧图片（`kf_XXXX.png`）
- `prompt.json`：结构化 Prompt（`fields` 含 scene/subject/outfit/lighting/camera/motion/prompt/negative）
- `prompt.txt`：可直接粘贴的一段英文正向 Prompt

### 8.4 产物落盘约定

所有脚本的产物统一落盘到：

```
output/<YYYY-MM-DD>/motion_clone/<项目名>/
```

其中 `<YYYY-MM-DD>` 为运行日期，`<项目名>` 为本次任务的项目名称（与脚本约定一致）。

---

## 9. 实测记录

> 以下全部为端到端验证中**实际观测到的数据**，未做任何推测；跑不通的部分如实标注。

### 测试视频

- 路径：`d:\ai_projects\ComfyUI\output\2026-10-01\xinniang_cosplay_v1\seg3_merged.mp4`
- 分辨率：544 × 960
- 源 fps：24.000
- 总帧数：219

### 骨架提取（pose_extract.py）

| 项目 | 平滑版 | 未平滑对照版 |
| --- | --- | --- |
| 后端 | dwpose | dwpose |
| 是否平滑 | 开启 | 关闭（`--no-smooth`） |
| 处理帧数 | 219（全部帧，未加 `--max-frames`） | 219 |
| 推理 + 渲染总耗时 | 365.17 秒 | 363.24 秒 |
| 输出目录 | `output/2026-10-02/motion_clone/xinniang_seg3` | `output/2026-10-02/motion_clone/_nosmooth_compare` |

（其中 DWPose 后端加载耗时 8.37 秒，渲染 219 张 PNG 耗时 4.65 秒。）

### 抖动对比（平滑 vs 未平滑）

统计口径：对 `people[0].body` 中**连续两帧都有效（conf > 0）**的关键点，计算相邻帧坐标位移
`sqrt(dx² + dy²)`，汇总所有样本求均值与标准差/方差。

| 指标 | 平滑版 | 未平滑版 | 变化 |
| --- | --- | --- | --- |
| 有效样本对（pairs） | 3424 | 3424 | 相同 |
| 位移均值 | 5.8426 px | 5.6362 px | +3.66%（略升） |
| 位移标准差 | 13.1437 px | 19.4753 px | **-32.51%** |
| 位移方差 | 172.7566 | 379.2858 | **-54.45%** |

**结论**：平滑**显著降低抖动**——位移标准差下降 32.51%、方差下降 54.45%，即帧间位移更集中、突发跳点被抑制；位移均值小幅上升 3.66%，属卡尔曼滤波的轻微拖尾效应，不影响"降低抖动"的结论。

### 语义提示词（semantic_prompt.py）

- 使用关键帧数：2（帧索引 = [0, 218]）
- 实际耗时：**1350.17 秒（约 22.5 分钟）**（本次修复后真推理已完成）
- 加载的 handler：`Qwen3VLChatHandler`

**本轮修复项**（只改 `semantic_prompt.py`）：
1. **剥离推理段**：新增 `strip_reasoning()`，解析 JSON 前先去掉成对 ` thinking...`、多余的 think
   结束标记（取最后一个之后）与未闭合的开始标记（取之前），并剥掉 markdown 代码围栏。
2. **提高生成上限**：`--max-tokens` 默认值 `512` → **`2048`**，help 改为中文说明。
3. **尝试关闭思考模式**：调用时先传 `chat_template_kwargs={"enable_thinking": False}`，失败则**静默回退**。
   实测本机 `llama_cpp_python` 0.3.49 不支持该参数，脚本打印了中文提示：
   `提示：当前 llama_cpp 不支持 chat_template_kwargs，已静默回退为普通调用（未能关闭思考模式）。`
   （`raw_response.txt` 中仍含 ` thinking`，证明思考模式并未真正关闭，最终靠剥离 + 2048 上限解决。）

**复跑结果**：
- `prompt.json` 的 `fields` **8 个键齐全**，键列表实测为：
  `['scene', 'subject', 'outfit', 'lighting', 'camera', 'motion', 'prompt', 'negative']`。
- `prompt.txt` 为**英文正向提示词**、**不含 think 推理段**（1 行，783 字符）。前 3 行原文（实为同一行）：

```
Cinematic photorealistic video, smooth slow zoom-out from an extreme close-up of a young East Asian woman's face to a medium-full shot; fair skin, dark eyes, glossy reddish-brown lips, crescent-moon gem between eyebrows, silver chain drop earrings; she wears a red and gold floral crown with dangling beads, a thin gold pendant necklace, a strapless red satin corset dress with gold floral embroidery and gold fringe trim, and black garter sheer stockings; opulent interior with red and gold silk canopy drapery, carved wood lattice, warm string lights, red carpet with gold medallions; soft high-key warm lighting around 3200K, shallow to deep depth of field transition, eye-level centered framing, 85mm to 50mm lens feel, film-grade color grading, ultra-detailed skin texture, 4K.
```

- 离线自检：`--self-test` 用例 A/B1/B2/C/D + 空清洗回退**全部 PASS**，输出 `SELFTEST PASS`（退出码 0）。

### 契约核对（统一输出目录 `output/2026-10-02/motion_clone/xinniang_seg3`）

| 序号 | 产物 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | `pose_frames/` | ✅ | PNG 数量 = 219，等于处理帧数 |
| 2 | `pose.mp4` | ✅ | 存在，4,502,555 字节（非 0） |
| 3 | `keypoints.json` | ✅ | 存在，2,804,733 字节 |
| 4 | `keyframes/` | ✅ | 含 `kf_000.png`、`kf_001.png`（共 2 张） |
| 5 | `prompt.json` | ✅ | 存在，3,236 字节；`fields` 含全部 8 个键 |
| 6 | `prompt.txt` | ✅ | 存在，784 字节（英文正向提示词，不含 think） |

`keypoints.json` 顶层字段实测齐全：
`source_video / fps / width / height / total_frames / processed_frames / backend / smoothed / conf_thresh / keypoint_format / counts / frames`，
取值分别为 `fps=24.0, width=544, height=960, total_frames=219, processed_frames=219, backend=dwpose, smoothed=true, conf_thresh=0.3, keypoint_format=openpose18`，
`counts={body:18, left_hand:21, right_hand:21, face:70}`；`len(frames)==processed_frames==219`。

### 骨架图质量抽检

- 前 5 张 PNG（`frame_000000` ~ `frame_000004`）尺寸均为 **544 × 960**，与 `keypoints.json` 的
  `width/height` **完全一致**。
- 非零像素数分别为：24313 / 24330 / 24286 / 24238 / 23735，**均 > 0**（黑底上确有彩色骨架被画出）。
- **结论**：产物为"黑底彩色骨架"，尺寸与源视频一致，可直接作为 OpenPose ControlNet 的 control image 输入。

### 限制与已知问题

- **单主体策略**：只取 body 关键点置信度之和最大的那一人；多人同框或主体切换时骨架会**跳变**到另一人。
- **转身与自遮挡**：背对镜头或肢体遮挡时，仍可能出现**左右手颠倒 / 关键点跳错**（2D 单目姿态估计的原理性缺陷）。
- **后端覆盖**：本次仅验证 `dwpose`，**未验证 yolov8 后端**（如需可加 `--backend yolov8`，且首次需下载权重）。
- **语义 JSON**：已修复——新增 `strip_reasoning()` 剥离 think 推理段、`--max-tokens` 提至 2048 后，
  `prompt.json` 的 `fields` 实测 8 键齐全（scene/subject/outfit/lighting/camera/motion/prompt/negative）。
  另注：本机 `llama_cpp_python` 0.3.49 不支持 `chat_template_kwargs`，`enable_thinking=False` 未生效，
  脚本已静默回退并打印中文提示；思考段仍会生成，但已被剥离、不再影响 JSON 解析。

### 顺序验证（先语义后骨架）

- 验证目录：`output/2026-10-02/motion_clone/_ordered_e2e`
- 限制条件：语义 `--frames 1`（1 张关键帧），骨架 `--max-frames 30`（30 帧）
- 源视频：`output/2026-10-01/xinniang_cosplay_v1/seg3_merged.mp4`（544×960，24fps，219 帧）

两段产物实测时间戳（先语义、后骨架，且串行不重叠）：

| 阶段 | 产物 | LastWriteTime |
| --- | --- | --- |
| 语义（第 1 步） | `keyframes/`（kf_000.png） | 2026-10-02 12:31:15.396 |
| 语义（第 1 步） | `prompt.json` / `prompt.txt` / `raw_response.txt` | 2026-10-02 12:44:31.29~31.30 |
| 骨架（第 2 步） | `pose_frames/`（30 张 PNG） | 2026-10-02 12:46:00.770 ~ 12:46:01.321 |
| 骨架（第 2 步） | `pose.mp4` | 2026-10-02 12:46:01.327 |
| 骨架（第 2 步） | `keypoints.json` | 2026-10-02 12:46:01.382 |

- **语义在前**：语义最后一个产物（`prompt.txt`）为 12:44:31.30，早于骨架最早产物（`pose_frames/` 首帧 12:46:00.77）。
- **串行不重叠**：语义进程 12:44:31 完成并释放显存后，才启动骨架进程；骨架随后运行 **49.84 秒**（日志 `总耗时=49.84 秒，处理帧数 30`），两段无时间重叠。
- **semantic 实际耗时**：**803.36 秒（约 13.4 分钟，抽帧数=1）**，取自日志 `全部完成：总耗时=803.36s，抽帧数=1`。
- **契约核对（6 项齐全）**：`pose_frames/` ✅（PNG=30）、`pose.mp4` ✅（601,385 字节）、`keypoints.json` ✅（382,287 字节；`processed_frames=30`、`len(frames)=30`、backend=dwpose、smoothed=true）、`keyframes/` ✅（kf_000.png 共 1 张）、`prompt.json` ✅（2,420 字节）、`prompt.txt` ✅（603 字节）。

### 渲染实测（Wan2.2 Animate，2026-10-02）

本次用 `tools/motion_clone/render_wan_animate.py` 对两种姿态模式各提交一次冒烟；为控制成本，两次都用 `--length 9`（Wan 要求 `length % 4 == 1`）。

**共同输入**：

- 参考图：`input/video_wan2_2_14B_animate_reference_image.png`
- 驱动视频：`input/video_wan2_2_14B_animate_original_video.mp4`（640×640，16fps，149 帧）
- 提示词来源：`output/2026-10-02/motion_clone/xinniang_seg3/prompt.txt`

| 模式 | prompt_id | 执行状态 | 耗时 | 成片路径 | 成片规格 |
| --- | --- | --- | --- | --- | --- |
| internal | `2606aaa9-4a70-4669-bb9b-e5b4150b0ec3` | `success`，`completed=true`，输出节点 16,15,21 | 1790918284211 → 1790920552568 = **2268.4 秒 ≈ 37.8 分钟** | `output/2026-10-02/motion_clone_render/xinniang_seg3/wan_internal_00001_.mp4` | 13 帧 / 16fps / 512×512 / 0.19MB |
| ours | `34fdcc9e-89c2-435d-a6a6-8a225996bbbc` | `success`，`completed=true`，输出节点 21 | 1790920555694 → 1790920587178 = **31.5 秒** | `output/2026-10-02/motion_clone_render/xinniang_seg3/wan_ours_00001_.mp4` | 13 帧 / 16fps / 512×512 / 0.12MB |

1. **ours 模式仅 31.5 秒**：因为 internal 刚跑完，`/history` 的 `execution_cached` 显示节点 `1,2,3,4,5,6,7,8,9`（全部模型加载与 LoRA 节点）命中缓存，模型无需重新加载。**这说明 37.8 分钟里绝大部分是 17.5GB 模型的加载开销**，而非扩散推理时间；模型 warm 时 ours 模式极快。

2. **请求 9 帧却产出 13 帧**：Wan 的时序压缩比为 4，输出的有效帧数为 `4 × latent 帧数 + 1`（`length=9` → latent 3 → 13 帧），属预期行为，不是错误。

3. **ours 模式的控制视频**：`output/2026-10-02/motion_clone_render/xinniang_seg3_ours/control/pose_xinniang_seg3.mp4`（身体+双手，9 帧 / 512×512）与 `control/face_xinniang_seg3.mp4`（仅脸，9 帧 / 512×512），由上一阶段的 `keypoints.json` 重绘并按 `ImageScale` 的 cover 语义缩放到 512×512 后替换工作流内置 DWPose 支路。

4. **`render_submit.json` 字段齐全**：`prompt_id` / `pose_mode` / `length` / `width` / `height` / `steps` / `seed` / `submitted_at` / `eta_minutes` / `positive_prompt` / `ref_image` / `driving_video` / `filename_prefix` / `out_dir` / `workflow_source`；ours 模式额外含 `control_pose_video` / `control_face_video`。

5. **已知问题（如实记录，本次未修完的运行）**：这两次冒烟是在 `filename_prefix` 修正**之前**提交的，因此成片落在 `motion_clone_render/xinniang_seg3/`，而 `render_submit.json` 与 `control/` 在 `xinniang_seg3_internal/` 与 `xinniang_seg3_ours/` 两个目录下——**三者被拆到了不同的目录**。修正后（`filename_prefix` 改为由 `--out-dir` 反推）新提交的任务会让成片与提交记录、控制视频落在同一目录；已用 `--dry-run` 验证修正后输出为 `2026-10-02/motion_clone_render/xinniang_seg3_internal/wan_internal`。

6. **查询方式**：脚本提交后只打印 `prompt_id` 与预计完成时间、**不轮询**；本次用一次延时查询（`GET /history/<prompt_id>`）确认两个任务均为 `success`。

7. **前提条件**：ComfyUI 以 `--lowvram` 启动（PID 26004），17.55GB 的 FP8 模型才能在 16GB 卡上运行且无 OOM。

### 渲染路线模型补齐实测（2026-10-02）

**下载（`tools/motion_clone/download_route_models.py`）**：

- 本次共下载 **11 个文件 / 合计 11.08 GB**，全部字节数校验通过，无残留 `.part`。
- 耗时约 **40 分钟**，峰值约 **11 MB/s**；中途出现 `IncompleteRead`，由脚本自动重试成功。
- 因模型已预下载就位，MimicMotion 节点自带的自动下载**未触发**。

**补齐模型实际字节数清单**：

| 模型 | 路径 | 字节数 |
| --- | --- | --- |
| SD1.5 底模 | `models/checkpoints/v1-5-pruned-emaonly.safetensors` | 4,265,146,304（4.27 GB） |
| AnimateDiff 运动模块 | `models/animatediff_models/v3_sd15_mm.ckpt` | 1,673,262,583（1.67 GB） |
| OpenPose ControlNet | `models/controlnet/control_v11p_sd15_openpose.pth` | 1,445,235,707（1.45 GB） |
| MimicMotion 合并 UNet | `models/mimicmotion/MimicMotionMergedUnet_1-1-fp16.safetensors` | 3,049,435,868（3.05 GB） |
| SVD VAE | `models/diffusers/stable-video-diffusion-img2vid-xt-1-1/vae/diffusion_pytorch_model.fp16.safetensors` | 195,531,910 |
| SVD 图像编码器 | `models/diffusers/stable-video-diffusion-img2vid-xt-1-1/image_encoder/model.fp16.safetensors` | 1,264,217,240 |

（MimicMotion 侧 `models/diffusers/stable-video-diffusion-img2vid-xt-1-1/` 共 **7 个文件（不含 unet）**：`model_index.json`、`vae/config.json`、`vae/diffusion_pytorch_model.fp16.safetensors`、`image_encoder/config.json`、`image_encoder/model.fp16.safetensors`、`scheduler/scheduler_config.json`、`feature_extractor/preprocessor_config.json`。）

**路线 A 离线验证与重启核验结论**：独立子进程 import 成功，共 **145 个节点 schema，其中 `ADE_*` 143 个**；用 `start_comfyui.bat` 重启后，`GET /object_info` 实测 `ADE_*` **正好 143 个**，与离线预测完全吻合，节点已在运行期生效（重启后 8188 监听进程 PID 由 26004 变为 35100）。详见下方「AnimateDiff + ControlNet 路线实测（2026-10-02）」。

**MimicMotion 冒烟实测**：

| 项目 | 值 |
| --- | --- |
| prompt_id | `a090bfa7-630c-483e-87df-972212f9ca5a` |
| 状态 | `status_str = success`，`completed = true` |
| 耗时 | 1790931006919 → 1790931378967 = **372.0 秒 ≈ 6.2 分钟** |
| 参数 | `--length 16` / `576×1024` / `steps 20` / `seed 42` |
| 产物 | `output/2026-10-02/motion_clone_render/mimic_smoke/mimicmotion_00001.mp4` |
| 成片规格 | **16 帧 / 12 fps / 576×576** |
| 自动下载 | **未触发**（模型已预下载就位） |

- **输出为何是 576×576 而不是 576×1024**：工作流里处理**参考图**的那个 `ImageResizeKJ`（节点 3）参数是 `width=576, height=1024, keep_proportion=true`；参考图 `input/video_wan2_2_14B_animate_reference_image.png` 是正方形（640×640），`keep_proportion=true` 下输出被约束为 **576×576**（先撞宽度上限）。MimicMotion 生成时的分辨率最终跟随参考图尺寸，所以成片是 576×576。**想强制竖屏**：把该节点的 `keep_proportion` 改为 `false`，或换一张竖构图参考图。**这是如实记录的行为，不是 bug**。

- **一个被证伪的旧结论（已更正）**：此前以为节点 4（处理姿态帧的 `ImageResizeKJ`）通过 `width_input` / `height_input` 接了节点 3 的实际输出尺寸、从而把整条链路压成 576×576。查 `custom_nodes/ComfyUI-KJNodes/nodes/image_nodes.py` 源码后确认：**这两个输入是被注释掉的**
  ```
  #"width_input": ("INT", { "forceInput": True}),
  #"height_input": ("INT", { "forceInput": True}),
  ```
  即它们**从未被声明**，服务端一直忽略；`resize()` 里只是保留了未使用的旧参数。该 `ImageResizeKJ`（v1）本身也已带弃用提示「should no longer be used, please check the v2 of the node」。因此这两个死键**已从 `mimicmotion_api.json` 中删除**（删除不改变行为——它们本来就是空转，冒烟成功恰好证明服务端忽略了它们）。后续若要用 v2 节点（`ImageResizeKJv2`），需另做适配。

**已知限制**：
1. 本轮用的参考图是正方形，故输出 576×576（见上条说明）。
2. 路线 A（AnimateDiff + ControlNet）已完成重启与运行期实测，结论见下方「AnimateDiff + ControlNet 路线实测（2026-10-02）」。

### AnimateDiff + ControlNet 路线实测（2026-10-02）

**重启前后的注册对比**（用项目自带启动器 `start_comfyui.bat` 重启，它会设置 `HF_HOME` / `HUGGINGFACE_HUB_CACHE` / `TORCH_HOME` 等到 D 盘，并以 `--lowvram --listen 0.0.0.0 --port 8188` 启动 `venv\Scripts\python.exe main.py`）：

| 项 | 重启前 | 重启后 |
| --- | --- | --- |
| 节点总数 | 1346 | **1497** |
| `ADE_*` 节点数 | **0** | **143** |
| 服务 PID | 26004 | **35100** |

- **离线预测与实测吻合**：重启前在不重启的独立子进程里预测 `ADE_*` 有 **143** 个，重启后 `/object_info` 实测**正好 143 个**，完全吻合。
- **关键节点均在册**：`ADE_LoadAnimateDiffModel`、`ADE_AnimateDiffLoaderGen1`、`ADE_AnimateDiffLoaderWithContext`、`ADE_AnimateDiffCombine`、`ADE_AnimateDiffSamplingSettings`、`ADE_StandardUniformContextOptions`。
- `ADE_LoadAnimateDiffModel` 的 `model_name` 枚举**唯一值就是 `v3_sd15_mm.ckpt`** —— 这同时证明 `models/animatediff_models/` 目录已被 ComfyUI 正确注册。
- **进程认知**：本机 `venv\Scripts\python.exe` 是**重定向桩**，会派生 anaconda 解释器作为**子进程**跑真正的服务，故 `Get-CimInstance Win32_Process` 会看到两个参数相同的 python 进程，**真正监听 8188 的是 anaconda 子进程**（重启前 26004，重启后 35100）；杀进程时两个都要处理。

**AnimateDiff + ControlNet(OpenPose) 冒烟实测**：

| 项目 | 值 |
| --- | --- |
| prompt_id | `b9802cb5-426b-4231-927b-e11095510f2e` |
| 状态 | `status_str = success`，`completed = true`，输出节点 14（`VHS_VideoCombine`） |
| 耗时 | 1790934666219 → 1790934750071 = **83852 ms ≈ 83.9 秒（约 1.4 分钟）** |
| 参数 | 16 帧 / 512×768 / 20 步 / cfg 7.5 / seed 42 / ControlNet strength 0.9 / frame_rate 8 |
| 产物 | `output/2026-10-02/motion_clone_render/animatediff_smoke/animatediff_00001.mp4` |
| 成片规格 | **16 帧 / 8 fps / 512×768**，首帧可读（另有同名 `.png` 预览图） |
| 提交记录 | `render_submit.json` **19 个字段齐全** |

- **控制信号来自上一阶段的骨架流水线（重点）**：本次 ControlNet 控制图**不是**随便找的图，而是上一阶段产出的 OpenPose 骨架视频 `output/2026-10-02/motion_clone/xinniang_seg3/pose.mp4`（DWPose 提取并渲染的黑底彩色骨架，219 帧 / 544×960 / 24fps），经 `ImageScale(crop=center)` 缩放到 512×768 后送入 `ControlNetApplyAdvanced`。**这意味着「语义/骨架 → 渲染」两条流水线真正打通了**：骨架产物可以直接驱动 AnimateDiff 出片。
- **实际使用的节点链**：`CheckpointLoaderSimple`(v1-5-pruned-emaonly) → `CLIPTextEncode`×2；`ADE_LoadAnimateDiffModel`(v3_sd15_mm.ckpt) → `ADE_ApplyAnimateDiffModelSimple` → `ADE_UseEvolvedSampling`；`ControlNetLoader`(control_v11p_sd15_openpose) → `ControlNetApplyAdvanced`；`VHS_LoadVideo` → `ImageScale(center)` → `EmptyLatentImage` → `KSampler` → `VAEDecode` → `VHS_VideoCombine`。
- **坑 1（Gen2 接口）**：AnimateDiff v3 用的是 **Gen2 接口**：`ADE_AnimateDiffLoaderGen1` 与 `ADE_AnimateDiffLoaderWithContext` **只接受 `model_name`(COMBO)，没有 MOTION_MODEL 输入槽**，无法消费 `ADE_LoadAnimateDiffModel` 的输出，会产生孤立节点；因此必须改用 Gen2 的 `ADE_ApplyAnimateDiffModelSimple` + `ADE_UseEvolvedSampling` 这条链。
- **坑 2（VHS 枚举）**：`VHS_LoadVideo` 的 `video` 下拉枚举是**扁平非递归**的（实测 22 项，无一含 `/`），子目录里的文件不会出现在 UI 下拉里；但 `POST /prompt` 对**实际存在的路径**是宽松的，传子目录相对路径可以正常通过校验并执行。所以脚本把骨架视频复制到 `input/motion_clone_animdiff_<时间戳>/` 是可行的，但你在 UI 里手动选文件时看不到它。
- **耗时仅 1.4 分钟**，**远快于预估 3.2 分钟**。
- 新增文件：`workflows/animatediff/animatediff_openpose_sd15_api.json`（API 格式工作流）、`tools/motion_clone/render_animatediff.py`（提交脚本）。

---

## 10. 参考链接

- **DWPose**（`yzd-v/DWPose`）: https://github.com/IDEA-Research/DWPose
- **ControlNet**（含 OpenPose 控制）: https://github.com/lllyasviel/ControlNet
- **controlnet_aux**（ComfyUI 的 ControlNet 预处理节点集，含 DWPose）: https://github.com/Fannovel16/comfyui_controlnet_aux
- **Ultralytics**（YOLOv8 / YOLOv8-Pose）: https://github.com/ultralytics/ultralytics
- **MimicMotion**: https://github.com/Tencent/MimicMotion
- **MimicMotionWrapper（ComfyUI 封装）**: https://github.com/kijai/ComfyUI-MimicMotionWrapper