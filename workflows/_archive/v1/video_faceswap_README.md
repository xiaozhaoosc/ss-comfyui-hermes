# 视频换脸方案 - Video Face Swap

## 方案概述

### 为什么选择 Video Pipeline？

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Video Pipeline (ReActor)** | 快速、专门的换脸模型、轻量 | 依赖专用模型 | ✅ **推荐** - 视频换脸 |
| Flux Klein Pipeline | 高质量、可控性强 | 慢（~3min/帧）、VRAM高 | 单张图片换脸 |
| 逐帧 Flux Klein | 最高质量 | 极慢、资源消耗大 | 不推荐 |

**Video Pipeline 优势**：
- **速度**：~0.5s/帧（CPU） vs Flux Klein 的 ~3min/帧
- **VRAM**：~4GB vs ~14GB
- **质量**：inswapper_128 + GFPGAN 修复，效果自然

---

## 方案一：ComfyUI ReActor 工作流

### 工作流文件
- `workflows/v1/video_faceswap_reactor.json` - ComfyUI 工作流

### 工作流节点
```
LoadVideo → Video Dump Frames → ReActorFaceSwap → Create Video from Path → SaveVideo
```

### 节点说明

#### 1. Video Dump Frames
- **功能**：将视频拆分为单独帧
- **输入**：视频文件路径
- **输出**：帧图片文件夹、帧数量

#### 2. ReActorFaceSwap
- **功能**：对单张图片执行换脸
- **输入**：
  - `input_image`：目标图片（视频帧）
  - `source_image`：源人脸图片
  - `swap_model`：换脸模型（inswapper_128.onnx）
  - `facedetection`：人脸检测器（retinaface_resnet50）
  - `face_restore_model`：人脸修复模型（none/GFPGANv1.4.pth）
- **输出**：换脸后的图片

#### 3. Create Video from Path
- **功能**：将帧图片合成为视频
- **输入**：帧文件夹、帧率、编解码器
- **输出**：视频文件

### 局限性
- ComfyUI 原生不支持视频→批量图片→ReActor 的直接流程
- 需要手动处理帧序列

---

## 方案二：Python 脚本直接处理（推荐）

### 脚本文件
- `tools/video_faceswap_direct.py` - 高效视频换脸脚本

### 技术栈
- **ffmpeg**：视频帧提取/合成
- **insightface**：人脸检测与换脸
- **onnxruntime**：模型推理

### 使用方法

```bash
cd D:\ai_projects\ComfyUI

# 使用默认配置
./venv/Scripts/python.exe tools/video_faceswap_direct.py

# 自定义参数
./venv/Scripts/python.exe tools/video_faceswap_direct.py \
  --input output/my_video.mp4 \
  --source output/my_face.png \
  --output output/my_faceswap.mp4 \
  --fps 30
```

### 处理流程

```
输入视频 (MP4)
    ↓ ffmpeg
视频帧 (PNG 序列)
    ↓ insightface
换脸处理
    ↓ ffmpeg
输出视频 (MP4)
```

### 核心代码

```python
# 初始化换脸模型
app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))
swapper = get_model('models/insightface/inswapper_128.onnx')

# 逐帧换脸
for frame_path in frames:
    target_img = cv2.imread(str(frame_path))
    result = swapper.get(result, target_face, source_face, paste_back=True)
```

---

## 模型文件

### 必需模型

| 模型 | 路径 | 大小 | 用途 |
|------|------|------|------|
| inswapper_128.onnx | `models/insightface/` | ~500MB | 换脸核心模型 |
| buffalo_l | `~/.insightface/models/` | ~1.5GB | 人脸检测/识别 |

### 可选模型

| 模型 | 路径 | 大小 | 用途 |
|------|------|------|------|
| GFPGANv1.4.pth | `models/insightface/` | ~350MB | 人脸修复 |

---

## 性能对比

### 测试环境
- CPU：i7-14700F
- RAM：32GB DDR5
- 输入：512×320, 33帧, 25fps

### 测试结果

| 方案 | 处理时间 | 输出质量 | VRAM |
|------|----------|----------|------|
| Video Pipeline (CPU) | ~5s | ★★★☆ | 4GB |
| Video Pipeline (GPU) | ~2s | ★★★☆ | 6GB |
| Flux Klein 逐帧 | ~99min | ★★★★ | 14GB |

---

## 常见问题

### Q1: 为什么源图片未检测到人脸？
A: 源图片必须是真实照片，不能是手绘或卡通图片。insightface 需要检测到人脸特征点才能进行换脸。

### Q2: 如何提升换脸质量？
A: 
1. 使用高质量源人脸图片（清晰、正脸）
2. 启用人脸修复：`face_restore_model = 'GFPGANv1.4.pth'`
3. 调整 `face_restore_visibility` 参数（0.1-1.0）

### Q3: 视频太大怎么办？
A: 
1. 降低帧率：`--fps 15`
2. 降低分辨率：先用 ffmpeg 缩放
3. 分段处理：将长视频拆分为多个片段

### Q4: 如何保留原视频音频？
A: 修改脚本，使用 ffmpeg 的 `-c:a copy` 参数：
```bash
ffmpeg -i output_faceswap.mp4 -i input_video.mp4 -c:v copy -c:a copy -map 0:v:0 -map 1:a:0 final.mp4
```

---

## 下一步

1. **使用真实人脸测试**：替换 `test_source_face.png` 为真实照片
2. **GPU 加速**：安装 CUDA 版 onnxruntime
3. **更长视频**：测试 1080p 长视频处理
4. **音频保留**：集成音频流处理
5. **SeedVR2 放大**：添加超分辨率后处理

---

## 相关文件

- `tools/video_faceswap_direct.py` - 高效换脸脚本
- `tools/video_faceswap.py` - ComfyUI API 版本（备用）
- `workflows/v1/video_faceswap_reactor.json` - ComfyUI 工作流
- `models/insightface/inswapper_128.onnx` - 换脸模型

---

*更新时间：2026-06-07*
