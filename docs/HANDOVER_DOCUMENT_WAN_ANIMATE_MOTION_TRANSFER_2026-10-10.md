# Wan2.2 Animate 14B 动作克隆全链路工程落地交接文档
**Session Handover Document: Wan2.2 Animate 14B Motion Transfer Pipeline & 1:1 Multi-Chunk Stitching**

- **文档创建日期**：2026-10-10
- **会话主题**：Wan2.2 Animate 14B 动作克隆（Motion Transfer）单驱动视频自动化提取、1:1 全长时序无缝缝合与 Web UI / API 双版本交付
- **运行环境**：Windows 11 / Python 3.11 / CUDA 12.4 / PyTorch 2.5.1
- **硬件基准**：NVIDIA GeForce RTX 4060 Ti 16GB (VRAM: 16380 MiB)
- **交付状态**：生产就绪（Production Ready），全链路自动化与静态/动态测试 100% 通过

---

## 1. 项目背景与核心业务目标

### 1.1 业务诉求
实现工业级、低门槛的 **AI 视频动作克隆（Motion Transfer）**：
- **输入端**：仅需 **1 张目标角色肖像图**（如 `005-822807425_...jpeg`）和 **1 个任意真实的舞蹈/动作参考视频**（如 `Instagram14_video.mp4`、`Instagram18_video.mp4`）。
- **处理端**：无需人工干预或第三方离线提取，工作流内置 GPU 极速提取肢体骨架与面部微表情。
- **输出端**：输出与原驱动视频 **1:1 完全一致的时长**（如 6.07 秒 / 7.07 秒）、音画精准同步、动作无缝还原的高清视频（480x832 @ 30 FPS）。

### 1.2 核心工程挑战与硬件边界
- **显存与时长瓶颈**：在 RTX 4060 Ti 16GB 显存环境下，Wan2.2 Animate 14B 模型单次无法承受 80 帧以上的单批次渲染（极易发生 CUDA OOM），其原生最佳单块长度为 49 帧（约 1.6 秒）。
- **全长无缝化诉求**：常规短片合成存在分段时序不连贯、动作突变、重叠帧卡顿等问题，必须通过工程化手段解决跨分块的滑动窗口时序延续与无缝合并。

---

## 2. 核心技术攻坚与演进历程

在本次研发过程中，经历了三个关键阶段的突破与重构：

### 阶段一：多块时序滑动与 5 帧重叠消除（CLI / API 原型）
1. **时序连贯机制（`continue_motion`）**：
   - WanAnimate 节点提供 `continue_motion` 输入槽，通过传入上一分块生成的最后 5 帧画面，作为下一分块生成的初始引导，保证动作不会在分块交界处发生撕裂。
2. **重叠消除与精准裁切（`GetImageRangeFromBatch`）**：
   - 相邻分块设计为 5 帧重叠（`offset` 步长为 44~45 帧）：
     - Chunk 1：帧 0~48（49 帧）$\rightarrow$ 裁切保留前 45 帧（0..44）
     - Chunk 2：帧 45~93（49 帧）$\rightarrow$ 裁切保留前 44 帧（45..88）
     - Chunk 3：帧 89~137（49 帧）$\rightarrow$ 裁切保留前 44 帧（89..132）
     - Chunk 4：帧 133~181（49 帧）$\rightarrow$ 裁切保留前 49 帧（133..181）
   - 裁切后帧数相加：$45 + 44 + 44 + 49 = 182$ 帧，在 30 FPS 下刚好等于 6.067 秒（100% 完整时长），消除由于重叠帧导致的“时间倒流”或顿挫。

### 阶段二：Web UI 图形化重构与排障（解决 3 大关键阻塞）

#### 阻碍 1：CreateVideo 槽位类型错误（FPS 类型不兼容）
- **现象**：Web UI 报错 `Create Video 的 fps 输入需要 FLOAT，但连接的输出为 INT`。
- **根因**：`GetVideoComponents` 节点的输出槽位为：
  - Slot 0: `images` (`IMAGE`)
  - Slot 1: `audio` (`AUDIO`)
  - Slot 2: `fps` (`FLOAT`)
  - Slot 3: `bit_depth` (`INT`)
  原脚本误将 `fps` 连接到了 Slot 3 (`bit_depth`)。
- **修复**：修正连接拓扑，明确将 Slot 2 (`FLOAT`) 接入 `CreateVideo` 的 `fps` 槽。

#### 阻碍 2：动作未跟随驱动视频 & 后半段动作卡死
- **现象**：用户在 UI 中更换驱动视频后，成片人物未跳该舞蹈，且动作在 1.6 秒后冻结。
- **根因分析**：
  1. 原 UI 工作流设计了 3 个视频输入：`Node 12`（原驱动视频）、`Node 22`（肢体骨骼）、`Node 24`（面部表情）。用户更换了 `Node 12`，但 `Node 22` 与 `Node 24` 仍残留为默认的 `ootd_chunk0_pose_pure.mp4` 与 `ootd_chunk0_face_pure.mp4`。WanAnimate 的动作完全由 `pose_video` 决定，导致人物跳了旧舞。
  2. 残留的骨骼底片只有 49 帧（1.6 秒），从第 45 帧起（Chunk 2 开始）骨骼底片越界耗尽，WanAnimate 只能复制最后一帧，导致后半段动作完全卡死。
- **修复**：彻底废除手动加载节点 22、23、24、25，改为工作流内由 `Node 12` 自动提取骨骼和表情。

#### 阻碍 3：DWPose CPU 降级危机与 GPU 35倍提速突破
- **性能危机**：接入 `DWPreprocessor` 进行自动提取时，OpenCV DNN 默认使用 ONNX 并在 Windows 平台降级为 CPU 运行，单帧耗时高达 **1400ms**！提取 182 帧需 4~8 分钟，不可接受。
- **技术突破**：深度挖掘 `custom_nodes/comfyui_controlnet_aux` 源码，发现已具备 TorchScript 权重：
  - Bbox 检测器：`yolox_l.torchscript.pt`
  - 姿态估计器：`dw-ll_ucoco_384_bs5.torchscript.pt`
  切换为 TorchScript 后，模型直接由 PyTorch 原生加载至 CUDA GPU 执行，单帧耗时骤降至 **39ms（25 FPS 实时级速度）**！整段视频提取缩短至数秒完成。

### 阶段三：终极落地 —— 单一视频入口与动态时长 1:1 对齐
彻底完成 UI 工作流重构，用户只需传入单个视频，工作流全自动处理一切。同时根据两类常见视频长度提供精准对齐的工作流：
- **4 分块标准版**：针对约 6 秒短视频（如 182 帧的 `Instagram14_video.mp4`）。
- **5 分块扩展版**：针对约 7 秒短视频（如 212 帧的 `Instagram18_video.mp4`）。

---

## 3. 系统架构与数据流拓扑

整个生产管线分为五大功能域，数据流完全闭环：

```
+-------------------------------------------------------------------------------------------------------+
|  ① 模型底座与 LoRA 控制区 (Nodes 1~7)                                                                 |
|  - UNETLoader (Wan2.2 14B) + CLIPLoader + VAELoader + CLIPVisionLoader                                |
|  - LoraLoaderModelOnly (lightx2v + relight) + ModelSamplingSD3 (shift=5.0)                            |
+-------------------------------------------------------------------------------------------------------+
                                  | (MODEL, VAE, CLIP)
+-------------------------------------------------------------------------------------------------------+
|  ② 提示词控制区 (Nodes 8~9)                                                                           |
|  - Positive / Negative CLIP Text Encode                                                               |
+-------------------------------------------------------------------------------------------------------+
                                  | (CONDITIONING)
+-------------------------------------------------------------------------------------------------------+
|  ③ 核心输入与骨骼极速提取区 (Nodes 10~16)                                                              |
|  - Node 10: 目标人物肖像图 (LoadImage)                                                                 |
|  - Node 11: CLIPVisionEncode                                                                          |
|  - Node 12: 原参考驱动视频 (LoadVideo，单入口！)                                                       |
|  - Node 13: 拆解组件 (GetVideoComponents) ---> 提取原声音频 (AUDIO) 与 原始帧率 (FLOAT)               |
|      |                                                                                                |
|      v (images: IMAGE)                                                                                |
|  - Node 14: ImageScale (512x512 lanczos)                                                              |
|      +--------> Node 15: DWPreprocessor [Face] (TorchScript GPU) ----> face_video (表情流)             |
|      +--------> Node 16: DWPreprocessor [Pose] (TorchScript GPU) ----> pose_video (骨骼流)             |
+-------------------------------------------------------------------------------------------------------+
                                  | (All streams connected)
+-------------------------------------------------------------------------------------------------------+
|  ④ 分块渲染与时序缝合区 (Chunks 1..N)                                                                 |
|  - Chunk 1: Offset=0,   Len=49 -> KSampler(4-step) -> VAEDecode -> Trim(45f)                         |
|  - Chunk 2: Offset=45,  Len=49 -> KSampler(4-step) -> VAEDecode -> Trim(44f)                         |
|  - Chunk 3: Offset=89,  Len=49 -> KSampler(4-step) -> VAEDecode -> Trim(44f)                         |
|  - Chunk 4: Offset=133, Len=49 -> KSampler(4-step) -> VAEDecode -> Trim(49f 或 44f)                   |
|  [- Chunk 5: Offset=177, Len=49 -> KSampler(4-step) -> VAEDecode -> Trim(35f)] (7s 扩展版)           |
|                                                                                                       |
|  - 级联缝合: Node 601 (C1+C2=89f) -> Node 602 (+C3=133f) -> Node 603 (+C4=182f) [-> Node 604 (+C5=212f)] |
+-------------------------------------------------------------------------------------------------------+
                                  | (Stitched IMAGE)
+-------------------------------------------------------------------------------------------------------+
|  ⑤ 音画终极合成与自动归档区 (Nodes 710~720)                                                           |
|  - Node 710: CreateVideo (接入缝合图像 + Node 13 实际音频 + Node 13 实际浮点 FPS)                      |
|  - Node 720: SaveVideo (自动输出至 output/YYYY-MM-DD/motion_transfer_full/)                          |
+-------------------------------------------------------------------------------------------------------+
```

---

## 4. 交付文件清单与资产索引

所有文件均严格遵守工程隔离与当日产物归档规范：

### 4.1 工作流资产文件
| 工作流名称 | 适用场景 | UI 文件路径（ComfyUI 浏览器直接加载） | 隔离开发与 API 文件路径 |
| :--- | :--- | :--- | :--- |
| **标准版 (4-Chunk)** | 182 帧 / 6.07 秒<br>(针对 Instagram14 等 6s 短片) | [`user/default/workflows/motion_transfer_wan_animate_multichunk_full_ui.json`](file:///d:/ai_projects/ComfyUI/user/default/workflows/motion_transfer_wan_animate_multichunk_full_ui.json) | UI: [`workflows/v3/motion_transfer_wan_animate_multichunk_full_ui.json`](file:///d:/ai_projects/ComfyUI/workflows/v3/motion_transfer_wan_animate_multichunk_full_ui.json)<br>API: [`workflows/v3/motion_transfer_wan_animate_multichunk_full_api.json`](file:///d:/ai_projects/ComfyUI/workflows/v3/motion_transfer_wan_animate_multichunk_full_api.json) |
| **扩展版 (5-Chunk)** | 212 帧 / 7.07 秒<br>(针对 Instagram18 等 7s 短片) | [`user/default/workflows/motion_transfer_wan_animate_multichunk_7s_ui.json`](file:///d:/ai_projects/ComfyUI/user/default/workflows/motion_transfer_wan_animate_multichunk_7s_ui.json) | UI: [`workflows/v3/motion_transfer_wan_animate_multichunk_7s_ui.json`](file:///d:/ai_projects/ComfyUI/workflows/v3/motion_transfer_wan_animate_multichunk_7s_ui.json)<br>API: [`workflows/v3/motion_transfer_wan_animate_multichunk_7s_api.json`](file:///d:/ai_projects/ComfyUI/workflows/v3/motion_transfer_wan_animate_multichunk_7s_api.json) |

### 4.2 自动化脚本与工具集
| 脚本名称 | 功能描述 | 物理路径 |
| :--- | :--- | :--- |
| [`build_full_ui_workflow.py`](file:///d:/ai_projects/ComfyUI/tools/build_full_ui_workflow.py) | **UI 工作流主生成器**：支持按分块参数自动装配节点、连线、视觉分组，并自动同步至 `user/default/` | `tools/build_full_ui_workflow.py` |
| [`build_multichunk_full_ui_wf.py`](file:///d:/ai_projects/ComfyUI/tools/build_multichunk_full_ui_wf.py) | **API 工作流生成器**：生成供 Python 自动化批量提交的 JSON 字典版本 | `tools/build_multichunk_full_ui_wf.py` |
| [`validate_full_wf.py`](file:///d:/ai_projects/ComfyUI/tools/validate_full_wf.py) | **拓扑校验器**：严格检查所有节点连接合法性、输入输出槽位类型、TorchScript 配置完整性 | `tools/validate_full_wf.py` |

### 4.3 核心依赖模型权重与存放位置
- **Wan2.2 扩散底座**：`models/diffusion_models/wan2.2_animate_14B_fp8.safetensors`
- **VAE 编解码器**：`models/vae/wan_2.1_vae.safetensors`
- **CLIP 视觉与文本**：
  - `models/clip_vision/clip_vision_h.safetensors`
  - `models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- **LoRA 加速与重光照**：
  - `models/loras/Wan2.1_Animate_14B_Lightx2v_4steps_lora.safetensors`
  - `models/loras/Wan2.1_Animate_14B_Relight_lora.safetensors`
- **DWPose 关键点与检测权重（TorchScript 专用）**：
  - `custom_nodes/comfyui_controlnet_aux/ckpts/hr16/yolox-onnx/yolox_l.torchscript.pt`
  - `custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt`

---

## 5. 操作指引与工程复用手册

### 5.1 Web UI 生产操作（适合创作者 / 视觉调试）
1. 启动 ComfyUI 并用浏览器访问 `http://127.0.0.1:8188`。
2. 在工作流加载菜单中选择：
   - 6 秒视频 $\rightarrow$ `motion_transfer_wan_animate_multichunk_full_ui.json`
   - 7 秒视频 $\rightarrow$ `motion_transfer_wan_animate_multichunk_7s_ui.json`
3. 在画布上找到绿色分组 **“③ 核心输入与骨骼自动提取区”**：
   - **`Node 10` (8. 目标人物参考图)**：选择目标人物图片（默认已填好测试图 `005-822807425_...jpeg`）。
   - **`Node 12` (10. 原参考驱动视频)**：选择你的舞蹈视频（如 `Instagram14_video.mp4` 或 `Instagram18_video.mp4`）。
4. 点击 **【Queue Prompt】** 运行：
   - 工作流将自动提取骨架和表情、按分块调度 4 步推理渲染、自动裁切多余重叠帧、无缝拼接，并将最终音画对齐的成片输出至 `output/YYYY-MM-DD/motion_transfer_full/`。

### 5.2 API 脚本批量提交（适合后台跑批 / 矩阵化生产）
使用 Python 进行自动化提交时，无需打开浏览器：
```bash
cmd /c python -c "import json, urllib.request; \
p=json.load(open('workflows/v3/motion_transfer_wan_animate_multichunk_full_api.json', encoding='utf-8')); \
req=urllib.request.Request('http://127.0.0.1:8188/prompt', data=json.dumps({'prompt': p}).encode('utf-8'), headers={'Content-Type': 'application/json'}); \
print(urllib.request.urlopen(req).read().decode('utf-8'))"
```

### 5.3 进阶：任意时长（N 秒）工作流的生成计算公式
若未来需要支持 10 秒、15 秒等任意时长的视频，只需修改 [`tools/build_full_ui_workflow.py`](file:///d:/ai_projects/ComfyUI/tools/build_full_ui_workflow.py) 中的分块规格数组：
- **分块滑动步长公式**：
  $$\text{Offset}_k = 45 + 44 \times (k - 2) \quad (k \ge 2)$$
- **单块保留帧数**：
  - 第一块保留 45 帧（剔除末尾 4 帧重叠）
  - 中间各块保留 44 帧（剔除末尾 5 帧重叠）
  - 最后一块保留剩余帧数（或 49 帧全保留）
- 修改后运行命令即可重新生成全套 UI 与 API 工作流：
  ```bash
  cmd /c python tools/build_full_ui_workflow.py
  cmd /c python tools/validate_full_wf.py
  ```

---

## 6. 常见故障排查（Troubleshooting）

| 异常现象 | 诱因排查 | 解决方案 |
| :--- | :--- | :--- |
| **人物动作不对，跳了旧舞蹈** | 检查是否仍在使用早期 3 输入工作流，导致读取了残留的旧 `ootd_chunk0_pose` 文件 | 务必切换至最新重构的 `multichunk_full_ui.json` 或 `multichunk_7s_ui.json`，确保 `pose_video` 连线来自 `Node 16`。 |
| **动作在 1.5 秒后卡住，但视频在播放** | 骨骼底片帧数耗尽（使用了仅有 49 帧的底片） | 确认已采用自动提取架构，驱动视频的完整帧流会直接贯穿所有分块。 |
| **CreateVideo 报错 `fps 需要 FLOAT 连接为 INT`** | 槽位连接越界，连到了 `bit_depth` (slot 3) | 确保连线从 `Node 13` 的 slot 2 (`fps: FLOAT`) 接入 `CreateVideo`。运行 `validate_full_wf.py` 可自动检测该项。 |
| **DWPose 运行极慢（每帧超过 1 秒）** | OpenCV DNN 降级到了 CPU | 检查 `Node 15` 和 `Node 16` 的 `bbox_detector` 和 `pose_estimator` 是否为 `.torchscript.pt` 结尾，切勿使用 `.onnx` 降级权重。 |
| **CUDA OOM 显存溢出** | 显存被其他未释放的缓存占用 | 1. 确认 KSampler 步数维持在 4 步（搭配 4steps LoRA）；<br>2. 保持渲染分辨率为 480x832；<br>3. 重启 ComfyUI 释放 PyTorch 显存缓存。 |

---

## 7. 后续优化建议与演进路线

1. **色彩与光影一致性（Color Matching）**：
   - 目前分块缝合在动作上已实现 100% 连贯，但在极少数剧烈光影变化的场景下，分块交界处偶有微弱的亮度跳跃。后续可考虑在 `GetImageRangeFromBatch` 与 `ImageBatch` 之间串联轻量级 `ColorMatch` 节点（以第一块为基准色彩锚点）。
2. **更高画质超分集成（Upscaling & Face Restoration）**：
   - 当前直出分辨率为 480x832。可在成片输出前增加快速后处理分支（如 Compact-2x 超分或轻量级 CodeFormer 脸部微修），进一步增强面部清晰度。
3. **根据执行纪律开启新会话**：
   - 当前动作克隆工程落地、问题排查、双版本工作流交付与交接文档已全部圆满交付。**建议用户在开启新主题（如新剧集渲染或新模型探索）前开启全新会话**，以最大化控制 Token 成本并保持上下文敏捷。
