# MimicMotion 动作迁移工作流

## 概述
MimicMotion（腾讯）将参考视频中的动作迁移到目标人物图片上，生成目标人物执行参考动作的视频。

## 工作流节点流程

```
📷 LoadImage (目标人物)
       ↓
🦴 MimicMotionGetPoses ← VHS_LoadVideo (参考动作视频)
       ↓
⚡ MimicMotionSampler ← DownloadAndLoadMimicMotionModel
       ↓
🎨 MimicMotionDecode
       ↓
🎬 VHS_VideoCombine → 输出视频
```

## 节点说明

| 节点 | 功能 | 关键参数 |
|------|------|---------|
| LoadImage | 加载目标人物图片 | 图片分辨率将决定输出分辨率 |
| VHS_LoadVideo | 加载参考动作视频 | frame_load_cap 控制处理帧数 |
| MimicMotionGetPoses | DWPose 姿态提取 | include_body/hand/face |
| DownloadAndLoadMimicMotionModel | 加载模型 | v1.0 或 v1.1，fp16 精度 |
| MimicMotionSampler | 核心采样 | steps=25, cfg=2-3, context_size=16 |
| MimicMotionDecode | 解码潜空间到图像 | decode_chunk_size=4 |
| VHS_VideoCombine | 合成输出视频 | fps=15, h264-mp4 |

## 依赖模型

### 主模型（~3GB）
- **MimicMotion-fp16.safetensors** 或 **MimicMotionMergedUnet_1-1-fp16.safetensors**
- 下载：`hf download Kijai/MimicMotion_pruned`
- 路径：`ComfyUI/models/mimicmotion/`

### SVD XT 1.1 基础模型（~4GB）
- stable-video-diffusion-img2vid-xt-1-1 (FP16 diffusers 格式)
- 下载：`hf download stabilityai/stable-video-diffusion-img2vid-xt-1-1`
- 路径：`ComfyUI/models/diffusers/stable-video-diffusion-img2vid-xt-1-1/`

### DWPose 模型（自动下载）
- yolox_l.torchscript.pt（人体检测）
- dw-ll_ucoco_384_bs5.torchscript.pt（姿态估计）
- 路径：`ComfyUI/custom_nodes/ComfyUI-MimicMotionWrapper/models/DWPose/`

### PoseNet（内置）
- mimic_motion_pose_net.safetensors（随插件一起提供）

## 推荐参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| model | v1.1 | 更好的质量 |
| precision | fp16 | 16GB VRAM 推荐 |
| steps | 25 | 质量/速度平衡 |
| cfg_min / cfg_max | 2.0 / 3.0 | 引导强度范围 |
| context_size | 16 (v1.0) / 72 (v1.1) | 帧窗口大小 |
| context_overlap | 6 | 帧重叠 |
| fps | 15 | 输出帧率 |

## 硬件要求
- **GPU**: RTX 3060+ (8GB+ VRAM)
- **推荐**: RTX 4060 Ti 16GB ✅ (当前设备)
- **输入分辨率**: 建议 512×768 或 576×1024

## 搭配使用
- **ReActor 换脸**: 在输出视频上叠加人脸一致性
- **GFPGAN 修复**: 增强面部质量
- **RIFE 插帧**: 提升视频流畅度

## 安装
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-MimicMotionWrapper.git
pip install -r ComfyUI-MimicMotionWrapper/requirements.txt
```
