# 我的女友是丧尸 - AI短剧生成项目

## 项目概述
使用 ComfyUI + Wan2.1 T2V 模型生成丧尸末日恋爱题材AI短剧，包含视频生成、TTS配音、字幕叠加的完整流水线。

---

## 一、技术方案

### 1.1 核心技术栈
| 组件 | 技术选型 | 说明 |
|------|----------|------|
| 视频生成 | Wan2.1 T2V 1.3B | ComfyUI 集成，文生视频 |
| CLIP编码器 | UMT5-XXL (4096维) | 自行转换，兼容 Wan2.1 |
| VAE | Wan2.1_VAE.pth | 官方提供 |
| TTS配音 | Edge TTS | 微软免费TTS，支持中文 |
| 字幕叠加 | FFmpeg drawtext | 批量烧录字幕 |
| 视频拼接 | FFmpeg concat | 多段视频合并 |

### 1.2 硬件环境
- GPU: NVIDIA RTX 4060 Ti 16GB
- 内存: 32GB DDR5
- ComfyUI模式: `--lowvram`（显存优化）

### 1.3 网络环境
- 局域网IP: 192.168.1.9
- WireGuard: 10.8.0.4
- SMB共享: `\\192.168.1.9\ComfyUI-Output`

---

## 二、实现过程

### 2.1 模型准备

#### CLIP编码器转换
**问题**: 官方提供的 `models_t5_umt5-xxl-enc-bf16.pth` 键名与 ComfyUI 不兼容
- 原始模型: 768维输出
- Wan2.1 需要: 4096维输出

**解决方案**:
1. 分析 ComfyUI 期望的键名格式（HuggingFace标准）
2. 创建键名映射表，转换 328 个张量
3. 嵌入 `spiece_model` tokenizer（Wan模型必需）
4. 输出: `models/clip/umt5xxl_encoder.safetensors` (10.59GB)

```python
# 关键映射示例
'encoder.block.0.layer.0.SelfAttention.q.weight'
→ 'encoder.block.0.layer.0.SelfAttention.q.weight'  # 保持一致
```

#### VAE模型
- 文件: `Wan2.1_VAE.pth`
- 位置: `models/vae/`
- 无需转换，直接使用

### 2.2 视频生成

#### 工作流配置
```json
{
  "width": 832,
  "height": 480,
  "num_frames": 81,  // 约5秒 @ 16fps
  "steps": 25,
  "cfg": 7.0,
  "sampler": "uni_pc",
  "scheduler": "normal"
}
```

#### 人物一致性策略
统一使用固定的人物描述提示词：
```
east asian young woman, 22 years old, long black hair, 
pale skin, zombie-like appearance with subtle grey-green tint, 
wearing torn casual clothes, expressive eyes, 
apocalyptic background with ruined buildings and overgrown vegetation
```

#### 场景生成
共 20 个场景，分 4 集：
| 集数 | 场景编号 | 时长 |
|------|----------|------|
| EP1 | 1-5 | 25秒 |
| EP2 | 6-10 | 25秒 |
| EP3 | 11-15 | 25秒 |
| EP4 | 16-20 | 25秒 |

### 2.3 TTS配音

#### 配音方案
- 引擎: Edge TTS
- 语言: 中文（徐州方言元素）
- 语速: 默认
- 情感: 根据场景调整

#### 输出格式
- 文件: `scene_XX.mp3`
- 位置: `\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸_成品\tts\`

### 2.4 后期处理

#### 字幕叠加
```bash
ffmpeg -i input.mp4 -vf "drawtext=fontfile=msyh.ttc:text='字幕内容':fontsize=24:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-60" -c:a copy output.mp4
```

#### 音视频合并
```bash
ffmpeg -i video.mp4 -i audio.mp3 -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest output.mp4
```

#### 视频拼接
```bash
# 创建文件列表
echo "file 'scene_01.mp4'" > concat.txt
echo "file 'scene_02.mp4'" >> concat.txt
# 拼接
ffmpeg -f concat -safe 0 -i concat.txt -c copy output.mp4
```

---

## 三、自动化流水线

### 3.1 核心脚本
| 脚本 | 功能 | 位置 |
|------|------|------|
| `tools/zombie_pipeline.py` | 批量生成流水线 | `D:\ai_projects\ComfyUI\tools\` |
| `tools/add_subtitles.py` | 字幕叠加 | `D:\ai_projects\ComfyUI\tools\` |
| `tools/episodes/episode_pipeline.py` | 分集处理 | `D:\ai_projects\ComfyUI\tools\episodes\` |

### 3.2 处理流程
```
1. 生成视频 (ComfyUI API)
   ↓
2. 移动到SMB共享 (自动监控)
   ↓
3. TTS配音 (Edge TTS)
   ↓
4. 字幕叠加 (FFmpeg)
   ↓
5. 音视频合并 (FFmpeg)
   ↓
6. 分集拼接 (FFmpeg concat)
```

---

## 四、产物清单

### 4.1 模型文件
| 文件 | 大小 | 位置 |
|------|------|------|
| umt5xxl_encoder.safetensors | 10.59GB | models/clip/ |
| Wan2.1_VAE.pth | ~300MB | models/vae/ |
| Wan2.1 T2V 1.3B | ~5GB | models/diffusion_models/ |

### 4.2 工作流文件
| 文件 | 说明 |
|------|------|
| workflows/wan21_test.json | 测试工作流 |
| workflows/zombie_girlfriend_script.json | 剧本和台词 |

### 4.3 输出文件
| 类型 | 数量 | 位置 |
|------|------|------|
| 原始视频 | 20个 | `\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸\` |
| TTS配音 | 20个 | `\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸_成品\tts\` |
| 成品视频 | 4集 | `\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸_成品\` |

### 4.4 测试产物
| 文件 | 规格 | 说明 |
|------|------|------|
| wan21_test_00001.mp4 | 832×480, 41帧 | 首次测试 |
| wan21_test_improved_00001.mp4 | 832×480, 41帧 | 优化测试 |

---

## 五、关键问题与解决

### 5.1 CLIP维度不匹配
- **问题**: 768维 vs 4096维
- **原因**: 键名不兼容 + tokenizer缺失
- **解决**: 键名映射 + 嵌入tokenizer

### 5.2 VRAM不足
- **问题**: 16GB显存无法生成长视频
- **解决**: 限制为41帧（约2.5秒），分段生成后拼接

### 5.3 人物一致性
- **问题**: 不同场景人物差异大
- **解决**: 统一人物描述提示词，固定种子参数

---

## 六、后续优化方向

1. **增加视频长度**: 尝试更高效的显存管理
2. **提升分辨率**: 考虑超分模型后处理
3. **方言优化**: 接入更专业的方言TTS
4. **自动剪辑**: 智能场景过渡和转场效果

---

*文档生成时间: 2026-06-23*
*项目状态: 开发中*
