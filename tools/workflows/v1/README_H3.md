# MiniMax H3 文生视频 + 原生音频 — 工作流说明

> 版本：v1（试映版）· 日期：2026-08-27 · 用途：「烽火边关」战争预告片分段生成

## 一、模型清单（5 个文件，都在 `D:\OLLAMA_MODELS\models\`）

| 组件 | 文件 | 子目录 |
|---|---|---|
| 主模型 | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `diffusion_models/` |
| 文本编码器（**越狱版**） | `qwen3vl_32b_heretic_minimax_h3_nvfp4.safetensors` | `text_encoders/` |
| 文本编码器（官方版，备份） | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `text_encoders/` |
| 视频 VAE | `minimax_h3_video_vae_fp16.safetensors` | `vae/` |
| 音频 VAE | `minimax_h3_audio_vae_fp32.safetensors` | `vae/` |

> 注：`D:\ai_projects\ComfyUI\models` 是指向 `D:\OLLAMA_MODELS\models` 的目录链接（Junction），两边是同一份文件。

## 二、节点链路（文生视频 + 原生音频）

```
UNETLoader (主模型)
    └─→ MiniMaxH3SigmaShift ─→ KSampler(model)
CLIPLoader (type=minimax, 越狱版) ─→ MiniMaxH3ImageToVideo(clip) ─→ KSampler(positive/negative/latent)
VAELoader (视频VAE) ─→ MiniMaxH3ImageToVideo(vae)
                      └─→ VAEDecode(vae) ─→ VHS_VideoCombine → MP4
VAELoader (音频VAE) ─→ VAEDecodeAudio(vae) ─→ SaveAudio → FLAC
KSampler(samples) ─→ VAEDecode + VAEDecodeAudio（H3 联合 AV 潜空间双解码）
```

关键点：
- **CLIPLoader 的 type 必须选 `minimax`**（不是 stable_diffusion 等）
- `VAEDecodeAudio` 会自动从 H3 联合潜空间提取音频部分（`latent.unbind()[-1]`），输出 32kHz 立体声
- 采样器用 `euler` + `simple`，cfg=1.0（flow matching 无 CFG）
- 负面 conditioning 直接复用正面输出（cfg=1.0 时忽略）

## 三、工作流文件

| 文件 | 格式 | 用途 |
|---|---|---|
| `h3_t2va_audio_ui.json` | **UI 图格式** | 拖入 ComfyUI 界面直接操作（改提示词/参数点 Queue） |
| `h3_t2va_audio_api.json` | **API 格式** | 脚本/API 提交（`POST /prompt`） |
| `h3_t2va_segment.json` | API 格式 | 纯视频版模板（无音频节点） |

> UI 格式已同步复制到 `ComfyUI\user\default\workflows\h3_烽火边关_文生视频+音频.json`，界面「工作流」菜单里可直接打开。

## 四、在界面里操作

1. 打开 ComfyUI（`http://127.0.0.1:8188`）
2. 菜单「工作流 → 打开」，或直接把 `h3_t2va_audio_ui.json` 拖进画布
3. 在 **🎬 H3 文生视频** 节点里改：提示词、分辨率（width/height，16 的倍数）、时长（length）
4. 点「运行」即可，视频存 `output/fenghuo/`，音频存 `output/fenghuo_audio/`

## 五、关键参数与坑

- **时长网格**：length 是 24fps 帧数，自动向上取整到「17k+5」网格（107≈4.46s，124≈5.17s，175≈7.3s，192≈8s）
- **分辨率**：width/height 需为 32 的倍数，16:9 常用 672×384（小尺寸）或 1344×768（高清）
- **seed 一致性**：同 seed 可复现同画面（用于补音频时保持画面一致）
- **低显存**：16GB 卡用 `--lowvram` 跑；672×384 下约 3 分钟/段（20 步）
- **越狱版 vs 官方版**：文本编码器选 `heretic`（越狱），官方 `awq` 留作备份，两者同尺寸可互换

## 六、脚本（`ComfyUI\tools\`）

| 脚本 | 作用 |
|---|---|
| `submit_h3_segments.py` | 批量提交 7 段视频（无音频） |
| `submit_h3_audio.py` | 批量提交 7 段视频+音频 |
| `monitor_h3_segments.py` | 监控生成进度（传 pids 文件路径） |
| `merge_h3_segments.py` | ffmpeg 合并 7 段视频 |
| `mux_h3_audio.py` | 合并 7 段音频并混入视频（AAC 192k） |

## 七、启动 ComfyUI

```bash
cd D:\ai_projects\ComfyUI
TQDM_DISABLE=1 "C:/Users/kenzhao/anaconda3/python.exe" -u main.py --lowvram --listen 0.0.0.0 --port 8188
```

（等价于 `start_comfyui.bat`，需 anaconda3 的 python，非 venv）
