# 🌟 Flux.1 Dev + PuLID 商业换脸 Python API 驱动项目

本项目提供了基于 Python API 调用 ComfyUI 实现**高精度商业人像换脸与动作迁移**的完整实战闭环。

---

## 📦 前置环境与依赖

```bash
pip install websocket-client requests
```

### 必需模型 (存放至 ComfyUI 对应子目录)

| 模型 | 存放路径 | 大小 |
| :--- | :--- | :--- |
| `flux1-dev-fp8.safetensors` | `models/unet/` | ~12 GB |
| `t5xxl_fp8_e4m3fn.safetensors` | `models/clip/` | ~4.7 GB |
| `clip_l.safetensors` | `models/clip/` | ~235 MB |
| `ae.safetensors` | `models/vae/` | ~320 MB |
| `pulid_flux_v1.safetensors` | `models/pulid/` | ~1.1 GB |
| `EVA02_CLIP_L_336_psz14_s6B.pt` | `models/eva_clip/` | ~420 MB |
| InsightFace 全套 | `models/insightface/` | ~880 MB |

### 必需自定义节点
- `ComfyUI-PuLID-Flux` (通过 ComfyUI Manager 安装)

---

## 🚀 快速使用

### 单张换脸
```bash
python run_flux_pulid.py --face "path/to/face.png" --body "path/to/body.png"
```

### 自定义参数
```bash
python run_flux_pulid.py \
    --face "face.png" \
    --body "body.png" \
    --prompt "A cinematic photo of a model in luxury dress" \
    --weight 0.85 \
    --guidance 3.5 \
    --steps 20 \
    --denoise 0.35 \
    --output "output/"
```

### 参数扫描模式 (自动遍历 weight × guidance 组合)
```bash
python run_flux_pulid.py --face "face.png" --body "body.png" --sweep
```

---

## 🔧 架构设计

本项目基于 [ComfyClient SDK](../sdk/comfy_client.py) 构建：

```
run_flux_pulid.py
    └── sdk/comfy_client.py
          ├── upload_image()          # 图片上传
          ├── find_node_by_title()    # Title 锚定寻址
          ├── queue_prompt()          # 队列提交 (含重试)
          ├── track_progress()        # WebSocket 进度追踪
          ├── download_outputs()      # 产物下载
          └── run_workflow()          # 一键运行
```

### Title 锚定寻址 (防抖设计)
不硬编码节点数字 ID，而是通过 `_meta.title` 动态定位，使脚本不会因 Web UI 微调而失效。
