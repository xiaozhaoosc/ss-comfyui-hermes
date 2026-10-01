# Standard Image Face Swap Pro

增强版图片换脸工作流，基于 ReActor + GFPGAN。

## 节点流程

```
📷 Source Face ──┐
                  ├── 🔄 ReActor Face Swap ──┬── 💾 Save (raw)
🎯 Target Image ─┘                            ├── ✨ GFPGAN Restore ── 💾 Save (restored)
                                              ├── 🚀 Face Boost (可选)
                                              ├── ⚙️ Options
                                              └── 📦 Save Face Model (缓存)
```

## 节点说明

| 节点 | ID | 说明 |
|------|-----|------|
| Source Face | #1 | 源脸图片（你想要的脸） |
| Target Image | #2 | 目标图片（要换脸的图） |
| ReActor Face Swap | #3 | 核心换脸节点 |
| GFPGAN Restore | #4 | 面部修复/增强 |
| Save (raw) | #5 | 保存原始换脸结果 |
| Save (restored) | #6 | 保存修复后的结果 |
| Face Boost | #7 | 额外增强（默认关闭） |
| Options | #8 | 多脸/性别检测等高级选项 |
| Save Face Model | #9 | 缓存源脸模型，加速后续使用 |

## 关键参数

### ReActor Face Swap (#3)
- `swap_model`: inswapper_128.onnx（默认，最佳质量）
- `facedetection`: retinaface_resnet50（最准确）
- `input_faces_index`: 目标图中要替换的脸（"0"=第一张脸）
- `source_faces_index`: 源图中使用的脸（"0"=第一张脸）

### GFPGAN Restore (#4)
- `visibility`: 0.8（修复强度，1.0=最大）
- `codeformer_weight`: 0.5（0=GFPGAN风格，1=CodeFormer风格）
- 设为 `model: "none"` 可跳过修复

### Face Boost (#7)
- `enabled`: false（默认关闭，需要时开启）
- 用于在 GFPGAN 基础上进一步增强细节

### 多脸场景
- `input_faces_index`: "0,1,2" 替换多张脸
- `detect_gender_input/source`: "male"/"female" 按性别过滤

## 依赖模型
- `models/insightface/inswapper_128.onnx` ✅ 已有
- `models/insightface/models/buffalo_l/` ✅ 已有
- `models/facerestore_models/GFPGANv1.4.pth` ✅ 已有

## 使用方式
1. 在 ComfyUI 中加载此工作流
2. 上传源脸图片到节点 #1
3. 上传目标图片到节点 #2
4. 点击 Queue Prompt 执行
5. 输出保存在 `output/faceswap_raw_*` 和 `faceswap_restored_*`
