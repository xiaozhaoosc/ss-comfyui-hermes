# ReActor 换脸 + IDM-VTON 换装 组合工作流

## 概述
端到端的换脸+换装管线：先用 ReActor 换脸，再用 IDM-VTON 换装。

## 流程
```
Step 1-2: 换脸
  LoadImage(源脸) ─┐
                   ├→ ReActorFaceSwap(+GFPGAN) ─→ 换脸结果
  LoadImage(目标) ─┘

Step 3-5: 换装
  换脸结果 ─┬→ DWPose(姿态估计) ─┐
            ├→ LoadImage(torso mask) ├→ IDM-VTON ─→ 最终结果
            └→ LoadImage(服装图) ───┘
```

## 使用方法

### 1. 生成 Torso Mask
```bash
# 单张
python tools/gen_torso_mask.py --input output/faceswap_comfyui/swap_restored_00001.png

# 批量 (整个目录)
python tools/gen_torso_mask.py --input output/faceswap_comfyui/ --output masks/

# 自定义比例 (top=25%, bottom=92%)
python tools/gen_torso_mask.py --input image.png --top 0.25 --bottom 0.92
```

### 2. 在 ComfyUI 中运行
1. Load → 选择 `faceswap_outfit_pipeline.json`
2. 配置各节点:
   - **📷 Source Face**: 换脸源图片 (如 ken1.png)
   - **🎯 Target**: 原始目标图片
   - **🎭 Torso Mask**: 用上面脚本生成的 mask
   - **👗 Garment**: 目标服装图片 (如 demo_cropped.jpg)
3. 修改 IDM-VTON 的 garment_description 描述你的服装
4. Queue Prompt

### 3. 调参建议
| 参数 | 推荐值 | 说明 |
|------|-------|------|
| guidance_scale | 2.0 | 越大越遵循 mask，>3 可能过拟合 |
| num_inference_steps | 30 | 20-50 都可，越大越慢越精细 |
| strength | 1.0 | 换装强度，0.8-1.0 |
| top_ratio | 0.30 | mask 起始位置，含肩部 |
| bottom_ratio | 0.95 | mask 结束位置，含腰部 |

## 依赖
- ComfyUI-ReActor
- ComfyUI-IDM-VTON
- comfyui_controlnet_aux (DWPose)
- models/insightface/inswapper_128.onnx
- models/facerestore_models/GFPGANv1.4.pth
- IDM-VTON 模型 (自动下载)

## 已知问题
- ❌ FaceProtectMask 不要用! 会导致换装不生效。用手动 torso mask
- ⚠️ 跨品类换装（如开衫→连衣裙）效果差
- ⚠️ 羽毛/透明材质边缘可能模糊
- 💡 VRAM: ~13GB，不能同时跑其他大模型
