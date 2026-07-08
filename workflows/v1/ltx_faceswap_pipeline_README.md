# LTX 生成 + 换脸管道

## 概述

端到端的 AI 视频生成 + 换脸管道：
1. **LTX-2.3** 生成视频
2. **insightface** 对生成的视频进行换脸
3. 输出最终换脸视频

## 使用方法

```bash
cd D:\ai_projects\ComfyUI

# 基础用法
./venv/Scripts/python.exe tools/ltx_faceswap_pipeline.py \
  --source path/to/face.png \
  --prompt "A person talking to the camera"

# 自定义参数
./venv/Scripts/python.exe tools/ltx_faceswap_pipeline.py \
  --source path/to/face.png \
  --prompt "A young woman talking, close-up shot, natural lighting" \
  --width 512 --height 320 --frames 33 --steps 16 \
  --output my_faceswap_video.mp4
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--source` | (必填) | 源人脸图片路径 |
| `--prompt` | "A person talking..." | LTX 生成提示词 |
| `--width` | 512 | 视频宽度 |
| `--height` | 320 | 视频高度 |
| `--frames` | 33 | 帧数 (33帧 ≈ 1.3s @25fps) |
| `--steps` | 16 | 采样步数 |
| `--seed` | -1 (随机) | 随机种子 |
| `--output` | 自动生成 | 输出文件名 |

## 处理流程

```
LTX-2.3 生成视频 (ComfyUI API)
    ↓
下载生成的视频
    ↓
ffmpeg 提取视频帧
    ↓
insightface 逐帧换脸
    ↓
ffmpeg 合成最终视频
```

## 已知限制

1. **LTX 生成质量**：Q2_K 量化可能产生抽象/扭曲内容，不一定包含清晰人脸
2. **人脸检测**：insightface 需要检测到人脸才能进行换脸
3. **生成时间**：LTX 生成约 5-10 分钟（16步，512x320）
4. **换脸速度**：~0.5s/帧（CPU）

## 优化建议

1. **提升 LTX 生成质量**：
   - 使用更高量化级别（Q3_K_M, Q4_K_M）
   - 增加采样步数（20-30步）
   - 使用更详细的提示词

2. **确保生成人脸**：
   - 在提示词中明确描述面部特征
   - 使用 "close-up shot" 或 "portrait" 等关键词
   - 参考 LTX 官方示例提示词

3. **提升换脸效果**：
   - 使用清晰的源人脸图片（正脸、光线好）
   - 启用 GFPGAN 人脸修复

## 文件说明

- `tools/ltx_faceswap_pipeline.py` - 主脚本
- `tools/video_faceswap_direct.py` - 纯换脸脚本（已生成视频的换脸）
- `workflows/v1/ltxv_23_gguf_optimized.json` - LTX 工作流参考

## 测试结果

| 测试 | LTX 生成 | 换脸 | 说明 |
|------|----------|------|------|
| 端到端测试 | ✅ | ⚠️ | LTX 生成成功，但内容无人脸 |

---

*创建时间：2026-06-08*
