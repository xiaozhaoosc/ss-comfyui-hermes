# ComfyUI 工作流可用性审计 — D:\BaiduNetdiskDownload

> 审计方法：自动解析目录下 52 个工作流 JSON（排除 lora-scripts 配置），提取每个工作流用到的节点类型与模型文件名，与本机「已启用节点」+「磁盘模型」逐一比对。
> 已枚举磁盘模型 150 个；已比对启用/禁用节点 36 个。

## 一、本机环境与资源基线

- **GPU**：RTX 4060 Ti 16GB，**必须 `--lowvram`** 启动；ComfyUI 不会自动起，需手动拉起。
- **已启用节点（14 个）**：ComfyUI-GGUF、ComfyUI-IDM-VTON、ComfyUI-KJNodes、ComfyUI-LLM-Session、ComfyUI-MAINodes、ComfyUI-MimicMotionWrapper、ComfyUI-PlagueKind-Nodes、ComfyUI-ReActor-Nodes、ComfyUI-VFI、ComfyUI-VideoHelperSuite、comfyui-bridge-llm、comfyui-sg-llama-cpp、comfyui_controlnet_aux、rgthree-comfy。
- **禁用节点（22 个，带 .disabled）**：AnimateDiff-Evolved、CatVTON、Impact-Pack、IPAdapter_plus、Jjk-Nodes、MagicAnimate、OOTDiffusion、Portrait-Maker、PuLID-Flux、QwenVL、ReActor(旧)、SeedVR2_VideoUpscaler、WanVideoWrapper、Comfyroll、LayerStyle、essentials、WAS、segment_anything、efficiency-nodes 等。
- **磁盘已有模型**：`flux1-dev-fp8` / `clip_l`、`majicmixRealistic_v7`、Counterfeit / AOM3、`MiniMax H3 全套`（ref2va/fl2va int8、audio vae、qwen3vl、turbo）、`inswapper_128.onnx`（ReActor）、IDM-VTON、`LTX2.3` 的 VAE/音频 VAE/文本投影、`face_yolov8m.pt` / `sam_vit_b` 等。
- **磁盘缺失的关键模型**：`t5xxl_fp16`、`ae.safetensors`（FLUX VAE）、`flux-2-klein*`、`Qwen-Image*` 全系、`LTX2.3-22B*` 大模型与空间放大器、`Wan2.1/2.2 14B*`、`Z-Image*`、各类 FLUX/QWEN/LTX 的 LoRA 与 ControlNet。

## 二、结论总览

| 类别 | 数量 | 说明 |
|---|---|---|
| **可立即跑（小改 1 个节点）** | 2 | 都是 MiniMax H3（文生视频 / 首尾帧） |
| **启用节点 + 下载模型后可跑** | 8 | FLUX 系、AnimateDiff、Wan2.2 remix 等 |
| **基本不可用（缺整套节点生态 + 缺大模型）** | ~42 | InstantID/PuLID/IPAdapter/MagicClothing/LTX/WAN-SCAIL/Z-Image/Qwen-Image 等 |

> 注：约 42 个被标「缺节点(未安装)」的工作流里，真正缺的是整套未安装的节点包（如 LTX 原生节点、SCAIL、InstantID、PuLID、BiRefNet、MagicClothing、OneReward 等）以及 14B~22B 级大模型，单靠启用禁用节点解决不了，需要 git 安装新节点包 + 下载数 GB~20GB 模型。

## 三、立即可跑（2 个，需删 1 个节点）

都在 `8.11MiniMaxH3女团MV\工作流\`：
- `MiniMaxH3文生视频工作流 By 像素幻想Lab.json`
- `MiniMaxH3首尾帧工作流 By 像素幻想Lab (Copy).json`

状态：节点（MAINodes/KJNodes/PlagueKind/MimicMotionWrapper 全启用）+ H3 全套模型均齐备。
**唯一拦路虎**：图里含 `MiniMaxH3MemoryEfficientSageAttentionPatch` 节点，它硬依赖本机**未装**的 `sageattention`，运行期会直接抛 `ModuleNotFoundError` 崩溃。
**修法**：删掉该节点，改用 `MiniMaxChunkFeedForward`（本机已验证可用，见 H3 工作流搭建规范）。
显存：16GB lowvram 可跑，速度偏慢（参考 55s/张级），属本机视频主力链路。

> 同目录的 `MiniMaxH3多参MV生成工作流` 还多缺一个 `AudioDurationToFrames` 节点（全机未安装），无法直接跑。

## 四、启用节点 + 下载模型后可跑（8 个）

这些工作流所需节点包**已安装但被禁用**，且都还缺若干模型文件 → 启用对应包 + 下载模型后即可在本机跑（16GB 显存可行，大模型较慢）。

| 工作流 | 需启用节点 | 还需补的模型（关键） |
|---|---|---|
| `图生视频\AnimateDiff+IPAdapter图生成动画.json`（含 (1) 副本） | AnimateDiff-Evolved、IPAdapter_plus、Impact-Pack | ip-adapter_sd15.bin、mm_sd_v14.ckpt、meinamix 底模、VAE |
| `（赠送）更新工作流1\图片-FLUX-OneReward-遮罩移除.json` | LayerStyle、essentials、WAS | FLUX.1-Turbo-Alpha、ae.safetensors、flux1-fill-dev、t5xxl_fp16 |
| `（赠送）更新工作流1\图片-FLUX-uso风格参考.json` | LayerStyle | ae、t5xxl_fp16、uso lora、sigclip |
| `（赠送）更新工作流1\图片-FLUX-扩图.json` | LayerStyle | ae、t5xxl_fp16、flux1-fill-dev |
| `（赠送）更新工作流1\图片-Qwen基础文生图.json` | SeedVR2_VideoUpscaler、LayerStyle | qwen_image_fp8、qwen_image_vae、qwen_2.5_vl_7b、Lightning lora |
| `（赠送）更新工作流1\图生图-FLUX风格转绘.json` | LayerStyle | ae、t5xxl_fp16、uso lora |
| `（赠送）更新工作流1\视频-wan2.2-remix首尾帧.json` | Impact-Pack | Wan2.2_Remix 14B i2v、umt5-xxl、wan_2.1_vae（~20GB 级，慎选） |

> 提示：`图片-FLUX.json`、`图片-FLUX-遮罩重绘.json`、`图片-FLUX-ControlNet-AUX.json`、`图片-FLUX-FILL-OneReward-遮罩迁移.json`、`图片-FLUX-seedvr2.json` 等基础 FLUX 工作流，其实 `flux1-dev-fp8` 已在磁盘，只差 `t5xxl_fp16` + `ae.safetensors` + 启用 `LayerStyle` + 去掉 SeedVR2 依赖，即可做基本 FLUX 文/图生图。

## 五、基本不可用（代表，缺整套节点生态 + 大模型）

- **LTX 2.3 全套**（单图数字人、二合一、低显存版、图-文-生视频-极速版、首尾帧、电商图专用）：LTX 原生节点包未安装，且需 `ltx-2.3-22b*` 大模型、`gemma_3_12B`、`MelBandRoformer` 等，全缺。
- **WAN-SCAIL 动作迁移（普通/高显存版）**：需 WanVideoWrapper（禁用）+ 未装的 SCAIL/Onnx/VitPose 节点 + 14B 模型。
- **QWEN-Image 全系**（control 姿态、Edit2511、图生图、局部重绘、扩图）：需 `qwen_image_fp8`、`qwen_image_vae`、`qwen_2.5_vl_7b` 等全缺。
- **Z-Image 全系**：模型 `z_image_turbo` 等全缺。
- **换装/角色类**：`神奇服装工作流`(MagicClothing)、`一致的角色创建器`(IPAdapter+Impact+PuLID+PulID)、`万物手办`(PuLID)、`写真/风格化写真/双人婚纱/自制换脸/肖像转证件照/老照片翻新` 等：依赖 InstantID/PuLID/IPAdapter_faceid/BiRefNet/OneReward/ReActor 组合，节点包多处于禁用或未装，模型（ip-adapter、codeformer、controlnet 等）也缺。
- **视频换脸工作流.json**：ReActor 节点已启用、`inswapper_128.onnx` 已在，仅差一个源人脸模型 `face_test.safetensors`（放一张参考脸图即可）。

## 六、运行提示（本机）

- 启动：`python main.py --lowvram --listen 0.0.0.0 --port 8188`（用 anaconda3 的 python）。
- 本机设了 `HTTP_PROXY=127.0.0.1:21193`，访问 `127.0.0.1:8188` 会被代理劫持返 502；本地请求务必绕代理。
- 16GB 显存跑 14B/22B 视频模型（WAN/LTX）可行但慢，建议 lowvram + block swap，单条串行。
