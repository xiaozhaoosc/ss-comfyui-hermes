# Standard Image Outfit Workflow

工作流文件：`standard_image_outfit.json`

## 节点流程

```
LoadImage → FaceProtectMask → GrowMask(+20) → BlurMask → VAEEncodeForInpaint → KSampler(SDXL) → VAEDecode → ImageCompositeMasked → SaveImage
                                    ↓
                              Parsing Preview → SaveImage
```

## 节点说明

| 节点 | 作用 | 关键参数 |
|------|------|----------|
| LoadImage | 加载人物照片 | - |
| FaceProtectMask | 人体解析生成服装 mask，排除面部/头发/墨镜 | clothing_labels=4,7,8; protect_labels=2,3,11; expand=10; feather=5 |
| GrowMask | 扩展 mask 边缘 | expand=20 |
| ImpactGaussianBlurMask | 高斯模糊 mask 边缘 | kernel=11, sigma=5 |
| CheckpointLoaderSimple | 加载 SDXL 模型 | sd_xl_base_1.0.safetensors |
| CLIPTextEncode ×2 | 正向/负向提示词 | - |
| VAEEncodeForInpaint | Inpaint 编码 | grow_mask_by=8 |
| KSampler | 采样 | steps=25, cfg=7.5, denoise=0.9 |
| ImageCompositeMasked | 合成回原图 | - |
| SaveImage ×2 | 保存结果 + 解析预览 | - |

## 依赖模型

- `sd_xl_base_1.0.safetensors` (SDXL)
- `parsing_atr.onnx` (FaceProtectMask 自动加载)

## 依赖自定义节点

- ComfyUI-Impact-Pack (ImpactGaussianBlurMask)
- ComfyUI-IDM-VTON (FaceProtectMask)

## 面部保护原理

FaceProtectMask 使用 ATR 人体解析模型将像素分为 18 类：
- **服装区域** (mask=白)：4=上衣, 7=连衣裙, 8=腰带
- **保护区域** (mask=黑)：2=头发, 3=墨镜, 11=面部
- 保护区域扩展 10px + 边缘羽化 5px，确保面部不被 inpainting 修改

## 可调参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| clothing_labels | 4,7,8 | 需要替换的服装 ATR 标签 |
| protect_labels | 2,3,11 | 需要保护的区域 ATR 标签 |
| protect_expand | 10 | 保护区域扩展像素 |
| feather | 5 | 边缘羽化像素 |
| denoise | 0.9 | 重绘强度 (0-1) |
| seed | 42 | 随机种子 |
