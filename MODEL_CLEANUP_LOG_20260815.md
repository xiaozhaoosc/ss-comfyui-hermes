# 模型去重与清理操作记录

**执行日期**: 2026-08-15
**操作类型**: 重复模型硬链接去重 + incomplete 下载残留删除
**目标目录**: `d:\ai_projects\ComfyUI\models\`

## 操作策略

- **重复文件**: 采用硬链接（Hard Link）替换，保留一份原文件，其他位置用硬链接重建。
  - 所有原有路径仍然有效，不会出现"找不到文件"
  - 磁盘只占用一份空间
  - 硬链接要求：同一卷（D: 盘内）✓
- **incomplete 文件**: 直接删除（HuggingFace 下载中断的残留，无任何用途）

---

## Part 1: 重复文件硬链接去重

所有重复文件均已通过 SHA256 哈希校验，确认内容完全一致。

### 组 1: flux1-fill-dev.safetensors（节省 22.7 GB）

| 操作 | 路径 | SHA256 前 16 位 | 大小 (MB) |
|---|---|---|---|
| 保留（主文件） | `unet\flux1-fill-dev.safetensors` | 03E289F530DF51D0 | 22702.1 |
| 删除原文件 + 创建硬链接 | `diffusion_models\flux1-fill-dev.safetensors` | 03E289F530DF51D0 | 22702.1 |

### 组 2: ltx-2.3-22b-dev-Q2_K.gguf（节省 7.9 GB）

| 操作 | 路径 | SHA256 前 16 位 | 大小 (MB) |
|---|---|---|---|
| 保留（主文件） | `LTX-2\ltx-2.3-22b-dev-Q2_K.gguf` | 67C2B4981EEF1C29 | 7892.6 |
| 删除原文件 + 创建硬链接 | `diffusion_models\ltx-2.3-22b-dev-Q2_K.gguf` | 67C2B4981EEF1C29 | 7892.6 |

### 组 3: ltx-2.3-22b-distilled-lora-384-1.1.safetensors（节省 7.3 GB）

| 操作 | 路径 | SHA256 前 16 位 | 大小 (MB) |
|---|---|---|---|
| 保留（主文件） | `LTX-2\ltx-2.3-22b-distilled-lora-384-1.1.safetensors` | F5D4953F3386197A | 7253.2 |
| 删除原文件 + 创建硬链接 | `loras\ltxv\ltx2\ltx-2.3-22b-distilled-lora-384-1.1.safetensors` | F5D4953F3386197A | 7253.2 |

### 组 4: Wan2.2_VAE.pth（节省 2.7 GB）

| 操作 | 路径 | SHA256 前 16 位 | 大小 (MB) |
|---|---|---|---|
| 保留（主文件） | `vae\Wan2.2_VAE.pth` | 20EB789667FA5E60 | 2688.3 |
| 删除原文件 + 创建硬链接 | `diffusion_models\wan2.2-ti2v-5b\Wan2.2_VAE.pth` | 20EB789667FA5E60 | 2688.3 |

### 组 5: vae_with_config.safetensors（节省 1.4 GB）

| 操作 | 路径 | SHA256 前 16 位 | 大小 (MB) |
|---|---|---|---|
| 保留（主文件） | `vae\vae_with_config.safetensors` | DBB98C7CC46F2AF8 | 1385.0 |
| 删除原文件 + 创建硬链接 | `LTX-2\vae_with_config.safetensors` | DBB98C7CC46F2AF8 | 1385.0 |

> 注意：`vae\vae_with_config_fixed.safetensors` 是另一个独立文件（未列入去重），保留不动。

### 组 6: ltx-2.3-spatial-upscaler-x2-1.1.safetensors（节省 0.9 GB）

| 操作 | 路径 | SHA256 前 16 位 | 大小 (MB) |
|---|---|---|---|
| 保留（主文件） | `latent_upscale_models\ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | 5F416311FA8172B6 | 949.6 |
| 删除原文件 + 创建硬链接 | `LTX-2\ltx-2.3-spatial-upscaler-x2-1.1.safetensors` | 5F416311FA8172B6 | 949.6 |

### 组 7: ae.safetensors（节省 0.6 GB）

| 操作 | 路径 | SHA256 前 16 位 | 大小 (MB) |
|---|---|---|---|
| 保留（主文件） | `vae\ae.safetensors` | AFC8E28272CD15DB | 319.8 |
| 删除原文件 + 创建硬链接 | `FLUX.1-dev\ae.safetensors` | AFC8E28272CD15DB | 319.8 |
| 删除原文件 + 创建硬链接 | `split_files\vae\ae.safetensors` | AFC8E28272CD15DB | 319.8 |

### Part 1 小计

- 重复组数: 7
- 涉及文件: 16 个（保留 7 个主文件 + 硬链接替换 9 个）
- **预计节省空间: ~43.5 GB**

---

## Part 2: incomplete 下载残留删除

以下 19 个文件均为 HuggingFace 下载中断产生的残留文件（`.incomplete` 后缀），无任何用途，直接删除。

| # | 大小 (MB) | 路径 |
|---|---|---|
| 1 | 4047.8 | `diffusion_models\.cache\huggingface\download\bUAlLkE0rb4i2pdDDxBG2AfLEMI=.5489463ed96056b0bb5472abb5d1bba7055e48d574e37877acb43b407465e26f.incomplete` |
| 2 | 4040.0 | `FLUX.1-dev\.cache\huggingface\download\transformer\diffusion_pytorch_model-00001-of-00003.safetensors.d86a3038eacaa720682cb9b1da3c49fecf8a3ded605af4def6061eaa18903eb8.incomplete` |
| 3 | 2540.0 | `LLM\Florence-2-Flux-Large\.cache\huggingface\download\model.safetensors.82d0f8da156f27d64c31abef8281b1c4cb646ec4edfab2debe5f64a78d208946.incomplete` |
| 4 | 1434.3 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\multi\yVcA9C8fbu6v8ynlve2f9uTtUUA=.b6314d05ef916131f726ec61ac3292a5f2e08d1d66cabb339340d62cc775f31d.8e336b12.incomplete` |
| 5 | 680.0 | `LLM\Florence-2-large\.cache\huggingface\download\pytorch_model.bin.8b7d99c2ca930af3bcc4625df55c82b6bb372456280310b5189c519d6083a270.incomplete` |
| 6 | 623.7 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\quant_models\3KJQU-YlbVT-f-if5d05juzGois=.ec64b182041c0c4357215fa429cc0308861ff7d642addb47840f621bbe565060.7b5f483d.incomplete` |
| 7 | 495.8 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\quant_models\I-0lOnUO88Tfqminhy4Csep7R9Q=.5cb097f827f03368f9aaed8f69c1d357179b9268dafb8e80f2312a7067205045.5fd0ff02.incomplete` |
| 8 | 130.0 | `LLM\Florence-2-large-PromptGen-v2.0\.cache\huggingface\download\model.safetensors.95b6441fb8e3a96b1f6ec0ac894a7632ea49fc77c0dd623a7a53d1d879390321.incomplete` |
| 9 | 127.9 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\comfyui\XRoPC5tZpOKFkMwjqzqBteXOj20=.11d4871b75bee91f4fe4d5c9f44ff966221b27a3dcb7558e511ac25a2c0e9925.9ce572d8.incomplete` |
| 10 | 63.9 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\comfyui\LnveaHJ9X3DWMZIHBPLMgWAJovQ=.d1fd59550aaed24cffba79117ca385eec56529becbe3ab2ec5b5b7f4eeb30274.750ed5e8.incomplete` |
| 11 | 30.0 | `CogVideo\loras\CogVideoX-Fun-V1.1-5b-InP\.cache\huggingface\download\vae\diffusion_pytorch_model.safetensors.bd47d57ad948ff80da0af0cb2e4dcdef65073aba59bccfd383ada9a7d1c02024.incomplete` |
| 12 | 24.4 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\quant_models\EMFrrqeQVmemrt0zlh-hZ1e2dcc=.bdd16124c97872ea59423674bf9244ca6697e920cb673c7bddc2558d1f689384.371f8c0a.incomplete` |
| 13 | 20.0 | `CogVideo\loras\CogVideoX-Fun-V1.1-5b-InP\.cache\huggingface\download\transformer\diffusion_pytorch_model.safetensors.4ec6b5cd7cb532bc83aba3f36fb35d2b27ca0f7165c07828b999bf66264ac6c7.incomplete` |
| 14 | 18.5 | `checkpoints\.cache\huggingface\download\8SUVQLXMQv0MHKVvCzb8RQ6zFt4=.865ba09f5b4c3cbd3468a4bd3acb9fcb2f8740c54317482f0bcd4ed1d3655cee.incomplete` |
| 15 | 16.1 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\quant_models\I_KmFsOkfwpnA4ihfaO1MTDdCE0=.f2bb904f203d260d45d213f642aa1fd424a19dc3532181653417ac405d62072d.b819a759.incomplete` |
| 16 | 15.2 | `.cache\huggingface\download\diffusion_models\QZ7NWmQSkg-04uFSVoyj_16vWjU=.a0226eaa2c3e6f47ae5ce83225120f16479da890ced1a3bc32b1a14619787914.incomplete` |
| 17 | 0.0 | `.cache\huggingface\download\split_files\text_encoders\vpP8tMlfjuF28Z7l8iatOGCHmrM=.6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a.incomplete` |
| 18 | 0.0 | `.cache\huggingface\download\split_files\diffusion_models\7bqBrVJN8g55dEA1XXXGHgzHm64=.2407613050b809ffdff18a4ac99af83ea6b95443ecebdf80e064a79c825574a6.incomplete` |
| 19 | 0.0 | `InfiniteTalk\InfiniteTalk\.cache\huggingface\download\quant_models\jKBid-StGwLzX69yjJS2-KdNRLA=.b82acd84dd5e5be5a1caad1112df67c26677598ed9b93581a6cb42827de5a5f6.db642400.incomplete` |

### Part 2 小计

- 文件数: 19
- **预计释放空间: ~14.3 GB**

---

## 总计

| 类别 | 节省空间 |
|---|---|
| Part 1: 重复文件硬链接去重 | ~43.5 GB |
| Part 2: incomplete 残留删除 | ~14.3 GB |
| **合计** | **~57.8 GB** |

---

## 回滚说明

### 硬链接回滚
硬链接在文件系统层面等同于原文件，无需回滚。如需恢复为独立文件副本，执行：
```powershell
# 示例：恢复 diffusion_models\flux1-fill-dev.safetensors 为独立文件
Copy-Item -Path "unet\flux1-fill-dev.safetensors" -Destination "diffusion_models\flux1-fill-dev.safetensors" -Force
```

### incomplete 文件回滚
incomplete 文件为下载残留，无法恢复。如需对应模型，需重新从 HuggingFace 下载。

---

## 执行状态

- [x] 文档创建: 2026-08-15
- [x] 硬链接去重执行: 2026-08-15（8 个文件替换为硬链接，节省 42.49 GB）
- [x] incomplete 删除执行: 2026-08-15（19 个文件删除，释放 13.97 GB）
- [x] 最终验证: 2026-08-15
  - 8 个硬链接全部 SHA256 校验通过（MATCH）
  - 0 个 .incomplete 文件残留
  - D: 盘剩余空间: 141.46 GB

## 实际释放空间汇总

| 类别 | 计划 | 实际 |
|---|---|---|
| Part 1: 重复文件硬链接去重 | ~43.5 GB | 42.49 GB |
| Part 2: incomplete 残留删除 | ~14.3 GB | 13.97 GB |
| **合计** | **~57.8 GB** | **56.46 GB** |
