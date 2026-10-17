# A 路线修复方案 + 双人白模法线复现方案

> 日期：2026-10-14 ｜ 环境：RTX 4060 Ti 16GB / ComfyUI 0.39.1（单实例 --lowvram）
> 背景：用户手工跑 A 路线（H3 + 法线 ControlNet）出片 2694×1024 / 362 帧，画面不对。

---

## 一、你那次出片"画面不对"的诊断

上传产物实测：**2694×1024 超宽横屏 @24fps / 362 帧**。

| 问题 | 原因 | 证据 |
|---|---|---|
| **画幅错位**（最大问题） | 源舞蹈 `runcha_dance.mp4` 是 9:16 竖屏（656×1164），而出片是 2.63:1 横屏。跑的链路里带了**横屏高清放大支路**（Aiden 原版的 `MMH3LatentUpscale 1280×704` / `VOSR2 2x` 就是横屏目标），或 ResolutionSelector 被切到横屏 → 人物被 center-crop + 拉伸变形 | Aiden 原版 #138 widget `[...1280, 704...]`；2694×1024 不是 32 网格原生分辨率，是放大支路产物 |
| **ControlNet 可能没生效** | 我此前 4 步 turbo 版全长实测 traj_corr=0.085（≈随机），Aiden 原版 ControlNet 生效依赖 **8 步采样 + 完整采样链** | 见 `tools/SCRIPTS_INVENTORY.md` 十一C |

**v2 修正（已提交，`prompt_id e62d9726`）**，全部改动：
1. **9:16 竖屏锁定**（ResolutionSelector 9:16 / 0.5MP → 544×960），砍掉一切横屏放大支路；
2. **步数 4 → 8**（Aiden #27 原版值），采样器 res_multistep → **euler**（Aiden #26 原版值）；
3. **双 LoRA 贴齐原版**：`Motion_Repair_V2 (0.3)` + `DMAD_4step (1.0)`（两个权重本机都已有）；
4. **ref_video 改喂"白模合成图"**（见第三节），不再是裸法线图——语义塔看到的是"灰色人形"而不是怪异蓝紫法线；
5. ControlNet strength 0.45→**0.6**、end_percent 0.75→**0.9**（转身密集，加强约束）。

提交器：`tools/run_h3_controlnet_transfer.py`（已升级，支持 `--steps/--sampler/--cn-strength/--cn-end/--no-white-model-ref`）。

---

## 二、缺失资源清单（按需手动下载/安装）

### 权重类 —— **全部已就位，一个都不用下载**

| 权重 | 位置 | 状态 |
|---|---|---|
| `minimax_h3_fun_controlnet_union_2.0_pruned_int8_convrot.safetensors` (4.53GB) | `models/model_patches/` | ✅ |
| `h3_upscaler_lms_v0.1_fp32.safetensors` (1.32GB) | `models/latent_upscale_models/` | ✅ |
| `minimax_h3_latent_upscaler_3d_fp16.safetensors` (659MB) | `models/latent_upscale_models/` | ✅ |
| `Motion_Repair_V2.safetensors` (148MB) | `models/loras/` | ✅ |
| `minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16.safetensors` (350MB) | `models/loras/` | ✅ |
| `taeh3.safetensors` (9.3MB) | `models/vae_approx/` | ✅ |
| `moge_3_vitg_fp16.safetensors` (2.39GB) | `models/geometry_estimation/` | ✅ |
| `BiRefNet-general.safetensors` (0.41GB) | `models/background_removal/` | ✅ |

### 插件类 —— 只有跑"Aiden 原版完整链"才需要；**v2 修正版一个都不装也能跑**

v2 已用核心节点替代了全部可选插件（BiRefNet 替代 RMBG、ImageCompositeMasked 替代 ImageBlend V2、RealESRGAN 可替代 VOSR2）。若你日后想 1:1 复原 Aiden 的 71 节点满配（含 SelfLift 高分块放大），再按此清单手动 `git clone` 到 `custom_nodes/` 并**重启 ComfyUI**：

| 插件 | 提供的节点 | 必要性 |
|---|---|---|
| `slmonker/selflift-Avatar` | SelfLiftAvatarH3Sampler / TST | 原版完整链**必需**（v2 不需要） |
| `yichengup/ComfyUI-YCNodes-MiniMax-H3` | H3SigmaRefiner | 原版 sigma 精修（可选增强） |
| `bbaudio-2025/Comfyui-MMH3-UltimateUpscale` | MMH3 三件套 | 原版潜空间放大（可选，注意它默认横屏 1280×704，竖屏要改参数） |
| `comfyui-vosr2` | VOSR2 一步 2x 超分 | 可选（本机 RealESRGAN 可替代） |
| `comfyui-rmbg` | RMBG-2.0 | 可选（核心 BiRefNet 已替代） |
| `comfyui-easy-use` | easy positive | 可选（核心 PrimitiveStringMultiline 已替代） |
| `ComfyUI_LayerStyle`（已装被禁用） | ImageBlend V2 等 | 可选（核心 ImageCompositeMasked 已替代）；启用 = 去掉 `.disabled` 后缀 + 重启 |

---

## 三、"参考视频那种法线白模（有 2 人）"是如何实现的 + 复现方案

### 3.1 真相：Aiden 的白模视频不是工作流生成的

对 Aiden 原版 71 节点工作流逐节点溯源 + 对素材本身探测，结论：

| 素材 | 实测 | 来源 |
|---|---|---|
| `白模1.mp4`（720×1280, 419帧, 平均饱和度≈12） | 3D 软件预先绑骨渲染的**人形木偶**（拔枪动作） | 作者附带成品 |
| `白模2.mp4`（1920×1080, 542帧, 平均饱和度≈3） | Twitter 用户 **@jackchen1919** 制作的"老黄耍枪"白模视频（#104 节点里保留着原推文文件名） | 外部下载的成品 |

工作流里**生产**白模的只有一条支路（给实拍视频转白模用）：

```
#117 抖音视频 → #32 缩放(longest 736) → #100 RMBG-2.0 抠图（灰底 #878787 人像 + 人像 mask）
                                              │
              ┌───────────────────────────────┘
              ▼
   #68 MoGeInference → #67 MoGeRender(normal_opengl 法线图) → #55 透传
                                                              │
   灰底人像(background) + 法线图(layer) + 人像mask ──→ #92 ImageBlend V2
                                                              │
                                              白模合成图（人物=法线着色，背景=纯灰）
                                              ├→ #126 ControlNet.control_video
                                              └→ #12  ref_video_0（喂 Qwen 语义塔）
```

**"有 2 人"就是这些外部素材里本来就有两个人**（双人对手戏）。抠图和法线都是整帧处理，天然支持多人。

### 3.2 复现方案（本机全节点就绪，两人同框零额外成本）

**路线 1：实拍双人视频 → 白模法线视频（推荐，全自动）**

双人与单人的处理完全相同——BiRefNet 和 MoGe 都是整帧模型，一次推理整帧里的所有人：

```
双人驱动视频（两人同框对舞/对打）
  → BiRefNet-general 抠图（两人一起留下，背景剔除）
  → 原帧贴到灰底 #878787
  → MoGe 法线（整帧一次出两人的法线）
  → 法线按人像 mask 贴回灰底
  = 双人白模法线视频
```

这条链**已经在我 v2 提交器里实现**（单人版）：`tools/run_h3_controlnet_transfer.py` 节点 50→51→52/53→55→44→45→46→54。要批量产白模素材，把同一支路单独存成一个工作流即可（下面给现成的 UI 版）。

**生成侧双人注意事项**：
1. `ref_image` 需要两张（`ref_image_0` / `ref_image_1` 各对应一人），Autogrow 端口最多支持 9 张；
2. Prompt 里明确写 `two characters: <Character A> ... <Character B> ...`，让 Qwen 语义塔知道画面是双人；
3. ControlNet 的 `control_video` 是整帧注入，双人骨架/法线一次约束，无需拆分；
4. `length` 与双人驱动视频对齐（H3 17n+5 网格）。

**路线 2：3D 绑骨木偶（白模1 那种）**

Blender / UE 给角色绑骨、赋 Normal/matcap 材质、按动作数据渲染。效果更"干净"但成本高，**不必要**——路线 1 的法线白模在 ControlNet 看来信息量等价（法线图编码的 3D 朝向才是 ControlNet 真正消费的东西）。

### 3.3 现成产物

- v2 白模合成链的 API 版可随时导出：`python tools/run_h3_controlnet_transfer.py --dump-api <路径>`（节点 50-55 就是白模支路）；
- 双人白模 UI 工作流：把 v2 的节点 50-55 支路 + `VHS_VideoCombine` 保存为独立工作流即可，需要时我可以直接生成并装入侧边栏。

---

## 四、验收方式（不变）

```powershell
# v2 出片后：
python tools/motion_fidelity_qa.py --ref-kp output/2026-10-13/motion_optimize/ref/keypoints.json `
  --ref-window 0:277 --ref-search 6 --cand-video <v2产物> `
  --identity-ref input/jia_ref.jpg --every 2 --smooth `
  --json <验证结果.json>
```

闸门：traj_corr≥0.50 / turn_corr≥0.50 / pose_err≤0.30 / 身份cos≥0.50。**四项全过才算 A 路线修复成功**；若 turn_corr 仍短，下一档调参是 strength 0.6→0.8 + end_percent 0.9→1.0。
