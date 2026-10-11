# MimicMotion 动作克隆工作流 · 使用说明

> 面向初学者级开发者。读完本文你能理解这个工作流在做什么、怎么用 UI 或命令行跑通、每个节点在干什么、参数怎么调，以及那些"踩了才知道"的坑。
>
> 语言：中文为主，术语 / 命令 / 文件名保留英文。

---

## 1. 这个工作流是干什么的

**一句话**：给一张**参考角色图**，再给一段**驱动视频**，让参考图里的角色**按驱动视频的姿态动起来**，输出一段动作克隆视频。

**原理（一句话讲清）**：MimicMotion 是 **SVD（Stable Video Diffusion）系**的视频生成模型——它把**驱动视频的姿态序列**当作条件（condition），把**参考图**当作身份/外观锚点（identity / appearance anchor），从而在保留参考图长相的同时复刻驱动视频的动作。

与本项目另外两条动作克隆路线相比，定位差异如下（耗时均为本机实测）：

| 路线 | 原理 | 适用场景 | 实测耗时参考 |
| --- | --- | --- | --- |
| **MimicMotion（本文）** | SVD 系 + 姿态条件，**直接吃驱动视频**（节点内部自动跑 DWPose 提姿态） | 有现成的"人+动作"驱动视频，想一键复刻到角色身上 | **16 帧 ≈ 6.2 分钟**（372.0 秒） |
| AnimateDiff + ControlNet(OpenPose) | SD1.5 + 运动模块 + 骨架控制，**需要先有骨架序列**（上一阶段产出 `pose.mp4`） | 已单独提好骨架、想要更快的迭代、可精细调 ControlNet | **16 帧 ≈ 83.9 秒**（约 1.4 分钟） |
| Wan2.2 Animate 14B | 把驱动视频的**骨架/表情**迁移到参考角色 | 精度优先、不赶时间、显存吃紧也能跑（需 `--lowvram`） | **49 帧 ≈ 40.7 分钟**（2444.6 秒） |

> 三条路线的完整调研见 `tools/motion_clone/README.md` 第 5 节。

本工作流文件：

- `workflows/mimicmotion/mimic_motion_ui.json` —— UI 画布版（**9 节点 / 10 连线**，节点带中文标题，可直接在 ComfyUI 里打开）。
- `workflows/mimicmotion/mimic_motion_api.json` —— API 版（9 节点 / 8 类），给命令行脚本注入参数用。

---

## 2. 两种用法

### A. UI 手工用（最简单）

1. 启动 ComfyUI（本机以 `--lowvram` 运行）。
2. 打开左侧「工作流」面板，点开 **`mimicmotion_ui`**。
3. 该画布**已预填**参考图与驱动视频：
   - 参考图：`video_wan2_2_14B_animate_reference_image.png`
   - 驱动视频：`video_wan2_2_14B_animate_original_video.mp4`
4. 想换素材就改输入，其余保持默认，直接点「运行」（Queue）。
5. 输出前缀是 `motion_clone_render/mimicmotion_ui`，成片落在 `output/motion_clone_render/` 下（**不带日期**，见第 6 节）。

> UI 版与 API 版的**唯一差别是两处输入值**：API 版留占位串（`INSTREAM_REF_IMAGE` / `INSTREAM_DRIVING_VIDEO`）供脚本注入；UI 版预填真实示例值，所以打开即可跑。

### B. 命令行用（脚本提交）

```powershell
& "d:\ai_projects\ComfyUI\venv\Scripts\python.exe" "d:\ai_projects\ComfyUI\tools\motion_clone\render_mimicmotion.py" `
  --ref-image "<参考角色图>" --video "<驱动视频>" `
  --length 16 --width 576 --height 1024
```

- 加 `--dry-run` **只校验、不提交**（注意：`--dry-run` 仍会把输入复制到 `input/motion_clone_mimic_<时间戳>/` 目录，只是不发 `POST /prompt`）。
- 脚本打印 `prompt_id` 与预计完成时间后**不轮询**；结果稍后手动查一次：

```powershell
Invoke-RestMethod "http://127.0.0.1:8188/history/<prompt_id>" | ConvertTo-Json -Depth 6
```

- 默认输出目录由「今日日期 + 驱动视频文件名」推出：`output/<日期>/motion_clone_render/<项目名>_mimicmotion/`；也可用 `--out-dir` 覆盖。

---

## 3. 节点逐个说明（共 9 个）

| 序号 | 节点类型 | 中文标题 | 作用 | 关键参数 |
| --- | --- | --- | --- | --- |
| 1 | `LoadImage` | 参考角色图 | 读入参考角色图（决定长相/外观） | `image`（下拉：ComfyUI `input/` 目录下的图片） |
| 2 | `VHS_LoadVideo` | 驱动视频（动作来源） | 读入驱动视频，取帧作为动作来源 | `video`、`frame_load_cap`（**= 生成帧数**）、`force_rate`、`select_every_nth` |
| 3 | `ImageResizeKJ` | 参考图缩放（keep_proportion=true） | 把参考图缩放到目标尺寸，**保持宽高比** | `width=576`、`height=1024`、`keep_proportion=true`、`divisible_by=64` |
| 4 | `ImageResizeKJ` | 姿态帧缩放 576x1024 | 把驱动视频帧缩放到目标尺寸，**不保持宽高比**（直接拉伸） | `width=576`、`height=1024`、`keep_proportion=false`、`divisible_by=64` |
| 5 | `MimicMotionGetPoses` | 提取姿态 MimicMotionGetPoses | **内部跑 DWPose**，把姿态帧渲染成骨架，并把参考图姿态也画进去 | `include_body`、`include_hand`、`include_face`（三者默认均 `true`） |
| 6 | `DownloadAndLoadMimicMotionModel` | 加载 MimicMotion 模型 | 加载合并 UNet + SVD 的 VAE/ImageEncoder + PoseNet | `model`、`precision`（默认 `fp16`） |
| 7 | `MimicMotionSampler` | MimicMotion 采样 | 核心采样，参数最多（见第 4 节） | `steps`、`cfg_min`、`cfg_max`、`seed`、`fps`、`context_size`、`context_overlap` 等 |
| 8 | `MimicMotionDecode` | 解码 | 把 latent 解码成帧（分块解码省显存） | `decode_chunk_size`（默认 4） |
| 9 | `VHS_VideoCombine` | 合成视频 | 把帧合成为 mp4 | `frame_rate`、`filename_prefix`、`format`、`crf` |

**连线关系简述**：

- 参考图支路：`1 → 3`；驱动视频支路：`2 → 4`。
- `3 → 5` 与 `4 → 5`（节点 5 同时拿到缩好的参考图与姿态帧）。
- `3 → 7`（参考图还直接喂给采样节点，作为身份锚点）；`4 → 5`；`5 → 7`（姿态喂给采样节点）。
- `6 → 7`（模型喂给采样）；`7 → 8`（latent 喂给解码）；`6 → 8`（解码也要 pipeline）；`8 → 9`（帧喂给合成）。

---

## 4. 参数怎么调

### 4.1 命令行参数（`render_mimicmotion.py`）

| 参数 | 默认值 | 说明 / 调大调小的影响 |
| --- | --- | --- |
| `--length` | `16` | **生成多少帧**，映射到工作流的 `frame_load_cap`。调大 → 视频更长但耗时线性上升；调小 → 更快（注意见下方"帧数下限"约束）。 |
| `--width` / `--height` | `576` / `1024` | 目标尺寸。**建议 64 的整数倍**（节点 `divisible_by=64` 会把非整倍数自动吸附并打印警告）。调大 → 更清晰但更吃显存、更慢；调小 → 更快。 |
| `--steps` | 沿用工作流值 **20** | 采样步数。调大 → 细节更足但更慢；调小 → 更快，过低会糊。 |
| `--seed` | 沿用工作流值 **42** | 随机种子。固定种子可复现；改了 → 画面细节变化。 |
| `--model` | `MimicMotionMergedUnet_1-1-fp16.safetensors` | 模型文件名（可选 `MimicMotionMergedUnet_1-0-fp16.safetensors`）。 |
| `--out-dir` | 缺省按日期+项目名推 | 覆盖输出目录。 |
| `--dry-run` | 关 | 只校验不提交（仍会搬运输入，见第 2 节）。 |

> **帧数下限约束（重要）**：采样节点里有 `assert B >= context_size`，其中 `B = 1（参考姿态）+ length（姿态帧数）`。`context_size` 默认 16，所以 **`--length` 至少要 15**，否则会断言失败。默认 16（B=17）是安全的。

### 4.2 采样节点 `MimicMotionSampler` 内部参数（UI 里直接调）

| 参数 | 默认值 | 说明 / 调大调小的影响 |
| --- | --- | --- |
| `steps` | 20（节点声明默认 25，工作流填 20） | 同 `--steps`。 |
| `cfg_min` / `cfg_max` | `2.0` / `2.0` | 引导强度上下限。调大可增强对条件（姿态/参考图）的遵循，但过大易过曝/僵硬；调小更"自由"。 |
| `seed` | 42（节点声明默认 0） | 同 `--seed`。 |
| `fps` | `15` | 写入生成 metadata 的目标帧率。实际成片的 `frame_rate` 由节点 9 决定（UI 里为 12）。 |
| `noise_aug_strength` | `0.0` | 加噪增强强度。0 表示不加；调大会更多改变参考图外观、更"动"，过大可能丢失身份。 |
| `context_size` | `16` | **分窗口处理长视频的窗口大小**（tile_size）。视频比窗口长就会被切成多个窗口分别处理。调大 → 单窗口更长，但显存与耗时上升。 |
| `context_overlap` | `6` | **相邻窗口的重叠帧数**（tile_overlap）。**overlap 越大，窗口接缝越平滑，但越慢**；太小会出现接缝跳变。 |
| `keep_model_loaded` | `false`（节点声明默认 `true`） | 跑完是否把模型留在显存。`false` → 跑完卸载，省显存但下次要重载；`true` → 常驻更快但占显存。 |
| `pose_strength` | `1.0` | 姿态条件强度。调大 → 更严格跟随驱动动作；调小 → 动作更"松"。 |
| `pose_start_percent` / `pose_end_percent` | `0.0` / `1.0` | 生效区间（按去噪进度百分比）。可只在某段行程施加姿态条件。 |
| `image_embed_strength` | `1.0` | 参考图身份嵌入强度。调大 → 更像参考图；过大可能"锁死"导致动作僵硬。 |

> **1.1 模型的 context_size 警告**：节点源码在检测到模型名含 `1-1` 且 `context_size != 72` 时会打印告警 `WARNING: 1.1 model should use 72 frame context_lenght`。本工作流默认 16 帧、context_size=16，是能跑通的组合（实测成功）；想按官方建议贴近 72 时需相应加大帧数。

### 4.3 解码节点 `MimicMotionDecode`

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `decode_chunk_size` | `4` | 分块解码大小。**显存紧就调小**（源码里出错还会自动回退到 1）；调大解码更快但更吃显存。 |

---

## 5. 输入准备与那个"下拉看不到"的坑

- **参考图与驱动视频都要放在 ComfyUI 的 `input/` 目录下**，才能在下拉里选到。
- **`VHS_LoadVideo` 的 `video` 下拉枚举是扁平非递归的**：实测 **22 项，无一含 `/`**——也就是说，**子目录里的视频不会出现在下拉里**。
  - **手工用**：请把驱动视频放到 `input/` **根目录**，下拉里才看得见。
  - **命令行用**：脚本会自动把参考图与驱动视频复制到 `input/motion_clone_mimic_<时间戳>/`，并以**相对路径**（如 `motion_clone_mimic_20261002_120000/xxx.mp4`）提交。`POST /prompt` 对**实际存在的路径**是宽松的，能正常通过校验并执行——所以脚本能用子目录，只是你在 UI 下拉里看不到它。

---

## 6. 输出

### CLI

- 目录：`output/<日期>/motion_clone_render/<项目名>_mimicmotion/`
- 成片：`mimicmotion_00001.mp4`
- 提交记录：`render_submit.json`，字段清单：
  `prompt_id` / `pose_mode`（值为 `mimicmotion_internal`）/ `length` / `width` / `height` / `steps` / `seed` / `model` / `ref_image` / `driving_video` / `filename_prefix` / `submitted_at` / `eta_minutes` / `out_dir` / `workflow_source`。

### UI

- 因为 UI 版前缀是 `motion_clone_render/mimicmotion_ui`（**不带日期**），成片会落在 `output/motion_clone_render/mimicmotion_ui_00001.mp4`。

### 实测基线

- `prompt_id = a090bfa7-630c-483e-87df-972212f9ca5a`，`status_str = success`，`completed = true`。
- 耗时 **372.0 秒 ≈ 6.2 分钟**（16 帧）。
- 成片规格：**16 帧 / 12 fps / 576×576**（详见第 8 节第 1 条）。

---

## 7. 模型与显存

### 模型路径与大小

| 内容 | 路径 | 大小 |
| --- | --- | --- |
| MimicMotion 合并 UNet | `models/mimicmotion/MimicMotionMergedUnet_1-1-fp16.safetensors` | 3,049,435,868 字节（3.05 GB） |
| SVD 组件目录 | `models/diffusers/stable-video-diffusion-img2vid-xt-1-1/` | 共 **7 个文件**（含 `vae` 与 `image_encoder`） |

SVD 目录 7 个文件为：`model_index.json`、`vae/config.json`、`vae/diffusion_pytorch_model.fp16.safetensors`、`image_encoder/config.json`、`image_encoder/model.fp16.safetensors`、`scheduler/scheduler_config.json`、`feature_extractor/preprocessor_config.json`。

### 节点会自动下载吗？本机有没有下过？

节点自带自动下载（主 UNet 从 `Kijai/MimicMotion_pruned`、SVD 从 `vdo/stable-video-diffusion-img2vid-xt-1-1`）。但**本机已预置**这些文件，所以**不会触发下载**（实测记录确认"自动下载未触发"）。

验证方法：`snapshot_download(local_dir=...)` 会在 `<local_dir>/.cache/huggingface/` 留下 metadata。检索这两个目标目录——

- `models/mimicmotion/` 下**没有** `.cache/huggingface/`；
- `models/diffusers/stable-video-diffusion-img2vid-xt-1-1/` 下也**没有** `.cache/huggingface/`。

即这两个模型从未通过节点自动下载。

> 注意：`models` 下其它无关子目录（如 `loras`、`unet`、`text_encoders`、`sams`）确实存在 `.cache/huggingface/`，那是别的任务留下的，与 MimicMotion 无关，别混为一谈。

### 一个脆弱点（务必写清）

节点对 SVD 是否存在的判断是：

```python
svd_path = os.path.join(folder_paths.models_dir, "diffusers", "stable-video-diffusion-img2vid-xt-1-1")
if not os.path.exists(svd_path):   # 只检查目录是否存在
    ...snapshot_download(...)
```

**它只检查目录是否存在，不逐文件检查。** 后果：目录在、但文件缺（比如只下了 `model_index.json`、缺 `vae/` 权重）时，会**静默跳过下载**；等到后面 `from_pretrained(svd_path, subfolder="vae"/"image_encoder")` 才报**"找不到配置"**这类**误导性错误**（你会以为是配置问题，其实是权重文件缺失）。

**补模型时务必逐文件校验字节数**，不要只看目录在不在。

> 补充：官方 `stabilityai/stable-video-diffusion-img2vid-xt-1-1` 是 **gated（401）**，需要 token；节点用的是**非 gated** 的 `vdo/stable-video-diffusion-img2vid-xt-1-1`。

### 显存

- ComfyUI 以 `--lowvram` 运行；**16GB 卡可跑**（实测无 OOM）。

---

## 8. 已知坑（现象 → 原因 → 怎么改）

### 1. 输出是 576×576，而不是竖屏 576×1024

- **现象**：脚本传了 `--width 576 --height 1024`，成片却是 **576×576**。
- **原因**：节点 3（参考图缩放）参数是 `width=576, height=1024, keep_proportion=true`。参考图 `video_wan2_2_14B_animate_reference_image.png` 是 **640×640 正方形**。`ImageResizeKJ` 源码里 `keep_proportion=true` 时按 `ratio = min(width/W, height/H)` 缩放——`min(576/640, 1024/640) = 0.9`，**先撞宽度上限**，结果被约束成 **576×576**。而 MimicMotion 的**生成分辨率跟随参考图尺寸**，所以成片是 576×576。（注意：节点 4 处理姿态帧用的是 `keep_proportion=false`，会直接拉伸到 576×1024，但最终生成分辨率仍由参考图那条决定。）
- **怎么改**：把节点 3 的 `keep_proportion` 改成 **`false`**，或换一张**竖构图**的参考图。

> 这是如实记录的行为，**不是 bug**。

### 2. `ImageResizeKJ`（v1）已被 KJNodes 弃用

- **现象**：工作流里用的是 `ImageResizeKJ`（v1），KJNodes 源码已标注 `DEPRECATED = True`，提示「should no longer be used, please check the v2 of the node」。
- **原因**：因 ComfyUI 前端变化，v1 节点被保留仅为不彻底破坏旧工作流。
- **附带事实**：它的 `width_input` / `height_input` 两个输入**在源码里是被注释掉的**（

  ```python
  #"width_input": ("INT", { "forceInput": True}),
  #"height_input": ("INT", { "forceInput": True}),
  ```

  ），即**从未声明、服务端一直忽略**，所以工作流里**已不含这两个键**。删除它们不改变行为。
- **怎么改**：若后续想改用 `ImageResizeKJv2`，需要**重新连尺寸线**（v2 的输入/输出槽位与 v1 不同）。

### 3. 单次生成偏慢

- **现象**：16 帧约 **6.2 分钟**；**首次调用**还要额外加载模型，更慢。
- **原因**：SVD 系扩散 + 合并 UNet + 内部 DWPose 姿态提取，本身计算量就不小；冷启动时模型加载占很大一部分。
- **怎么改**：想快就**减 `--length`**、**减 `--steps`**；`keep_model_loaded=true` 可省去重复加载（但更占显存）；`decode_chunk_size` 显存紧时调小。

---

## 9. 参考

- 节点自带 README：`custom_nodes/ComfyUI-MimicMotionWrapper/README.md`
- 示例工作流：`custom_nodes/ComfyUI-MimicMotionWrapper/examples/mimic_motion_example_02.json`
- 本路线在总调研文档里的位置：`tools/motion_clone/README.md` 第 5 节（MimicMotion 小节）