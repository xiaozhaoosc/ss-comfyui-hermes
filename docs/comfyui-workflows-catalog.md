# ComfyUI 本地安装 — 工作流与资源目录

> **路径**: `D:\ai_projects\ComfyUI`
> **GPU**: RTX 4060 Ti 16GB VRAM
> **最后更新**: 2026-06-28
> **状态**: 当前未运行

---

## 一、已安装自定义节点（22 个）

### 核心功能节点

| 节点名 | 功能 | 用途 |
|--------|------|------|
| **ComfyUI-Impact-Pack** | 面部检测/分割/增强 | 人脸处理核心 |
| **ComfyUI-ReActor** | 换脸（ReActor 引擎） | 图片/视频换脸 |
| **ComfyUI-Reactor-Nodes** | 换脸辅助节点 | ReActor 扩展 |
| **ComfyUI-IDM-VTON** | 虚拟试穿（IDM-VTON） | AI 换装 |
| **ComfyUI-OOTDiffusion** | OOTDiffusion 换装 | AI 换装（另一方案） |
| **ComfyUI_IPAdapter_plus** | IP-Adapter 图像风格迁移 | 风格参考/人脸保持 |
| **ComfyUI-QwenVL** | Qwen 视觉语言模型 | 图像/视频理解分析 |
| **comfyui_segment_anything** | SAM 图像分割 | 自动抠图/分割 |

### 视频处理节点

| 节点名 | 功能 | 用途 |
|--------|------|------|
| **ComfyUI-VideoHelperSuite** | 视频加载/保存/处理 | 视频工作流核心 |
| **ComfyUI-AnimateDiff-Evolved** | AnimateDiff 动画生成 | 文生动画 |
| **ComfyUI-LTXVideo** | LTX Video 视频生成 | LTX 2.0/2.3 视频 |
| **ComfyUI-MimicMotionWrapper** | 动作迁移 | 参考视频动作迁移 |
| **ComfyUI-SeedVR2_VideoUpscaler** | SeedVR2 视频超分 | AI 视频放大 |

### 图像处理节点

| 节点名 | 功能 | 用途 |
|--------|------|------|
| **comfyui_controlnet_aux** | ControlNet 辅助节点 | 边缘/深度/姿态检测 |
| **ComfyUI_LayerStyle** | 图层样式/合成 | 图像合成/特效 |
| **ComfyUI_essentials** | 基础工具节点 | 常用工具集合 |
| **ComfyUI-GGUF** | GGUF 量化模型支持 | 低显存运行大模型 |
| **rgthree-comfy** | 实用工具节点 | 参数控制/UI 增强 |
| **WAS-Node-Suite** | 综合工具集 | 300+ 工具节点 |
| **ComfyUI-KJNodes** | KJ 工具节点 | 模型优化/QoL |
| **ComfyUI-Jjk-Nodes** | 文本/参数工具 | 文本处理 |

---

## 二、已安装模型

### 2.1 扩散模型（Diffusion Models）— 53GB

| 模型 | 大小 | 类型 | VRAM 需求 | 用途 |
|------|------|------|-----------|------|
| `flux-2-klein-9b-fp8.safetensors` | 8.8GB | FP8 | ~10GB | Flux 2 图像生成（推荐） |
| `flux-2-klein-9b-Q4_K_M.gguf` | 5.6GB | GGUF Q4 | ~7GB | Flux 2 低显存版 |
| `z_image_turbo_bf16.safetensors` | 12GB | BF16 | ~14GB | Z-Image 真实幻想风格 |
| `wan2.1-t2v-1.3b/` | 5.3GB | BF16 | ~8GB | WAN 2.1 文生视频（轻量） |
| `wan2.1-t2v-1.3b-full/` | — | — | — | WAN 2.1 完整版 |
| `wan2.2-ti2v-5b/` | 22GB (3 shards) | BF16 | ~16GB | WAN 2.2 图生视频 |
| `hunyuan_video_720_cfgdistill_fp8_e4m3fn.safetensors` | 13GB | FP8 | ~14GB | 混元视频 720p |
| `ltx-2.3-22b-dev-Q2_K.gguf` | 7.8GB | GGUF Q2 | ~10GB | LTX 2.3 视频生成 |
| `SDXL_Inpainting_q8_0.gguf` | 3.9GB | GGUF Q8 | ~6GB | SDXL 修复/重绘 |
| `seedvr2_3b_fp8_e4m3fn.safetensors` | 3.2GB | FP8 | ~5GB | SeedVR2 视频超分 |

### 2.2 UNet 模型 — 23GB

| 模型 | 大小 | 用途 |
|------|------|------|
| `flux1-fill-dev.safetensors` | 23GB | Flux 1 Fill Dev 修复/重绘 |

### 2.3 Checkpoint 模型 — 28GB

| 模型 | 大小 | 用途 |
|------|------|------|
| `sd_xl_base_1.0.safetensors` | 6.5GB | SDXL 基础模型 |
| `sd_xl_refiner_1.0.safetensors` | 5.7GB | SDXL 精修模型 |
| `sd_xl_base_1.0_inpainting_0.1.safetensors` | 3.0GB | SDXL 修复模型 |
| `cyberrealisticPony_v7.safetensors` | 6.5GB | Pony 真实风格 |
| `anything-v5.safetensors` | 2.0GB | 动漫风格 |
| `v1-5-pruned-emaonly.safetensors` | 4.0GB | SD 1.5 基础 |

### 2.4 VAE 模型

| 模型 | 大小 | 用途 |
|------|------|------|
| `Wan2.2_VAE.pth` | 2.7GB | WAN 2.2 视频 VAE |
| `Wan2.1_VAE.pth` | 485MB | WAN 2.1 视频 VAE |
| `flux2-vae.safetensors` | — | Flux 2 VAE |
| `fluxVaeSft_aeSft.sft` | — | Flux VAE SFT |
| `hunyuan_video_vae_bf16.safetensors` | — | 混元视频 VAE |
| `cogvideox_vae.safetensors` | — | CogVideoX VAE |
| `ema_vae_fp16.safetensors` | — | SD 通用 VAE |

### 2.5 CLIP / 文本编码器

| 模型 | 大小 | 用途 |
|------|------|------|
| `t5xxl_fp16.safetensors` | — | T5-XXL FP16（Flux/WAN 用） |
| `t5xxl_fp8_e4m3fn.safetensors` | — | T5-XXL FP8（低显存） |
| `t5xxl_fp8_e4m3fn_scaled.safetensors` | — | T5-XXL FP8 缩放版 |
| `t5-v1_1-xxl-encoder-Q3_K_M.gguf` | — | T5-XXL GGUF Q3（最低显存） |
| `clip_l.safetensors` | — | CLIP-L |
| `siglip-so400m-patch14-384/` | — | SigLIP（Flux 2 用） |

### 2.6 LoRA 模型

| 模型 | 大小 | 用途 |
|------|------|------|
| `kook_zimage_realistic_fantasy_turbo.safetensors` | 163MB | Z-Image 真实幻想 Turbo |
| `Kook_Zimage_真实幻想_Turbo.safetensors` | 163MB | 同上（中文名备份） |
| `Flux  Realistic Asian girls face Flux_01.safetensors` | 147MB | Flux 亚洲人脸 |
| `flux_lora_cute_korean_girl_v1.safetensors` | 165MB | Flux 韩国女孩 |
| `flux_lora_cute_korean_girl_v1_fp8.safetensors` | 83MB | 同上 FP8 版 |
| `FLUX-dev-lora-Logo-Design.safetensors` | 37MB | Flux Logo 设计 |
| `super-realism.safetensors` | 585MB | 超级写实风格 |
| `unfiltered_realism_v2.safetensors` | 82MB | 无滤镜写实 |
| `watercolor_sdxl.safetensors` | 325MB | SDXL 水彩风格 |

### 2.7 ControlNet 模型

| 模型 | 用途 |
|------|------|
| `controlnet_union_sdxl.safetensors` | SDXL ControlNet Union |
| `control_v11p_sd15_openpose.pth` | SD1.5 OpenPose |
| `diffusers_xl_depth_full.safetensors` | SDXL 深度图 |

### 2.8 其他模型

| 目录 | 内容 |
|------|------|
| `upscale_models/` | RealESRGAN x2/x4/x2-anime |
| `ipadapter/` | IP-Adapter Plus SDXL |
| `insightface/` | buffalo_l + inswapper_128（换脸用） |
| `reactor/` | ReActor 人脸模型 |

---

## 三、蓝图工作流（81 个）

### 3.1 文生图 (Text to Image) — 10 个

| 工作流 | 模型 | VRAM | 说明 |
|--------|------|------|------|
| `Text to Image (Flux.2 Dev).json` | Flux 2 Dev | ~10GB | **推荐** Flux 2 FP8 |
| `Text to Image (Flux.1 Dev).json` | Flux 1 Dev | ~12GB | Flux 1 |
| `Text to Image (Flux.1 Krea Dev).json` | Flux 1 Krea | ~12GB | Flux Krea 风格 |
| `Text to Image (Z-Image-Turbo).json` | Z-Image Turbo | ~14GB | 真实幻想风格 |
| `Text to Image (Z-Image-Base).json` | Z-Image Base | ~14GB | Z-Image 基础 |
| `Text to Image (Qwen-Image).json` | Qwen-Image | — | 通义千问生图 |
| `Text to Image (Qwen-Image 2512).json` | Qwen-Image 2512 | — | Qwen 新版 |
| `Text to Image (Anima).json` | Anima | — | Anima 生图 |
| `Text to Image (Ernie Image).json` | 文心一格 | — | 百度文心 |
| `Text to Image (Ernie Image Turbo).json` | 文心一格 Turbo | — | 百度文心快速版 |
| `Text to Image (NetaYume Lumina).json` | NetaYume | — | 动漫风格 |
| `Text to Image.json` | 默认 | — | 默认工作流 |

### 3.2 图生图 / 图像编辑 — 8 个

| 工作流 | 说明 |
|--------|------|
| `Image Edit (Flux.2 Dev).json` | Flux 2 图像编辑 |
| `Image Edit (Flux.2 Klein 4B).json` | Flux 2 Klein 编辑 |
| `Image Edit (Qwen 2509).json` | Qwen 图像编辑 |
| `Image Edit (Qwen 2511).json` | Qwen 新版编辑 |
| `Image Edit (FireRed Image Edit 1.1).json` | FireRed 编辑 |
| `Image Edit (LongCat Image Edit).json` | LongCat 编辑 |
| `Image Inpainting (Flux.1 Fill Dev).json` | Flux 修复/重绘 |
| `Image Inpainting (Qwen-image).json` | Qwen 修复 |
| `Image Outpainting (Qwen-Image).json` | Qwen 扩展画布 |

### 3.3 图生视频 (Image to Video) — 5 个

| 工作流 | 模型 | 说明 |
|--------|------|------|
| `Image to Video (Wan 2.2).json` | WAN 2.2 5B | **推荐** 图生视频 |
| `Image to Video (LTX-2.3).json` | LTX 2.3 22B | LTX 图生视频 |
| `First-Last-Frame to Video (LTX-2.3).json` | LTX 2.3 | 首尾帧生成视频 |
| `First-Last-Frame to Video.json` | — | 默认首尾帧 |
| `Canny to Video (LTX 2.0).json` | LTX 2.0 | 边缘图生视频 |

### 3.4 文生视频 (Text to Video) — 2 个

| 工作流 | 模型 | 说明 |
|--------|------|------|
| `Text to Video (Wan 2.2).json` | WAN 2.2 5B | **推荐** 文生视频 |
| `Text to Video (LTX-2.3).json` | LTX 2.3 22B | LTX 文生视频 |

### 3.5 视频处理 — 8 个

| 工作流 | 说明 |
|--------|------|
| `Video Upscale(GAN x4).json` | GAN 4x 视频超分 |
| `Video Inpainting (Wan2.1 VACE).json` | WAN VACE 视频修复 |
| `Video Inpaint (VOID).json` | VOID 视频修复 |
| `Video Stitch.json` | 视频拼接 |
| `Merge Videos.json` | 视频合并 |
| `Frame Interpolation.json` | 帧插值 |
| `Video Captioning (Gemini).json` | Gemini 视频描述 |
| `Video Depth Estimation (MoGe).json` | 视频深度估计 |
| `Video Face Detection (Mediapipe).json` | 视频人脸检测 |
| `Video Segmentation (SAM3).json` | 视频分割 |
| `Video to Pose Map (SDPose Multi-Person).json` | 视频姿态提取 |

### 3.6 ControlNet — 4 个

| 工作流 | 说明 |
|--------|------|
| `ControlNet (Z-Image-Turbo).json` | Z-Image ControlNet |
| `Canny to Image (Z-Image-Turbo).json` | 边缘图 ControlNet |
| `Depth to Image (Z-Image-Turbo).json` | 深度图 ControlNet |
| `Depth to Video (ltx 2.0).json` | 深度图生视频 |
| `Pose to Image (Z-Image-Turbo).json` | 姿态图 ControlNet |
| `Pose to Video (LTX 2.0).json` | 姿态图生视频 |

### 3.7 分割/检测/深度 — 6 个

| 工作流 | 说明 |
|--------|------|
| `Image Segmentation (SAM3).json` | SAM3 图像分割 |
| `Image Face Detection (Mediapipe).json` | Mediapipe 人脸检测 |
| `Image Depth Estimation (Lotus Depth).json` | Lotus 深度估计 |
| `Image Depth Estimation (MoGe).json` | MoGe 深度估计 |
| `Image to Pose Map (SDPose Multi-Person).json` | 多人姿态 |
| `Image to Pose Map (SDPose-OOD).json` | OOD 姿态 |
| `Geometry Estimation (MoGe).json` | MoGe 几何估计 |
| `Remove Background (BiRefNet).json` | BiRefNet 背景去除 |

### 3.8 3D / 音频 / 其他 — 10 个

| 工作流 | 说明 |
|--------|------|
| `Image to Model (Hunyuan3d 2.1).json` | 混元 3D 模型生成 |
| `Image to Layers(Qwen-Image-Layered).json` | Qwen 图层分离 |
| `Text to Audio (ACE-Step 1.5).json` | ACE 文生音频 |
| `Audio Generation (Stable Audio 3 Medium).json` | Stable Audio 音频 |
| `Audio Generation (Stable Audio 3 Medium Base).json` | Stable Audio 基础版 |
| `Image Upscale(Z-image-Turbo).json` | Z-Image 超分 |
| `Image Captioning (gemini).json` | Gemini 图像描述 |
| `Prompt Enhance.json` | 提示词增强 |
| `Get Any Video Frame.json` | 视频帧提取 |

### 3.9 图像处理工具 — 14 个

| 工作流 | 说明 |
|--------|------|
| `Brightness and Contrast.json` | 亮度/对比度 |
| `Color Adjustment.json` | 颜色调整 |
| `Color Balance.json` | 色彩平衡 |
| `Color Curves.json` | 曲线调整 |
| `Hue and Saturation.json` | 色相/饱和度 |
| `Image Levels.json` | 色阶 |
| `Image Blur.json` | 模糊 |
| `Edge-Preserving Blur.json` | 保边模糊 |
| `Unsharp Mask.json` | USM 锐化 |
| `Sharpen.json` | 锐化 |
| `Chromatic Aberration.json` | 色差效果 |
| `Film Grain.json` | 胶片颗粒 |
| `Glow.json` | 发光效果 |
| `Image Channels.json` | 通道分离 |
| `Crop Images 2x2.json` / `3x3.json` | 图像裁切 |
| `Split Image Grid to Tiles.json` | 网格切分 |
| `Select Per-Line Text by Index.json` | 文本选择 |

---

## 四、用户自定义工作流

### 4.1 换脸系列

| 文件 | 说明 |
|------|------|
| `user/default/workflows/faceswap_image_reactor.json` | ReActor 图片换脸 |
| `user/default/workflows/faceswap_video_reactor.json` | ReActor 视频换脸 |
| `workflows/v1/faceswap_image_reactor.json` | v1 版图片换脸 |
| `workflows/v1/faceswap_video_reactor.json` | v1 版视频换脸 |
| `workflows/v1/batch_faceswap_video_api.json` | 批量视频换脸 API |
| `workflows/v1/flux_klein_faceswap.json` | Flux Klein + 换脸 |
| `workflows/v1/flux_klein_faceswap_api.json` | Flux Klein 换脸 API |
| `workflows/flux_klein_faceswap_api.json` | 同上（顶层） |
| `workflows/v1/reactor_test_api.json` | ReActor API 测试 |

### 4.2 换装系列

| 文件 | 说明 |
|------|------|
| `workflows/v1/faceswap_outfit_pipeline.json` | 换脸+换装 pipeline |
| `workflows/v1/standard_image_outfit.json` | 标准图片换装 |
| `workflows/v1/standard_image_outfit_faceprotect.json` | 换装+人脸保护 |
| `workflows/v1/standard_video_outfit.json` | 标准视频换装 |
| `workflows/v1/ootd_test.json` | OOTDiffusion 测试 |
| `workflows/v1/outfit_swap_sam_test.json` | SAM 换装测试 |
| `workflows/v1/outfit_swap_sam_test_api.json` | SAM 换装 API |
| `workflows/v1/video_outfit_controlnet.json` | ControlNet 视频换装 |
| `workflows/v1/sdxl_inpaint_clothing_removal.json` | SDXL 衣物移除 |
| `workflows/idm_vton_*.json` (7 个) | IDM-VTON 虚拟试穿系列 |

### 4.3 视频生成

| 文件 | 说明 |
|------|------|
| `workflows/v1/standard_video_gen.json` | 标准视频生成 |
| `workflows/v1/ltxv_23_gguf_hires.json` | LTX 2.3 GGUF 高清 |
| `workflows/v1/ltxv_23_gguf_optimized.json` | LTX 2.3 GGUF 优化 |
| `workflows/v1/mimicmotion_motion_transfer.json` | MimicMotion 动作迁移 |
| `workflows/wan21_test.json` | WAN 2.1 测试 |
| `workflows/zombie_optimized_640x384.json` | 僵尸女友优化版 |

### 4.4 超分/增强

| 文件 | 说明 |
|------|------|
| `workflows/v1/seedvr2_upscale_api.json` | SeedVR2 超分 API |
| `workflows/v1/standard_seedvr2_upscale.json` | 标准 SeedVR2 超分 |

### 4.5 Z-Image 系列

| 文件 | 说明 |
|------|------|
| `workflows/v1/standard_zimage_realskin.json` | Z-Image 真实皮肤 |
| `workflows/v1/standard_zimage_realskin_lite.json` | Z-Image 轻量版 |
| `workflows/RunComfyZ-Image-Real-Skin.json` | RunComfy Z-Image |

### 4.6 Flux Klein 系列

| 文件 | 说明 |
|------|------|
| `workflows/RunComfyFlux-Klein-Face-Swap.json` | Flux Klein 换脸 |
| `workflows/RunComfyFlux-Klein-Face-Swap-GGUF.json` | 同上 GGUF 版 |

### 4.7 数字人

| 文件 | 说明 |
|------|------|
| `user/default/workflows/数字人kenstandard_image_数据人ken_pro.json` | Ken 数字人形象 |

---

## 五、可运行工作流速查表

### ✅ 16GB VRAM 可直接运行

| 能力 | 工作流 | 模型 | VRAM |
|------|--------|------|------|
| 文生图 | `Text to Image (Flux.2 Dev)` | Flux 2 Klein FP8 | ~10GB |
| 文生图 | `Text to Image (Flux.1 Dev)` | Flux 1 Fill Dev | ~12GB ⚠️ |
| 文生图 | `Text to Image (Qwen-Image)` | Qwen-Image | — |
| 图生视频 | `Image to Video (Wan 2.2)` | WAN 2.2 5B | ~16GB ⚠️ |
| 文生视频 | `Text to Video (Wan 2.2)` | WAN 2.2 5B | ~16GB ⚠️ |
| 文生视频 | `Text to Video (LTX-2.3)` | LTX 2.3 Q2 | ~10GB |
| 视频超分 | `Video Upscale(GAN x4)` | RealESRGAN | ~2GB |
| 视频超分 | SeedVR2 | SeedVR2 FP8 | ~5GB |
| 换脸 | ReActor 工作流 | inswapper_128 | ~2GB |
| 换装 | IDM-VTON 工作流 | IDM-VTON | ~8GB |
| 分割 | SAM3 工作流 | SAM3 | ~4GB |
| 背景去除 | BiRefNet 工作流 | BiRefNet | ~4GB |
| 深度估计 | MoGe/Lotus | MoGe/Lotus | ~4GB |
| 音频生成 | Stable Audio 3 | Stable Audio | ~4GB |

### ⚠️ 接近极限（需关闭其他程序）

| 能力 | 模型 | VRAM |
|------|------|------|
| Z-Image 生图 | z_image_turbo_bf16 | ~14GB |
| WAN 2.1 完整版 | wan2.1-t2v-1.3b-full | ~14GB |
| WAN 2.2 5B | wan2.2-ti2v-5b | ~16GB |

### ❌ 16GB VRAM 不可运行

| 模型 | 大小 | 原因 |
|------|------|------|
| Flux 1 Fill Dev | 23GB | 需 24GB+ VRAM |
| Hunyuan Video 720p | 13GB FP8 | 推理需 20GB+ |
| Z-Image Turbo BF16 | 12GB | 推理需 18GB+ |

---

## 六、磁盘占用

| 目录 | 大小 |
|------|------|
| diffusion_models/ | ~53GB |
| unet/ | ~23GB |
| checkpoints/ | ~28GB |
| loras/ | ~1.8GB |
| clip/ | ~15GB (估) |
| vae/ | ~8GB |
| 其他模型 | ~5GB |
| **总计** | **~134GB** |

---

*文档路径: `D:\ai_projects\ComfyUI\docs\comfyui-workflows-catalog.md`*
*知识库同步: `D:\obsidian\obsidian\AI工具\ComfyUI-工作流目录.md`*
