# Pipeline: Face Swap → Outfit Swap

## 架构

```
输入视频 + 源人脸 + 服装图
         │
    ┌────▼────┐
    │ Stage 1 │ Face Swap (batch_faceswap.py)
    │  换脸    │ insightface + GFPGAN, 按段分割/合并
    └────┬────┘
         │ 换脸视频
    ┌────▼────┐
    │ Stage 2 │ Frame Extract (ffmpeg)
    │ 帧提取   │ 全部帧 + 关键帧索引(1s间隔)
    └────┬────┘
         │ 全部帧 + 关键帧索引
    ┌────▼────┐
    │ Stage 3 │ Mask Generation (ATR parsing)
    │ 遮罩生成  │ 面部保护: 排除 face/hair/sunglasses
    └────┬────┘
         │ 关键帧遮罩
    ┌────▼────┐
    │ Stage 4 │ IDM-VTON (ComfyUI API)
    │ 换装     │ 逐关键帧换装, 断点续传
    └────┬────┘
         │ 换装关键帧
    ┌────▼────┐
    │ Stage 5 │ Optical Flow (Farneback)
    │ 光流插值  │ 原帧运动场 warp + alpha 混合
    └────┬────┘
         │ 全部换装帧
    ┌────▼────┐
    │ Stage 6 │ Compose (ffmpeg)
    │ 合成视频  │ 保留原始音频
    └────┬────┘
         │
    最终视频 (换脸+换装)
```

## 用法

### 完整流水线

```bash
cd D:\ai_projects\ComfyUI

python tools/pipeline_faceswap_outfit.py run \
  --video input/todo/swap_face/2.mp4 \
  --face input/todo/face/model1/model1face.png \
  --garment input/vton/garment.jpg \
  --garment-desc "white casual t-shirt" \
  --output-dir output/pipeline_2
```

### 跳过换脸（已有换脸视频）

```bash
python tools/pipeline_faceswap_outfit.py run \
  --video output/batch_faceswap/2_faceswap.mp4 \
  --skip-faceswap \
  --garment input/vton/garment.jpg \
  --garment-desc "white casual t-shirt" \
  --output-dir output/pipeline_2
```

### 运行单个 Stage

```bash
# 只跑 Stage 4 (换装)
python tools/pipeline_faceswap_outfit.py stage --stage 4 \
  --output-dir output/pipeline_2 \
  --garment input/vton/garment.jpg

# 查看状态
python tools/pipeline_faceswap_outfit.py status \
  --output-dir output/pipeline_2
```

## 输出目录结构

```
output/pipeline_1/
├── .pipeline_state.json     # 进度状态 (断点续传)
├── 1_faceswapped/           # Stage 1: 换脸输出
│   └── 1_faceswap.mp4
├── 2_frames/                # Stage 2: 全部帧
│   ├── frame_000001.png
│   └── ...
├── 3_masks/                 # Stage 3: 面部保护遮罩
│   ├── mask_0000.png
│   └── ...
├── 4_swapped_kf/            # Stage 4: 换装关键帧
│   ├── kf_0000.png
│   └── ...
├── 5_interp_frames/         # Stage 5: 光流插值帧
│   ├── frame_000001.png
│   └── ...
└── final.mp4                # Stage 6: 最终视频
```

## 关键参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--keyframe-interval` | 1.0s | 关键帧间隔，越小越精细但越慢 |
| `--steps` | 30 | IDM-VTON 推理步数 |
| `--width/height` | 768/1024 | IDM-VTON 输入分辨率 |
| `--protect-expand` | 10px | 面部保护扩展范围 |
| `--feather` | 5px | 遮罩边缘羽化 |
| `--clothing-labels` | 4,7,8 | ATR 服装标签 |
| `--protect-labels` | 2,3,11 | ATR 保护标签 |

## 断点续传

每个 Stage 完成后记录到 `.pipeline_state.json`。
重新运行会跳过已完成的 Stage。
删除该文件或用 `--force` 可重跑。

## 依赖

- ComfyUI (运行中, 端口 8188)
- ComfyUI-IDM-VTON (PipelineLoader + IDM-VTON 节点)
- ComfyUI-Impact-Pack (DWPreprocessor)
- insightface + GFPGAN (Stage 1 换脸)
- onnxruntime (ATR 人体解析)
- ffmpeg
