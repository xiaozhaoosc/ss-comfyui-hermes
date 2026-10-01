# LTX-2.3 删除操作记录

**日期**: 2026-08-15
**原因**: ComfyUI-LTXVideo 插件与 ComfyUI 0.30.0 不兼容（ImportError: cannot import name 'interleaved_freqs_cis'），LtxvApiTextToVideo 节点需云端登录认证，本地无法使用。经测试验证不可用，决定删除全部 LTX-2.3 相关文件释放磁盘空间。

## 删除清单

### 1. 模型文件（项目内，约 99.2 GB）

| 路径 | 大小 |
|------|------|
| models/LTX-2/ （含 ltx-2.3-22b-distilled-1.1.safetensors, ltx-2.3-22b-dev-Q2_K.gguf, gemma-3-12b 文本编码器, sharded_v2 分片等） | 85537.6 MB |
| models/diffusion_models/ltx-2.3-22b-dev-Q2_K.gguf （副本） | 7892.6 MB |
| models/loras/ltxv/ltx2/ （LoRA 副本） | 7253.2 MB |
| models/latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors （副本） | 949.6 MB |

### 2. 模型文件（外部共享目录，约 83.5 GB）

| 路径 | 大小 |
|------|------|
| D:/OLLAMA_MODELS/models/LTX-2/ （与项目内目录结构一致） | 85537.6 MB |

### 3. ComfyUI-LTXVideo 插件（约 60 MB）

| 路径 | 说明 |
|------|------|
| custom_nodes/ComfyUI-LTXVideo/ | 完整插件目录，含节点、示例工作流、资源 |

### 4. 用户工作流文件

| 路径 |
|------|
| workflows/v1/ltxv_23_test.json |
| workflows/v1/ltxv_23_gguf_test.json |
| workflows/v1/ltxv_23_gguf_optimized.json |
| workflows/v1/ltxv_23_gguf_hires.json |
| ltxv_23_test_api.json |
| tools/workflows/v1/ltxv_23_test.json |
| tools/workflows/v1/ltxv_23_gguf_test.json |
| tools/workflows/v1/ltxv_23_gguf_optimized.json |
| tools/workflows/v1/ltxv_23_gguf_hires.json |

### 5. 工具脚本（依赖 LTX-2.3，无法独立使用）

| 路径 | 说明 |
|------|------|
| tools/ltx_faceswap_pipeline.py | LTX-2.3 生成 + insightface 换脸管道 |
| tools/workflows/v1/ltx_faceswap_pipeline_README.md | 管道说明文档 |

### 6. 配置文件修改

| 文件 | 修改内容 |
|------|----------|
| extra_model_paths.yaml | 移除 ltx2: 配置块（第 24-30 行） |

### 7. 保留项（不删除）

| 路径 | 原因 |
|------|------|
| venv/Lib/site-packages/comfyui_workflow_templates_json/templates/video_ltx2_3_*.json | 属于 ComfyUI 安装包内置模板，非用户自建 |
| venv/Lib/site-packages/comfyui_workflow_templates_json/templates/video_ltx2_*.json | 同上 |
| venv/Lib/site-packages/comfyui_workflow_templates_json/templates/ltxv_*.json | 同上 |
| blueprints/*.json | ComfyUI 前端蓝图模板，属于安装包 |

## 空间释放预估

- 项目内: ~99.2 GB（模型副本 + 插件 + 工作流）
- 外部共享: ~83.5 GB
- 总计: ~182.7 GB

## 执行结果（2026-08-15 01:10）

| 项目 | 状态 | 备注 |
|------|------|------|
| models/LTX-2/ | 已删除 | 85537.6 MB |
| models/diffusion_models/ltx-2.3-22b-dev-Q2_K.gguf | 已删除 | 7892.6 MB |
| models/loras/ltxv/ltx2/ | 已删除 | 7253.2 MB |
| models/latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors | 已删除 | 949.6 MB |
| D:/OLLAMA_MODELS/models/LTX-2/ | 不存在 | 盘点时可能为配置路径映射，实际未找到 |
| custom_nodes/ComfyUI-LTXVideo/ | 已删除 | 60 MB |
| workflows/v1/ltxv_23_*.json (4个) | 已删除 | |
| ltxv_23_test_api.json | 已删除 | |
| tools/workflows/v1/ltxv_23_*.json (4个) | 不存在 | 盘点误报 |
| tools/ltx_faceswap_pipeline.py | 已删除 | |
| tools/workflows/v1/ltx_faceswap_pipeline_README.md | 已删除 | |
| extra_model_paths.yaml ltx2 配置块 | 已移除 | 第 24-30 行 |

实际释放空间: ~101.7 GB（项目内模型 + 插件 + 工作流）

