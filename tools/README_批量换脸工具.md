# 批量视频换脸 + AI水印 + 语录 + 混音

## 概述
一键完成：ComfyUI批量换脸 → 恢复原声10%+逍遥仙75%混音 → AI生成水印 → 底部语录叠加 → 语录重命名

## 文件结构
```
D:\ai_projects\ComfyUI\tools\
├── batch_faceswap_overlay.py    # ✨ 一键启动脚本（全流程）
├── add_text_overlay.py          # 单独后处理（水印+语录+重命名）
├── restore_and_mix_audio.py     # 单独音频处理（恢复原声+混音）
└── quotes.json                  # 语录库（52条：国学/鸡汤/热梗）
```

## 一键启动

```bash
# 完整流程：换脸 + 原声10% + 逍遥仙75% + AI水印 + 语录 + 重命名
python tools\batch_faceswap_overlay.py \
  --input "D:\ai_projects\ComfyUI\input\新视频目录" \
  --face "D:\ai_projects\ComfyUI\input\todo\face\ken4.png" \
  --output "D:\ai_projects\ComfyUI\output\final" \
  --bg-music "D:\ai_projects\ComfyUI\input\music\01. 逍遥仙.flac" \
  --bg-volume 0.75 \
  --orig-volume 0.10

# 跳过换脸（已有结果时）
python tools\batch_faceswap_overlay.py \
  --input "已有换脸结果目录" \
  --face "xxx" \
  --output "输出目录" \
  --skip-faceswap \
  --original-dir "原始视频目录（有音频）" \
  --bg-music "音乐文件" \
  --bg-volume 0.75 \
  --orig-volume 0.10

# 只恢复原声，不加BGM
python tools\batch_faceswap_overlay.py ... --no-music

# 只用国学类语录
python tools\batch_faceswap_overlay.py ... --category 国学
```

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--input` | ✅ | 输入视频目录 |
| `--face` | ✅ | 人脸图片路径 |
| `--output` | ✅ | 最终输出目录 |
| `--skip-faceswap` | ❌ | 跳过换脸步骤 |
| `--original-dir` | ❌ | 原始视频目录（有音频，用于音频恢复） |
| `--bg-music` | ❌ | 背景音乐路径（默认自动从 input/music 选取） |
| `--bg-volume` | ❌ | 背景音乐音量（默认: 0.75） |
| `--orig-volume` | ❌ | 原声音量（默认: 0.10） |
| `--no-music` | ❌ | 不添加背景音乐，只恢复原声 |
| `--category` | ❌ | 语录分类: 国学/鸡汤/热梗 |

## 已知坑（开发备忘）

1. **FFmpeg 中文路径**：Windows上FFmpeg无法读取含中文的文件路径（Illegal byte sequence）。脚本自动复制到ASCII临时目录处理。
2. **amix 自动归一化**：默认 `amix` 会降低各输入音量。必须用 `normalize=0` 保持原始音量比例。
3. **aloop 超时**：`aloop=loop=-1:size=2e+09` 在48kHz FLAC上极慢。改用 `-stream_loop -1`（输入级循环）。
4. **enable 表达式转义**：`between(t\,0\,5)` 在嵌套f-string中转义错乱。用变量拼接：`enable_expr = "between(t\\,0\\,5)"`。

## 语录库

52条语录（国学18 + 鸡汤16 + 热梗18），编辑 `quotes.json` 扩充：
```json
{"text": "语录内容", "source": "来源", "category": "分类"}
```

## 输出示例

```
输出目录/
├── 长风破浪会有时，直挂云帆济沧海.mp4    ← 换脸+原声10%+逍遥仙75%+AI水印+底部语录
├── 格局打开.mp4
├── 双向奔赴才有意义.mp4
└── ...
```

## 依赖

- Python 3.10+ | FFmpeg (scoop install ffmpeg) | ComfyUI + ReActor + VHS
