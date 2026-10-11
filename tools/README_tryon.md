# 换脸+换装工具集

> 路径: `D:\ai_projects\ComfyUI\tools\`
> 更新: 2026-06-11

---

## 一键使用

### 图片换装（最简）
```bash
python tools/tryon.py --input photo.jpg --garment shirt.jpg --output result.png --garment-desc "white shirt"
```

### 图片换脸+换装
```bash
python tools/tryon.py --input photo.jpg --face target.jpg --garment shirt.jpg --output result.png --garment-desc "white shirt"
```

### 视频换装
```bash
python tools/tryon.py --input video.mp4 --garment shirt.jpg --output result.mp4 --garment-desc "white shirt" --fps 5 --frame-skip 5 --steps 10
```

`tryon.py` 会自动生成 mask 和 pose，无需手动准备。

---

## 工具清单

| 脚本 | 用途 | 推荐用法 |
|------|------|----------|
| **`tryon.py`** | 🌟 一键换装（自动 mask/pose） | 日常使用 |
| `faceswap_tryon_pipeline.py` | 底层流水线（手动指定参数） | 调试/高级用法 |
| `batch_faceswap.py` | 批量视频换脸 | 多视频处理 |
| `gen_mask.py` | 生成上衣遮罩 | 自定义 mask |
| `fix_mask.py` | 修复 mask（排除头部+渐变） | mask 质量优化 |
| `gen_pose.py` | 生成姿态骨架 | 自定义 pose |
| `download_unet_fast.py` | UNet 模型下载 | 模型安装 |
| `hf_speed_test.py` | HF 镜像源测速 | 网络诊断 |
| `test_idm_vton_clean.py` | IDM-VTON 推理测试 | 模型验证 |

---

## 参数参考

### tryon.py 参数

| 参数 | 必须 | 默认 | 说明 |
|------|------|------|------|
| `--input` | ✅ | - | 输入图片/视频 |
| `--garment` | ✅ | - | 目标服装图片 |
| `--output` | ✅ | - | 输出路径 |
| `--face` | ❌ | None | 目标人脸（不指定=跳过换脸） |
| `--garment-desc` | ❌ | "garment" | 服装文字描述 |
| `--steps` | ❌ | 20 | 推理步数 |
| `--fps` | ❌ | 源帧率 | 视频输出帧率 |
| `--frame-skip` | ❌ | 1 | 每N帧处理一帧 |
| `--pose` | ❌ | 自动生成 | 姿态图路径 |
| `--mask` | ❌ | 自动生成 | 遮罩图路径 |

### 性能参数建议

| 场景 | steps | fps | frame-skip | 预估时间 |
|------|-------|-----|------------|----------|
| 图片高质量 | 30 | - | - | ~6分钟 |
| 图片快速预览 | 10 | - | - | ~2分钟 |
| 视频高质量 | 20 | 5 | 3 | ~50分钟/25秒视频 |
| 视频快速预览 | 10 | 3 | 6 | ~15分钟/25秒视频 |
| 视频极速预览 | 5 | 2 | 10 | ~5分钟/25秒视频 |

---

## 输出目录

```
output/
├── full_faceswap_tryon_v2.png    # 最佳图片结果
├── video_tryon_test.mp4          # 视频测试结果
├── batch_faceswap/               # 批量换脸结果
│   ├── 1_faceswap.mp4
│   └── 2_faceswap.mp4
└── ...
```

---

## 环境依赖

- Python 3.10+ (ComfyUI venv)
- PyTorch + CUDA
- diffusers 0.38.0
- transformers
- insightface
- gfpgan
- onnxruntime
- opencv-python
- Pillow
- numpy

模型文件见 `models/IDM-VTON/` 和 `models/insightface/`。
