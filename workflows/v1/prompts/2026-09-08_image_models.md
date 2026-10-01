# 图片生成模型清单（ComfyUI）

**任务**：整理当前可用的图片生成模型（不含视频模型）
**日期**：2026-09-08
**备注**：`minimax_h3_*`、`LTX23.gguf` 为视频模型，不在此清单；`sd15_legacy` 为 SD1.5 旧版目录。

## 模型清单

| 类别 | 路径目录 | 模型文件 | 用途 / 备注 |
|---|---|---|---|
| FLUX | `models/diffusion_models/` | `flux1-dev-fp8.safetensors` | FLUX dev fp8，16GB 卡主力文生图 |
| FLUX | `models/unet/` | `T8-flux.1-dev-abliterated-V2-GGUF-Q8_0.gguf` | FLUX abliterated，Q8 量化（更高精度） |
| FLUX | `models/unet/` | `T8-flux.1-dev-abliterated-V2-GGUF-Q4_K_M.gguf` | FLUX abliterated，Q4 量化（省显存） |
| SD1.5 | `models/checkpoints/` | `majicmixRealistic_v7.safetensors` | 写实人像 |
| SD1.5 | `models/checkpoints/` | `AOM3A3_orangemix.safetensors` | 动漫风格 |
| SD1.5 | `models/checkpoints/` | `Counterfeit-V3.0_fp16.safetensors` | 动漫风格 fp16 |
| SD1.5 | `models/checkpoints/` | `sd15_legacy/` | SD1.5 旧版（目录） |

## 使用建议（16GB 卡）

- **文生图主力**：FLUX dev fp8（`flux1-dev-fp8`），兼顾质量与显存。
- **需省显存 / 长程批量**：FLUX abliterated Q4_K_M（Q8 精度更高但更吃显存）。
- **写实人像**：SD1.5 `majicmixRealistic_v7`。
- **动漫二次元**：SD1.5 `AOM3A3_orangemix` / `Counterfeit-V3.0_fp16`。