# ComfyUI 工作流资产清单

> 生成时间：2026-09-21 ｜ 机器：Windows / RTX 4060 Ti 16GB ｜ ComfyUI 1.44.19
> 扫描范围：`user/`、`workflows/`、`tools/workflows/`、`.trae/skills/`、`models/`
>
> ⚠️ **重要**：本清单初版基于文件扫描；**已用实跑验证并修正**（见第六节）。
> 表中标 ⚠️ 的工作流，除节点缺失外，多数还**缺模型本体**，实际为「有图无模型」。
> 真正可跑通的底模只有 **SD1.5×3 + Flux Dev**（详见 6.1）。

---

## 一、环境速览

| 项目 | 值 |
|---|---|
| 启动命令 | `python main.py --lowvram --listen 0.0.0.0 --port 8188` |
| Python | anaconda3（**非** venv） |
| 显存 | RTX 4060 Ti 16GB，必须 `--lowvram` |
| 模型根目录 | `D:\ai_projects\ComfyUI\models` → Junction → `D:\OLLAMA_MODELS\models` |
| 已知约束 | numpy 必须 1.26.4；>14GB 显存需警惕 OOM |

---

## 二、分类总表

> 状态图例：✅ 实测可跑 ｜ ⚠️ 缺节点或缺模型 ｜ 🗄️ 已弃用
> 「缺模型」判定依据：`CheckpointLoaderSimple` / `UnetLoaderGGUF` 的实际枚举结果。

### 类别 A — 图片生成 / 编辑

| 工作流文件 | 能力 | 模型 | 节点/模型状态 | 可用性 |
|---|---|---|---|---|
| `v3/krea2_t2i_workflow.json` | KREA-2 文生图 | KREA-2-TURBO | **模型缺失** | ❌ 不可跑 |
| `v3/krea2_turbo_fp8_native.json` | KREA-2 Turbo FP8 | KREA-2-TURBO(fp8) | **模型缺失** | ❌ 不可跑 |
| `v3/krea2_turbo_gguf_fork.json` | KREA-2 Turbo GGUF | KREA-2-TURBO(gguf) | **模型缺失** | ❌ 不可跑 |
| `v3/Rebels_KREA-2-TURBO.json` | KREA-2 叛逆版 | KREA-2-TURBO | **模型缺失** | ❌ 不可跑 |
| `v1/standard_zimage_realskin.json` | Z-Image 真实皮肤人像 | z_image_turbo_bf16 | **模型缺失** + QwenVL/Jjk 禁用 | ❌ 不可跑 |
| `v1/standard_flux_faceswap.json` | Flux2 生图→换脸→超分 | flux-2-klein-9b | **模型缺失** + SeedVR2 禁用 | ❌ 不可跑 |
| `user/workflows/qwen_image_edit.json` | Qwen-Image 图片编辑 | Qwen-Image | **模型缺失** | ❌ 不可跑 |
| `v1/standard_image_outfit.json` | SAM分割+SDXL 图片换装 | sd_xl_base_1.0, sam_vit_b | **SDXL缺失** + SAM/Impact 禁用 | ❌ 不可跑 |
| `v1/standard_image_outfit_faceprotect.json` | 换装+面部保护 | sd_xl_base_1.0 | **SDXL缺失** + Impact 禁用 | ❌ 不可跑 |
| `v1/sdxl_inpaint_clothing_removal.json` | 去衣局部重绘 | SDXL | **SDXL缺失** | ❌ 不可跑 |
| `v1/ra_inpaint_ipadapter_reactor.json` | 局部重绘+IPAdapter+换脸 | SDXL | **SDXL缺失** + IPAdapter 禁用 | ❌ 不可跑 |
| `user/default/workflows/数字人kenstandard_image_数据人ken_pro.json` | 数字人 Ken Pro | — | 空壳（245B） | ❌ 无效文件 |
| **★ 实测可用：直接用 SD1.5 底模跑 txt2img** | 写实/动漫人像 | majicmix / Counterfeit / AOM3 | 全部就绪 | ✅ **9~10 s/张** |
| **★ 实测可用：Flux Dev FP8 txt2img** | 高保真写实 | flux1-dev-fp8 | 全部就绪 | ✅ **55 s/张** |
| `v1/ootd_test.json` / `outfit_swap_sam_test.json` | 穿搭/换装测试 | SDXL+SAM | 缺模型缺节点 | ❌ |

### 类别 B — 换脸（Face Swap）

| 工作流文件 | 能力 | 模型 | 节点依赖 | 状态 |
|---|---|---|---|---|
| `v1/faceswap_image_reactor.json` | 图片换脸（标准） | inswapper_128, GFPGANv1.4 | ComfyUI-ReActor-Nodes | ✅ 可用 |
| `v1/faceswap_video_reactor.json` | 视频换脸（标准） | inswapper_128, GFPGANv1.4 | ReActor, VideoHelperSuite | ✅ 可用 |
| `user/default/workflows/faceswap_video_reactor_260805_v2_手动确认帧率.json` | 视频换脸 v2（手动帧率） | 同上 | 同上 | ✅ 最新 |
| `v1/video_faceswap_reactor.json` | 视频换脸（旧） | 同上 | 同上 | 🗄️ 弃用 |
| `v1/flux_klein_faceswap.json` + `_api.json` | Flux Klein 换脸 | flux-2-klein | ReActor | ✅ |
| `v3/flux_pulid_workflow_api.json` | Flux PuLID 换脸 | flux + PuLID | PuLID-Flux(禁用) | ⚠️ 节点缺失 |
| `v1/faceswap_outfit_pipeline.json` | 换脸→换装串联 | 多模型 | IDM-VTON, Impact(禁用) | ⚠️ 部分缺失 |
| `tools/workflows/done/faceswap_video_reactor_260804_v3/v4.json` | 视频换脸迭代版 | 同上 | 同上 | ✅ 可用 |
| `tools/workflows/done/faceswap_video_reactor_260806_v3_opt.json` | 视频换脸 8/06 优化版 | 同上 | 同上 | ✅ 推荐 |
| `tools/workflows/done/faceswap_tryon_combo_v1.json` | 换脸+试穿组合 | 多模型 | 多 | ✅ |

### 类别 C — 视频生成（文生视频 / 图生视频）

| 工作流文件 | 能力 | 模型 | 节点/模型状态 | 可用性 |
|---|---|---|---|---|
| `v1/h3_t2va_audio_ui_v2.json` + `user/default/.../h3_t2va_audio_ui_v2_2.json` | **MiniMax H3 文生视频+原生音频** | minimax_h3_ref2va, qwen3vl_32b, h3 video/audio vae | 节点+模型**齐全** | ✅ 推荐 |
| `v1/h3_t2va_audio_api.json` | H3 文生视频+音频（API 格式） | 同上 | 齐全 | ✅ |
| `v1/h3_t2va_segment.json` / `_audio.json` | H3 分段模板（纯视频 / 带音频） | 同上 | 齐全 | ✅ |
| `v1/h3_t2va_loadtest.json` | H3 压测模板 | 同上 | 齐全 | ✅ |
| `v1/h3_xinniang_v1_workflow.json` | H3 新娘主题 v1 | 同上 | 齐全 | ✅ |
| `user/default/workflows/h3_文生视频+音频_v2.json` | H3 文生视频+音频（画布版） | 同上 | 齐全 | ✅ |
| `user/default/workflows/h3_烽火边关_文生视频+音频.json` | H3「烽火边关」预告片 | 同上 | 齐全 | ✅ |
| `v1/standard_video_gen.json` | LTX 2.3 文生视频 | ltx-2.3-22b, gemma_3_12B | LTXVideo 节点缺失 | ❌ 不可跑 |
| `v1/PinkCherry_LTX23_NSFW_Workflow_v1_8_16G_optimized.json` | LTX 2.3 16G 优化版 | PinkCherry LTX23 gguf（**模型在**） | LTXVideo 节点缺失 | ⚠️ 启用节点可用 |
| `v3/wan21_test.json` | Wan 2.1 测试 | wan2.1 | 缺模型 + WanWrapper 禁用 | ❌ |
| `tools/workflows/zombie_optimized_640x384.json` | 僵尸短片优化版 | LTX | LTXVideo 节点缺失 | ⚠️ |
| `tools/workflows/wan2_zombie_girlfriend_prompts.json` | Wan2 僵尸女友提示词 | wan2 | 缺模型 + 节点禁用 | ❌ |

### 类别 D — 视频换装 / 虚拟试穿（VTON）

| 工作流文件 | 能力 | 模型 | 节点依赖 | 状态 |
|---|---|---|---|---|
| `v1/standard_video_outfit.json` | 深度 ControlNet+SDXL 视频换装 | sd_xl_base_1.0, diffusers_xl_depth | controlnet_aux, VHS | ✅ 可用 |
| `v1/video_outfit_controlnet.json` | 视频换装 ControlNet 版 | 同上 | 同上 | ✅ |
| `v1/standard_image_outfit.json` | 图片换装（SAM） | SDXL + SAM | SAM(禁用) | ⚠️ |
| `tools/workflows/idm_vton_*.json`（12 个） | IDM-VTON 虚拟试穿系列 | IDM-VTON 全套 | ComfyUI-IDM-VTON | ✅ 可用 |
| `tools/workflows/idm_vton_hq_workflow.json` | IDM-VTON 高清版 | IDM-VTON | ComfyUI-IDM-VTON | ✅ 推荐 |
| `tools/workflows/idm_vton_tryon_api.json` | IDM-VTON API 格式 | IDM-VTON | 同上 | ✅ |
| `workflows/avatar_wf3_cloth_swap.json` | Avatar 换衣（15步加速） | IDM-VTON | 同上 | ✅ |

### 类别 E — 动作迁移 / 数字人

| 工作流文件 | 能力 | 模型 | 节点依赖 | 状态 |
|---|---|---|---|---|
| `v1/mimicmotion_motion_transfer.json` | MimicMotion 动作迁移 | MimicMotionMergedUnet | MimicMotionWrapper, SVD | ✅ 可用 |
| `workflows/avatar_wf4_motion_transfer.json` | Avatar 动作迁移 | MimicMotion | 同上 | ✅ |
| `workflows/avatar_wf1_head_swap.json` | SAM 换头 | SAM | SAM(禁用) | ⚠️ |
| `workflows/avatar_wf2_face_swap.json` | ReActor 换脸 (codeformer 0.75) | inswapper + codeformer | ReActor | ✅ |
| `workflows/avatar_wf5_full_pipeline.json` | 全链完整版 768×1344/124帧 | 全套 | 多 | ⚠️ 未出成片 |
| `workflows/avatar_wf5_short_v2.json` | 全链短版 480×832/22帧/6步 | 全套 | 多 | ✅ 实测 590s |
| `workflows/avatar_wf5_short_v2_canvas.json` | 短版画布版（带中文注释） | 全套 | 多 | ✅ 日常推荐 |
| `user/default/workflows/数字人kenstandard_image_数据人ken_pro.json` | 数字人 Ken Pro | — | — | ⚠️ 仅 245B（空壳） |

> 全链顺序：换衣(IDM-VTON) → 换脸(ReActor) → 动作迁移(MimicMotion) → H3 图生视频

### 类别 F — 超分 / 修复 / 增强

| 工作流文件 | 能力 | 模型 | 节点依赖 | 状态 |
|---|---|---|---|---|
| `v1/standard_seedvr2_upscale.json` + `_api.json` | SeedVR2 超分辨率 | seedvr2_3b_fp8 | SeedVR2(禁用) | ⚠️ 节点缺失 |
| `.trae/skills/comfyui/workflows/upscale_4x.json` | ESRGAN 4× 放大 | 4x-UltraSharp | 原生 | ✅ |
| `tools/workflows/todo/ComfyUI之抠图之王Birefnet II抠图工作流.json` | BiRefNet 抠图 | BiRefNet-general | RMBG | ✅ 模型就绪 |

### 类别 G — 学习 / 官方模板（`.trae/skills/`）

| 分组 | 文件 | 说明 |
|---|---|---|
| `comfyui/workflows/` | sd15_txt2img, sdxl_txt2img, sdxl_img2img, sdxl_inpaint, flux_dev_txt2img, animatediff_video, wan_video_t2v, upscale_4x | 8 个基础 API 格式模板 |
| `comfyui-workflow-master/templates/` | sd15 / sdxl / flux / sd3 / wan22 / hunyuan / ltxv / cosmos / mochi / stable-cascade / stable-audio / hunyuan3d / upscale | 30+ 个模型模板 |
| `comfyui-workflow-master/templates/comfyui_LLM_party/` | llm-chat-api, llm-chat-ollama, llm-prompt-enhance, llm-script-to-video | LLM 集成模板 |
| `comfyui-workflow-master/references/nodes/` | 01-loaders ~ 42-debug-misc | 42 份节点参考文档 |

### 类别 H — 社区下载素材（`workflows/todo/`，待整理）

| 主题 | 文件举例 |
|---|---|
| 换脸 | 换脸工作流, instant id 换脸, PhotoMaker_换脸, ReActor+肖像大师, IPAdapter人脸迁移 |
| 换装 | 换装工作流, 简易换装, FitDiT 换装, 模特一键换衣-电商, 服装制作工作流 V2 |
| 换背景 | 换背景工作流, 商品换背景, 产品摄影换背景, RMBG 背景移除 |
| 人像 | 一键人像摄影 v3, 超细节 8k, 简化后模特生成, 人物一键生成多姿势图 |
| 动作 | 固定人像换指定动作, Kontext 换姿势, 人物动作背景个性化 |
| 视频 | 短片图生视频, AnimateDiff 无闪烁, Phantom 多主体, 视频动作迁移 WAN2.1-VACE-14B |
| 其他 | 换发色, 老照片上色修复, 生成透明背景素材, 混合工作流, qwen—image 万物迁移合集 |

> ⚠️ 这些为社区下载件，多数依赖未安装节点（Impact-Pack、IPAdapter、LayerStyle、Comfyroll、WAS、efficiency-nodes 均在 `.disabled`），**不能直接运行**，仅作参考/移植来源。

---

## 三、模型资产清单

> ✅ = 已实测可加载并出图 ｜ 文件存在但未验证的标注大小

### checkpoints（`models/checkpoints/`）— 全部实测可用
| 模型 | 大小 | 类型 | 实测 |
|---|---|---|---|
| Counterfeit-V3.0_fp16.safetensors | 4.0 GB | SD1.5 动漫（冷调） | ✅ 10.3 s/张 |
| majicmixRealistic_v7.safetensors | 2.0 GB | SD1.5 写实 | ✅ 9.2 s/张 |
| AOM3A3_orangemixs.safetensors | 2.0 GB | SD1.5 动漫（暖调） | ✅ 9.9 s/张 |
| sd15_legacy/（SD1.5 全套 + ControlNet inpaint/openpose） | ~6.3 GB | SD1.5 基础组件 | — |

### unet / diffusion_models
| 模型 | 大小 | 加载器 | 实测 |
|---|---|---|---|
| flux1-dev-fp8.safetensors | 11.4 GB | `UNETLoader` | ✅ 54.9 s/张 |
| T8-flux.1-dev-abliterated-V2-GGUF-Q8_0 | 12.1 GB | `UnetLoaderGGUF` | ❌ **超显存跑不动** |
| T8-flux.1-dev-abliterated-V2-GGUF-Q6_K | 9.4 GB | `UnetLoaderGGUF` | 未测（建议） |
| T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M | 6.6 GB | `UnetLoaderGGUF` | 未测（本机合理档） |
| PinkCherry_FineTune_Q5_K_M_v18_LTX23.gguf | 15.2 GB | `UnetLoaderGGUF` | LTX 节点缺失 |
| minimax_h3_ref2va / fl2va / fused（int8） | 各 20.0 GB | `UNETLoader` | H3 视频主模型 ✅ |

### text_encoders
| 模型 | 大小 | 用途 |
|---|---|---|
| qwen3vl_32b_minimax_h3_int8_convrot | 25.9 GB | H3 编码器（int8） |
| gemma-3-12b-it-heretic-v2.safetensors | 23.3 GB | LTX 2.3 编码器（越狱版） |
| gemma-4-31b-jang-crack-Q4_K_M / Q3_K_M.gguf | 17.8 / 14.6 GB | Gemma 4 31B |
| qwen3vl_32b_heretic_minimax_h3_nvfp4 | 15.0 GB | H3 编码器（越狱版，推荐） |
| qwen3vl_32b_minimax_h3_nvfp4_awq | 15.0 GB | H3 编码器（官方版，备份） |
| gemma-3-12b-it-heretic-v2-Q5_K_M.gguf | 8.1 GB | LTX 编码器量化版 |
| t5xxl_fp8_e4m3fn.safetensors | 4.7 GB | **Flux T5 编码器（实测在用）** |
| ltx-2.3_text_projection_bf16.safetensors | 2.2 GB | LTX 文本投影 |
| clip_l.safetensors | 0.2 GB | **Flux CLIP-L（实测在用）** |

### vae
| 模型 | 大小 | 用途 |
|---|---|---|
| minimax_h3_video_vae_fp16 | 5.0 GB | H3 视频 VAE |
| minimax_h3_video_vae_int8_convrot | 3.0 GB | H3 视频 VAE（int8） |
| LTX23_video_vae_bf16 | 1.4 GB | LTX 2.3 视频 VAE |
| minimax_h3_audio_vae_fp32 | 0.6 GB | **H3 音频 VAE（原声输出）** |
| LTX23_audio_vae_bf16 | 0.3 GB | LTX 2.3 音频 VAE |
| **flux-vae-bf16.safetensors** | 0.2 GB | **Flux VAE（实测在用）** |
| vae-ft-mse-840000-ema-pruned.ckpt | — | SD1.5 VAE（Loader 可见） |
| taeltx2_3 | 0.02 GB | LTX 2.3 TAESD |

### loras（18 个）
| 分组 | 模型 |
|---|---|
| H3 加速 | minimax_h3_turbo_4step_ckpt500、turbo_v4_step600_ema_pruned、turbo_4step_comfyui_pruned、temporal_expansion_step375_r16 |
| LTX | LTX-2.3/ltx-2.3-22b-distilled-lora-384-1.1（7.3 GB） |
| 亚洲人像（Flux 系） | hinaFluxDevAsianMix_v12、hina_flux2klein4b_asianMix_v4.0、hinaFluxSchnellAsianMix_v25、hina_flux2Klein9b_asianMix_v1.4、hinaFluxKreaAsianMix_v19-rev2、hinaFluxKreaAsianMix_v195、NexBlend Asian 01 |
| 其他 | my_flux_lora_v1（自训）、thai_shorty_zimgT、ppango_women、flux-ppango、Thai_shorty_F1D、FilmVelvia3 |

### 其他模型目录
| 目录 | 内容 |
|---|---|
| `controlnet/` | flux_controlnet_union_pro_2.0（4.1 GB） |
| `background_removal/` | BiRefNet-general（424 MB） |
| `facedetection/` | yolov5l-face、detection_Resnet50_Final、parsing_parsenet |
| `facerestore_models/` | GFPGANv1.4、codeformer |
| `insightface/` | inswapper_128.onnx、buffalo_l 全套 |
| `sams/` | sam_vit_b_01ec64 |
| `ultralytics/` | person_yolov8m-seg、face_yolov8m、hand_yolov8s |
| `IDM-VTON/` | 完整 IDM-VTON 全套（33 文件） |
| `mimicmotion/` | MimicMotionMergedUnet、MagicAnimate、IP-Adapter-FaceID |
| `diffusers/` | SVD img2vid-xt-1-1 |

---

## 四、自定义节点状态

### ✅ 已启用（13 个）
`comfyui_controlnet_aux`、`ComfyUI-GGUF`、`ComfyUI-IDM-VTON`、`ComfyUI-KJNodes`、`ComfyUI-LLM-Session`、`ComfyUI-MAINodes`、`ComfyUI-MimicMotionWrapper`、`ComfyUI-PlagueKind-Nodes`、`ComfyUI-ReActor-Nodes`、`comfyui-sg-llama-cpp`、`ComfyUI-VFI`、`ComfyUI-VideoHelperSuite`、`rgthree-comfy`

### ⛔ 已禁用（22 个，影响关键工作流）
| 节点 | 影响 |
|---|---|
| `ComfyUI-Impact-Pack` | 换装面部保护、DWPreprocessor → 影响 avatar 全链、pipeline |
| `comfyui_segment_anything` | SAM 换装/换头 → 影响 standard_image_outfit、avatar_wf1 |
| `ComfyUI-SeedVR2_VideoUpscaler` | 超分 → 影响 standard_seedvr2_upscale、flux_faceswap |
| `ComfyUI-WanVideoWrapper` | Wan 系列视频 |
| `ComfyUI-AnimateDiff-Evolved` | AnimateDiff 动画 |
| `ComfyUI-IPAdapter_plus` | IPAdapter 人脸迁移 |
| `ComfyUI-PuLID-Flux` | PuLID 换脸 |
| `ComfyUI-QwenVL` | Qwen 视觉理解（Z-Image 工作流依赖） |
| `ComfyUI-Jjk-Nodes` | Z-Image 工作流依赖 |
| `ComfyUI_LayerStyle` | 图层样式 |
| `CharacterFaceSwap` | 角色换脸 |
| 其他 | Comfyroll、essentials、CatVTON、OOTDiffusion、Portrait-Maker、MagicAnimate、efficiency-nodes、WAS、ComfyUI-ReActor(旧版) |

---

## 五、工具脚本精华（`tools/`，200+ 个）

| 分类 | 代表脚本 |
|---|---|
| **换脸批处理** | `batch_faceswap.py`、`batch_faceswap_v2/v3.py`、`batch_faceswap_gpu.py`、`batch_demosaic_faceswap.py`、`video_faceswap_enhanced.py` |
| **虚拟试穿** | `batch_tryon_comfyui.py`、`idm_vton_inference.py`、`tryon.py`、`submit_idm_vton.py`、`video_tryon_pipeline_v2.py` |
| **H3 视频批量** | `submit_h3_segments.py`、`submit_h3_audio.py`、`h3_*.py`（30+ 主题脚本）、`merge_h3_segments.py`、`mux_h3_audio.py`、`monitor_h3_segments.py` |
| **流水线** | `pipeline_faceswap_outfit.py`（6 阶段带断点续传）、`faceswap_tryon_pipeline_v2.py`、`alchemist_pipeline.py` |
| **LTX 视频** | `ltx_ootd_8videos_optimized.py`、`ltx_quality_test.py`、`ltx_speed_test.py` |
| **LoRA 训练** | `gen_lora_dataset.py`、`assemble_lora_dataset.py`、`gen_lora_diff.py`、`gen_lora_verify.py`、`run_flux_lora_test.py` |
| **后期处理** | `add_subtitles.py`、`add_ai_watermark.py`、`add_text_overlay.py`、`make_title_card.py`、`restore_and_mix_audio.py` |
| **运维** | `stop_comfyui.py`、`wait_comfyui.py`、`smoke_test.py`、`validate_avatar_workflows.py`、`api2canvas.py`、`toggle_nodes.py` |
| **下载** | `download_avatar_models_v2.py`、`download_idm_vton.py`、`download_flux_models.py` 等 |

---

## 六、实测结论（2026-09-21 实跑验证）

> 以下为用一组「年轻女性 / 乌黑长发 / 白色吊带 / 室内柔光」提示词，
> 在 4 个模型上各跑 8 张后的**实测**结果，非文档推断。

### 6.1 可用模型排名（实测）

| 模型 | 家族 | 实测耗时 | 画质/还原度 | 结论 |
|---|---|---|---|---|
| `majicmixRealistic_v7.safetensors` | SD1.5 | **9.2 s/张** | 写实，还原度高 | ⭐ 批量主力 |
| `AOM3A3_orangemixs.safetensors` | SD1.5 | 9.9 s/张 | 动漫，暖调 | 动漫风可选 |
| `Counterfeit-V3.0_fp16.safetensors` | SD1.5 | 10.3 s/张 | 动漫，冷调偏青 | 动漫风可选 |
| `flux1-dev-fp8.safetensors` | Flux.1-dev | 54.9 s/张（峰值 178s） | **语义/细节最强** | 高质量成品 |

### 6.2 重要修正与新发现

1. **`CheckpointLoaderSimple` 实际只认 3 个可用底模**：`majicmixRealistic_v7`、
   `Counterfeit-V3.0_fp16`、`AOM3A3_orangemixs`。清单第二版列的 SDXL / KREA-2 /
   Flux2-Klein / Z-Image **模型本体并不在磁盘上**，对应工作流属于「有图无模型」。
2. **GGUF 模型必须用 `UnetLoaderGGUF`**，不会出现在 `UNETLoader` 列表里。
   可用 GGUF：`PinkCherry LTX23`、`T8-flux.1-dev-abliterated` Q4/Q6/Q8。
3. **Flux Q8（12.1GB）在 16GB 卡上实测跑不动**：与 t5xxl(4.7GB) 合计超显存，
   任务在队列中挂起。**Q4_K_M（6.6GB）才是本机合理档位**（未及实测）。
4. **`UNETLoader` 必须带 `weight_dtype` 参数**（否则 500 validation error），
   `UnetLoaderGGUF` 则不需要。
5. **本地 `T8-flux.1-dev-abliterated` 是去审查版，会忽略着装约束直接出裸图**。
   用于人物题材必须改用标准版 `flux1-dev-fp8` 并加显式负面提示词。
6. **单卡队列严格串行**：大模型任务会阻塞整条队列，中断需
   `POST /interrupt` + `POST /queue {"clear":true}`。
7. `/system_stats` 在本机返回 500（GPU 探测异常），但 `/object_info`、`/queue`、
   `/prompt`、`/history` 均正常 —— 不要用它做健康检查。

### 6.3 可直接复用的生成脚本（`tools/`）

| 脚本 | 用途 |
|---|---|
| `_pc_common.py` | ComfyUI API 封装（提交/轮询/取产物） |
| `_pc_prompts.py` | 提示词库（分模型适配 + 着装锚定/负面词） |
| `_pc_gen_sd15.py` | SD1.5 批量出图（支持断点续跑、元数据合并） |
| `_pc_gen_flux.py` | Flux 批量出图（GGUF / safetensors 双通道） |
| `_pc_sheet.py` | 多模型 × 多场景对比拼图 |
| `_pc_report.py` | 汇总实测数据生成 Markdown 报告 |

### 6.4 对比产物位置

`output/prompt_compare/` — 报告、拼图、各模型 `_run.json` 明细。

---

## 七、快速上手建议

**最稳妥的可用能力（节点/模型均就绪）：**
1. 图片换脸 → `workflows/v1/faceswap_image_reactor.json`
2. 视频换脸 → `user/default/workflows/faceswap_video_reactor_260805_v2_手动确认帧率.json`
3. 视频换脸（优化）→ `tools/workflows/done/faceswap_video_reactor_260806_v3_opt.json`
4. H3 文生视频+音频 → `workflows/v1/h3_t2va_audio_ui_v2.json`
5. 数字人全链（短版）→ `workflows/avatar_wf5_short_v2_canvas.json`
6. IDM-VTON 高清试穿 → `tools/workflows/idm_vton_hq_workflow.json`
7. 动作迁移 → `workflows/v1/mimicmotion_motion_transfer.json`
8. 视频换装 → `workflows/v1/video_outfit_controlnet.json`
9. KREA-2 文生图 → `workflows/v3/krea2_t2i_workflow.json`

**需要先启用节点才能用：**
- 超分类 → 启用 `ComfyUI-SeedVR2_VideoUpscaler.disabled`
- 换装面部保护 → 启用 `ComfyUI-Impact-Pack.disabled`
- SAM 系列 → 启用 `comfyui_segment_anything.disabled`
- Wan 视频 → 启用 `ComfyUI-WanVideoWrapper.disabled`
- LTX 视频 → 启用 LTXVideo 节点（当前缺失）

> 启用方式：`python tools/toggle_nodes.py`，或手动去掉目录的 `.disabled` 后缀后重启 ComfyUI。
