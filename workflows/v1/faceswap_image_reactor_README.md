# ReActor 图片换脸工作流

## 概述
基于 ReActor + GFPGAN 的图片换脸工作流，可直接在 ComfyUI 中拖入使用。

## 流程
```
LoadImage(源脸) ─┐
                 ├→ ReActorFaceSwap(+GFPGAN) ─┬→ SaveImage (纯换脸)
LoadImage(目标) ─┘                              └→ ReActorRestoreFace → SaveImage (增强版)
```

## 节点说明
| 节点 | 功能 | 关键参数 |
|------|------|---------|
| LoadImage ×2 | 加载源脸 + 目标图 | 文件名 |
| ReActorFaceSwap | 换脸 + 初次修复 | inswapper_128.onnx, GFPGANv1.4.pth |
| ReActorRestoreFace | 二次面部增强 | visibility=0.8 |
| SaveImage ×2 | 保存原始/增强版 | filename_prefix |

## 使用方法
1. 打开 ComfyUI → 菜单 → Load → 选择 `faceswap_image_reactor.json`
2. 左上 LoadImage 选择换脸源（如 `input/todo/face/ken1.png`）
3. 左下 LoadImage 选择目标图片
4. 点击 Queue Prompt 运行
5. 输出保存到 `output/faceswap_comfyui/`

## 依赖
- ComfyUI-ReActor (已安装)
- models/insightface/inswapper_128.onnx
- models/facerestore_models/GFPGANv1.4.pth
- models/insightface/buffalo_l/ (人脸检测模型)
