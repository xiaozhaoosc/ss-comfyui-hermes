# ComfyUI 标准化工作流 v1

## 工作流列表

### 1. standard_image_faceswap.json - 图片换脸
- **用途**: 将源人脸替换到目标图片上
- **输入**: 源人脸图片 + 目标图片
- **输出**: 换脸后的图片
- **依赖模型**: inswapper_128.onnx, retinaface_resnet50
- **依赖节点**: ComfyUI-ReActor
- **使用方法**: 替换LoadImage节点中的图片文件名，提交到ComfyUI API

### 2. standard_video_faceswap.json - 视频换脸
- **用途**: 将源人脸替换到视频的每一帧
- **输入**: 源人脸图片 + 输入视频
- **输出**: 换脸后的MP4视频
- **依赖模型**: inswapper_128.onnx, GFPGANv1.4.pth, retinaface_resnet50
- **依赖节点**: ComfyUI-ReActor, ComfyUI-VideoHelperSuite
- **使用方法**: 替换LoadVideo和LoadImage中的文件名

### 3. standard_video_gen.json - AI视频生成
- **用途**: 通过文本描述生成视频
- **输入**: 文本提示词
- **输出**: MP4视频 (768x480, 49帧)
- **依赖模型**: ltx-2.3-22b-dev-Q2_K.gguf, gemma_3_12B_it.safetensors, vae_with_config_fixed.safetensors, ltx-2.3-22b-dev.safetensors
- **依赖节点**: ComfyUI-LTXVideo, ComfyUI-GGUF
- **使用方法**: 修改CLIPTextEncode #4中的提示词
- **参数**: 可调整width/height/length/steps/seed

### 4. standard_image_outfit.json - 图片换装
- **用途**: 使用SAM分割+SDXL重绘更换服装
- **输入**: 人物图片 + SAM坐标点 + 文本描述
- **输出**: 换装后的图片
- **依赖模型**: sd_xl_base_1.0.safetensors, sam_vit_b_01ec64.pth
- **依赖节点**: comfyui_segment_anything, ComfyUI-Impact-Pack
- **使用方法**: 修改SAM Parameters中的坐标点和CLIPTextEncode中的服装描述

### 5. standard_video_outfit.json - 视频换装
- **用途**: 使用深度ControlNet+SDXL对视频逐帧换装
- **输入**: 视频 + 文本描述 + 掩码区域
- **输出**: 换装后的MP4视频
- **依赖模型**: sd_xl_base_1.0.safetensors, diffusers_xl_depth_full.safetensors
- **依赖节点**: comfyui_controlnet_aux, ComfyUI-VideoHelperSuite
- **使用方法**: 修改CLIPTextEncode中的服装描述，调整SolidMask的坐标区域

### 6. standard_seedvr2_upscale.json - SeedVR2 超分辨率
- **用途**: AI图片超分放大，保留细节和纹理
- **输入**: 图片
- **输出**: 超分后的图片 (~720p基准, 1280px最大边)
- **依赖模型**: seedvr2_3b_fp8_e4m3fn.safetensors, ema_vae_fp16.safetensors
- **依赖节点**: ComfyUI-SeedVR2_VideoUpscaler
- **使用方法**: 替换LoadImage中的图片文件名

### 7. standard_flux_faceswap.json - Flux Klein 生图+换脸+超分
- **用途**: Flux2生成高质量图片 → ReActor换脸 → SeedVR2超分
- **输入**: 参考图片 + 人脸源图片 + 文本提示词
- **输出**: 换脸+超分后的图片 (768x1024)
- **依赖模型**: flux-2-klein-9b.safetensors, qwen_3_8b.safetensors, flux2-vae.safetensors, seedvr2_3b_fp8_e4m3fn.safetensors, ema_vae_fp16.safetensors, inswapper_128.onnx
- **依赖节点**: ComfyUI-ReActor, ComfyUI-SeedVR2_VideoUpscaler, comfyui_controlnet_aux
- **使用方法**: 替换LoadImage图片和CLIPTextEncode提示词

### 8. standard_zimage_realskin.json - Z-Image Real Skin 自然纹理肖像
- **用途**: 生成具有真实皮肤纹理的高质量人像
- **输入**: 参考肖像图片（可选）+ 风格描述文本
- **输出**: 高质量人像图片 (960x1280)
- **依赖模型**: z_image_turbo_bf16.safetensors, qwen_3_4b.safetensors, ae.safetensors, unfiltered_realism_v2.safetensors, kook_zimage_realistic_fantasy_turbo.safetensors
- **依赖节点**: AILab_QwenVL, LayerUtility, JjkText, JoinStrings
- **使用方法**: 替换LoadImage中的参考图片，修改JjkText #4中的风格描述

## 模型文件位置

所有模型放在 ComfyUI/models/ 对应子目录下:

| 目录 | 模型文件 |
|------|----------|
| checkpoints/ | sd_xl_base_1.0.safetensors, ltx-2.3-22b-dev.safetensors, flux-2-klein-9b.safetensors |
| diffusion_models/ | z_image_turbo_bf16.safetensors, seedvr2_3b_fp8_e4m3fn.safetensors |
| text_encoders/ | gemma_3_12B_it.safetensors, qwen_3_8b.safetensors, qwen_3_4b.safetensors |
| vae/ | vae_with_config_fixed.safetensors, flux2-vae.safetensors, ae.safetensors, ema_vae_fp16.safetensors |
| loras/ | unfiltered_realism_v2.safetensors, kook_zimage_realistic_fantasy_turbo.safetensors, ltxv/ |
| controlnet/ | diffusers_xl_depth_full.safetensors, controlnet_union_sdxl.safetensors |
| upscale_models/ | RealESRGAN_x4plus.pth |
| ReActor | inswapper_128.onnx, GFPGANv1.4.pth (reactor/ 或 insightface/) |

## API调用示例

```python
import requests, json

# 加载工作流
with open('workflows/v1/standard_image_faceswap.json') as f:
    workflow = json.load(f)

# 修改输入
workflow['prompt']['1']['inputs']['image'] = 'my_face.jpg'
workflow['prompt']['2']['inputs']['image'] = 'target.jpg'

# 提交
resp = requests.post('http://127.0.0.1:8188/prompt', json=workflow)
print(resp.json())
```
