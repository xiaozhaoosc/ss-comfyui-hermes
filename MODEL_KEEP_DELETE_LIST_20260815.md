# ComfyUI 模型清理最终清单

**最后更新**: 2026-08-15
**目标目录**: `d:\ai_projects\ComfyUI\models\`
**依据**: `D:\ai_projects\ComfyUI\workflows\done\` 中的 9 个工作流

---

## 一、保留的模型（24.4 GB）

以下 5 个目录及其内容已被保留，其余所有模型目录已删除。

### 1. `insightface\` (854 MB, 6 files)

| 文件 | 大小 | 用途 |
|---|---|---|
| `inswapper_128.onnx` | 528.6 MB | 换脸核心模型（9 个工作流共用） |
| `buffalo_l\1k3d68.onnx` | ~10 MB | 人脸关键点检测 |
| `buffalo_l\2d106det.onnx` | ~3 MB | 人脸关键点检测 |
| `buffalo_l\det_10g.onnx` | 16.1 MB | 人脸检测 |
| `buffalo_l\genderage.onnx` | ~1 MB | 性别年龄识别 |
| `buffalo_l\w600k_r50.onnx` | 166.3 MB | 人脸特征提取（recognition） |

> 注: `insightface\models\buffalo_l\` 重复副本已删除（325.5 MB）

### 2. `facerestore_models\` (691.7 MB, 2 files)

| 文件 | 大小 | 用途 |
|---|---|---|
| `GFPGANv1.4.pth` | 332.5 MB | 人脸修复（8 个工作流用） |
| `codeformer.pth` | 359.2 MB | 人脸增强（combo + v3_opt 工作流用） |

### 3. `facedetection\` (364.1 MB, 3 files)

| 文件 | 大小 | 用途 |
|---|---|---|
| `yolov5l-face.pth` | 178.3 MB | YOLOv5l 人脸检测（combo + v3_opt） |
| `detection_Resnet50_Final.pth` | 104.4 MB | Resnet50 人脸检测 |
| `parsing_parsenet.pth` | 81.4 MB | 人脸解析（FaceProtectMask 可能使用） |

### 4. `ultralytics\` (123.4 MB, 3 files)

| 文件 | 大小 | 用途 |
|---|---|---|
| `bbox\face_yolov8m.pt` | 49.6 MB | YOLOv8m 人脸检测（face_index_preview） |

### 5. `IDM-VTON\` (21.8 GB, 33 files)

| 组件 | 用途 |
|---|---|
| `unet\` | UNet 换装主模型 (5.7 GB) |
| `unet_encoder\` | UNet 参考编码器 |
| `vae\` | VAE 编解码器 |
| `image_encoder\` | 图像编码器 (2.4 GB) |
| `text_encoder\` | 文本编码器 1 |
| `text_encoder_2\` | 文本编码器 2 |
| `tokenizer\` | 分词器 1 |
| `tokenizer_2\` | 分词器 2 |
| `densepose\` | DensePose 姿态检测 |
| `humanparsing\` | 人体解析（parsing_atr + parsing_lip） |
| `openpose\` | OpenPose 姿态检测 |
| `scheduler\` | 调度器配置 |

> 被 `faceswap_tryon_combo_v1.json` 工作流引用

---

## 二、已删除的目录（429.47 GB）

以下 50 个目录/文件已在本次操作中删除：

| 目录 | 大小 | 说明 |
|---|---|---|
| `diffusion_models\` | 137.76 GB | flux/krea/qwen_image_edit/wan2.2 等 |
| `unet\` | 40.03 GB | flux1-fill-dev（硬链接主文件）等 |
| `clip\` | 36.56 GB | t5xxl/umt5xxl/siglip 等 |
| `text_encoders\` | 32.67 GB | qwen_2.5_vl_7b 等 |
| `checkpoints\` | 31.46 GB | SDXL/SD1.5 基础模型 |
| `FLUX.1-dev\` | 22.44 GB | FLUX.1-dev 全套 |
| `OOTDiffusion\` | 16.37 GB | 虚拟试衣（与 IDM-VTON 重复） |
| `controlnet\` | 15.55 GB | SD15 controlnet |
| `ideogram4-nf4\` | 15.01 GB | Ideogram 4 |
| `MagicAnimate\` | 14.62 GB | 动画生成 |
| `animatediff_models\` | 10.93 GB | AnimateDiff |
| `vae\` | 10.11 GB | 多种 VAE |
| `mimicmotion\` | 8.52 GB | MimicMotion |
| `sams\` | 7.86 GB | SAM 全套 |
| `configs\` | 7.03 GB | flux1-fill-dev-Q4_1.gguf 等 |
| `CatVTON\` | 4.90 GB | 虚拟试衣 |
| `diffusers\` | 4.20 GB | diffusers 模型 |
| `clip_vision\` | 4.07 GB | CLIP 视觉模型 |
| `loras\` | 1.93 GB | 各类 lora |
| `midas\` | 1.29 GB | 深度估计 |
| `pulid\` | 1.06 GB | PuLID |
| `ipadapter\` | 1.03 GB | IP-Adapter |
| `grounding-dino\` | 0.93 GB | 目标检测 |
| `eva_clip\` | 0.80 GB | EVA02 CLIP |
| `segformer_b2_clothes\` | 0.41 GB | SegFormer |
| `sam\` | 0.35 GB | SAM |
| `nsfw_detector\` | 0.32 GB | NSFW 检测 |
| `onnx\` | 0.33 GB | DWPose ONNX |
| `split_files\` | 0.31 GB | ae.safetensors 硬链接副本 |
| `upscale_models\` | 0.19 GB | 放大模型 |
| `style_models\` | 0.12 GB | 风格模型 |
| `vae_approx\` | 0.04 GB | VAE 近似 |
| 其他空目录 ×17 | ~0 | 占位目录 |
| `insightface\models\` | 0.33 GB | buffalo_l 重复副本 |
| `MODEL_DOWNLOAD_LIST.md` | ~0 | 下载清单文件 |

---

## 三、累计清理汇总（2026-08-15 全部操作）

| 日期 | 操作 | 释放空间 |
|---|---|---|
| 2026-08-15 | 硬链接去重（7组重复文件） | 42.49 GB |
| 2026-08-15 | incomplete 残留删除（19个文件） | 13.97 GB |
| 2026-08-15 | 删除 InfiniteTalk/CogVideo/LLM | 145.16 GB |
| 2026-08-15 | 删除未引用模型目录（50个） | 429.47 GB |
| **累计释放** | | **631.09 GB** |

### 磁盘空间变化

| 时间点 | D: 盘剩余空间 |
|---|---|
| 操作前 | ~87 GB |
| 全部操作后 | **709.19 GB** |
| **净增** | **~622 GB** |

---

## 四、工作流与模型对应关系

### workflows\done\ 中的 9 个工作流

| 工作流 | 使用模型 |
|---|---|
| `face_index_preview_260804.json` | ultralytics\bbox\face_yolov8m.pt |
| `faceswap_tryon_combo_v1.json` | inswapper_128.onnx, codeformer.pth, yolov5l-face.pth, IDM-VTON 全套 |
| `faceswap_video_reactor_260801.json` | inswapper_128.onnx, GFPGANv1.4.pth |
| `faceswap_video_reactor_260801_v2.json` | inswapper_128.onnx, GFPGANv1.4.pth |
| `faceswap_video_reactor_260804_v3.json` | inswapper_128.onnx, GFPGANv1.4.pth |
| `faceswap_video_reactor_260804_v4.json` | inswapper_128.onnx, GFPGANv1.4.pth |
| `faceswap_video_reactor_260805_v2_opt.json` | inswapper_128.onnx, GFPGANv1.4.pth |
| `faceswap_video_reactor_260805_v2_verify.json` | inswapper_128.onnx, GFPGANv1.4.pth |
| `faceswap_video_reactor_260806_v3_opt.json` | inswapper_128.onnx, GFPGANv1.4.pth, codeformer.pth, yolov5l-face.pth |

> `retinaface_resnet50` 是 ReActor 内置的人脸检测器，不需要独立模型文件。
> `buffalo_l` 套件是 insightface 的基础依赖，所有换脸工作流间接使用。

---

## 五、注意事项

1. **qwen_image_edit 工作流**: 其引用的模型（qwen_image_edit_fp8_e4m3fn.safetensors 等）已删除，因为该工作流不在 `workflows\done\` 目录。如需使用，需重新下载。
2. **flux_fill_outpaint 工作流**: 同上，已删除。
3. **如需恢复**: 已删除的模型需从 HuggingFace 或其他来源重新下载。
4. **硬链接说明**: 之前硬链接去重的文件中，部分硬链接副本（如 `diffusion_models\flux1-fill-dev.safetensors`）已随 `diffusion_models\` 目录删除，但这不影响任何功能，因为 FLUX 相关模型本身已全部删除。
