# Flux Klein 换脸工作流 — 详细文档

> 基于 FLUX.2 Klein 9B 的 AI 换脸工作流，支持图片换脸和可选的 SeedVR2 超分辨率放大。

**来源**: [RunComfy Flux Klein Face Swap](https://www.runcomfy.com/zh-CN/comfyui-workflows/flux-klein-face-swap-in-comfyui-seamless-ai-face-replacement)

---

## 文件说明

| 文件 | 格式 | 说明 |
|------|------|------|
| `flux_klein_faceswap.json` | 前端导入格式 | 在 ComfyUI 界面中通过 "Load" 导入 |
| `flux_klein_faceswap_api.json` | API Prompt 格式 | 可通过 curl/脚本直接提交运行 |

---

## 工作流架构

```
                        ┌─────────────────┐
                        │   LoadImage #81  │ ← 目标图片（要换脸的照片）
                        └────────┬────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   ▼             ▼              ▼
          ┌──────────────┐ ┌──────────┐ ┌──────────────┐
          │DWPreprocessor│ │ImageScale│ │  GetImageSize│
          │   #267       │ │  By #260 │ │    #255      │
          └──────┬───────┘ └────┬─────┘ └──────┬───────┘
                 │              │              │
                 ▼              ▼              ▼
          ┌──────────────────────────────────────────┐
          │        ImageResizeKJv2 #468               │
          │   (resize to working resolution)          │
          └──────────────────┬───────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐ ┌───────────┐ ┌────────────┐
       │ VAEEncode  │ │Reference  │ │ VAEEncode  │
       │   #270     │ │Latent #269│ │   #258     │
       └─────┬──────┘ └─────┬─────┘ └─────┬──────┘
             │              │              │
             ▼              ▼              ▼
       ┌─────────────────────────────────────────┐
       │     3x ReferenceLatent (#253,#257,#269)  │
       │     → 融合参考条件                        │
       └──────────────────┬──────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
  ┌────────────┐  ┌──────────────┐  ┌──────────────┐
  │UNETLoader  │  │CLIPTextEncode│  │ LoadImage    │
  │   #180     │  │    #250      │  │  #244 (face) │
  │ FLUX2 Klein│  │ 换脸指令     │  │  人脸来源    │
  └─────┬──────┘  └──────┬───────┘  └──────┬───────┘
        │                │                 │
        ▼                ▼                 ▼
  ┌──────────────────────────────────────────────┐
  │           BasicGuider #277                    │
  │      Flux2Scheduler #237 + KSampler #240     │
  │      RandomNoise #256                        │
  │      SamplerCustomAdvanced #261               │
  └──────────────────────┬───────────────────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  VAEDecode   │
                  │    #251      │
                  └──────┬───────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐ ┌────────┐ ┌────────────────┐
        │PreviewImg│ │SaveImg │ │SeedVR2放大(可选)│
        │  #268    │ │ #467   │ │   #326         │
        └──────────┘ └────────┘ └────────────────┘
```

---

## 模型清单

### 核心模型（必需）

| 模型文件 | 大小 | 来源 | 存储位置 | ComfyUI 路径 |
|----------|------|------|----------|-------------|
| `flux-2-klein-9b-fp8.safetensors` | 9.43GB | [black-forest-labs/FLUX.2-klein-9b-fp8](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8) | `D:\OLLAMA_MODELS\models\diffusion_models\` | `models/diffusion_models/` (hardlink) |
| `qwen_3_8b.safetensors` | 16GB | [black-forest-labs/FLUX.2-klein](https://huggingface.co/black-forest-labs/FLUX.2-klein) | `D:\OLLAMA_MODELS\models\text_encoders\` | `models/text_encoders/` (hardlink) |
| `flux2-vae.safetensors` | 321MB | [black-forest-labs/FLUX.2-klein](https://huggingface.co/black-forest-labs/FLUX.2-klein) | `D:\OLLAMA_MODELS\models\vae\` | `models/vae/` (hardlink) |

### 辅助模型（DWPose 人脸/姿态检测）

| 模型文件 | 大小 | 来源 | 存储位置 |
|----------|------|------|----------|
| `yolox_l.torchscript.pt` | 208MB | [hr16/yolox-onnx](https://huggingface.co/hr16/yolox-onnx) | `custom_nodes/comfyui_controlnet_aux/ckpts/hr16/yolox-onnx/` |
| `dw-ll_ucoco_384_bs5.torchscript.pt` | 129MB | [hr16/DWPose-TorchScript-BatchSize5](https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5) | `custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/` |

### 可选模型（SeedVR2 超分辨率放大）

| 模型文件 | 大小 | 来源 | 说明 |
|----------|------|------|------|
| `seedvr2_ema_7b-Q4_K_M.gguf` | ~4GB | SeedVR2 插件自动下载 | DiT 放大模型 |
| `ema_vae_fp16.safetensors` | ~200MB | SeedVR2 插件自动下载 | 放大 VAE |

### GGUF 备选模型

| 模型文件 | 大小 | 来源 | 说明 |
|----------|------|------|------|
| `flux-2-klein-9b-Q4_K_M.gguf` | 5.9GB | [unsloth/FLUX.2-klein-9B-GGUF](https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF) | 可替代 FP8 版本，需用 `UnetLoaderGGUF` 节点 |

---

## 自定义节点

| 节点包 | 用途 | 安装命令 |
|--------|------|----------|
| `comfyui_controlnet_aux` | DWPose 人脸/姿态检测 | `git clone https://github.com/Fannovel16/comfyui_controlnet_aux` |
| `ComfyUI-KJNodes` | ImageResizeKJv2 等工具节点 | `git clone https://github.com/kijai/ComfyUI-KJNodes` |
| `ComfyUI-SeedVR2_VideoUpscaler` | 视频放大（可选） | `git clone https://github.com/kijai/ComfyUI-SeedVR2` |
| `rgthree-comfy` | Image Comparer 对比查看 | `git clone https://github.com/rgthree/rgthree-comfy` |
| `ComfyUI-GGUF` | GGUF 模型加载（可选） | `git clone https://github.com/city96/ComfyUI-GGUF` |

**额外依赖**（pip）：`mediapipe`, `fvcore`, `yapf`, `omegaconf`, `ftfy`, `addict`, `yacs`, `einops`, `scikit-image`

---

## 关键节点参数

### UNETLoader #180
| 参数 | 值 | 说明 |
|------|------|------|
| `unet_name` | `flux-2-klein-9b-fp8.safetensors` | 核心扩散模型 |
| `weight_dtype` | `default` | 默认精度 |

### CLIPLoader #178
| 参数 | 值 | 说明 |
|------|------|------|
| `clip_name` | `qwen_3_8b.safetensors` | Qwen3 文本编码器 |
| `type` | `flux2` | Flux2 专用模式 |

### DWPreprocessor #267
| 参数 | 值 | 说明 |
|------|------|------|
| `detect_hand` | `enable` | 检测手部 |
| `detect_body` | `enable` | 检测身体 |
| `detect_face` | `enable` | 检测人脸 |
| `resolution` | `1024` | 检测分辨率 |
| `bbox_detector` | `yolox_l.torchscript.pt` | YOLOX 人脸检测模型 |
| `pose_estimator` | `dw-ll_ucoco_384_bs5.torchscript.pt` | DWPose 姿态估计 |

### Flux2Scheduler #237
| 参数 | 值 | 说明 |
|------|------|------|
| `steps` | `20` | 采样步数 |
| `max_shift` | `1.0` | 最大偏移 |
| `base_shift` | `0.5` | 基础偏移 |

### CLIPTextEncode #250（换脸指令）
```
match the skin tone of the limbs and the face. Maintain character consistency.
Use the face head shape and hairstyle from image 2, keep the body pose and clothing from image 1.
Natural lighting, photorealistic.
```

### EmptyFlux2LatentImage #246
| 参数 | 值 | 说明 |
|------|------|------|
| `width` | `1024` | 输出宽度 |
| `height` | `1024` | 输出高度 |
| `batch_size` | `1` | 单帧输出 |

---

## 使用方法

### 方法 1：ComfyUI 界面
1. 启动 ComfyUI：`cd /d/ai_projects/ComfyUI && ./venv/Scripts/python.exe main.py --lowvram`
2. 打开浏览器 `http://127.0.0.1:8188`
3. 拖入 `flux_klein_faceswap.json` 加载工作流
4. 在 LoadImage #81 选择目标图片（要换脸的照片）
5. 在 LoadImage #244 选择人脸来源图片
6. 修改 CLIPTextEncode #250 的提示词（可选）
7. 点击 "Queue Prompt" 运行

### 方法 2：API 调用
```bash
# 提交工作流
curl -s -X POST http://127.0.0.1:8188/prompt \
  -H "Content-Type: application/json" \
  -d @workflows/v1/flux_klein_faceswap_api.json

# 检查执行状态
curl -s http://127.0.0.1:8188/history/<prompt_id>
```

---

## VRAM 使用情况

| 阶段 | VRAM | 说明 |
|------|------|------|
| 模型加载 | ~15GB | Flux2 9B FP8 + Qwen3 8B + VAE |
| DWPose 检测 | ~2GB | YOLOX + DWPose |
| 采样推理 | ~14GB | `--lowvram` 模式下部分 offload 到 CPU |
| SeedVR2 放大 | ~16GB | 需要额外 7B DiT 模型 |

**建议**：16GB VRAM 下关闭 SeedVR2 放大，或使用 3B 版本。

---

## 已知问题

1. **SeedVR2 放大参数兼容性**：原工作流中 `resolution` 设为 `'fixed'`，API 格式不兼容，需改为具体数值
2. **DWPose 模型下载**：ComfyUI 内置下载器可能因网络问题失败，建议手动下载放到 ckpts 目录
3. **输入图片分辨率**：建议源图片和目标图片分辨率接近，头部大小和角度相似
4. **低 VRAM 模式**：使用 `--lowvram` 时采样速度较慢（约 2-5 分钟/张）

---

## 测试结果

| 测试 | 输入 | 输出 | 耗时 | 状态 |
|------|------|------|------|------|
| 首次测试 | face_target.png + face_source.png | flux_faceswap_result.png (2.2MB) | ~3 分钟 | ✅ 成功 |

**效果评估**：换脸结果自然连贯，光照、肤色、表情匹配良好，无明显拼接痕迹。

---

## 参考链接

- [RunComfy 工作流页面](https://www.runcomfy.com/zh-CN/comfyui-workflows/flux-klein-face-swap-in-comfyui-seamless-ai-face-replacement)
- [FLUX.2 Klein 9B FP8 模型](https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8)
- [SeedVR2 插件](https://github.com/kijai/ComfyUI-SeedVR2)
- [comfyui_controlnet_aux](https://github.com/Fannovel16/comfyui_controlnet_aux)
