# 🧟 我的女友是丧尸 — AI短剧自动化生成方案

## 一、项目概述

**目标**：使用 ComfyUI + Wan2.1 T2V 模型，自动化生成一部末日丧尸恋爱题材 AI 短剧，包含：
- 人物一致的东方面孔女主角
- 徐州方言 TTS 配音
- 自动字幕叠加
- 多段视频 FFmpeg 拼接成完整剧集

**硬件环境**：
| 项目 | 配置 |
|------|------|
| GPU | NVIDIA RTX 4060 Ti 16GB |
| CPU | Intel i7-14700F |
| 内存 | 32GB DDR5 |
| 存储 | D盘 1.4TB 可用 |

**软件环境**：
| 组件 | 版本/配置 |
|------|-----------|
| ComfyUI | 最新版，`--lowvram` 模式 |
| Wan2.1 T2V | 14B 主模型 + 1.3B fallback |
| CLIP Encoder | umt5xxl_encoder.safetensors（自转换，4096维） |
| VAE | Wan2.1_VAE.pth |
| FFmpeg | v8.1.1（scoop 安装） |
| TTS | Edge TTS（zh-CN-XiaoyiNeural） |

---

## 二、技术方案架构

```
┌─────────────────────────────────────────────────────┐
│                   整体流水线                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. 剧本生成 ──→ 20个场景 + 台词（徐州方言）          │
│       │                                             │
│       ▼                                             │
│  2. TTS配音 ──→ Edge TTS 逐条生成语音                │
│       │                                             │
│       ▼                                             │
│  3. 视频生成 ──→ ComfyUI Wan2.1 T2V（421帧/段）      │
│       │                                             │
│       ▼                                             │
│  4. 后期处理 ──→ FFmpeg 字幕 + 配音合并               │
│       │                                             │
│       ▼                                             │
│  5. 剧集拼接 ──→ FFmpeg 拼接为完整EP1-EP4            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 三、实现过程详录

### 阶段一：模型准备与部署

#### 问题1：CLIP模型格式不兼容
**现象**：ComfyUI 加载 `models_t5_umt5-xxl-enc-bf16.pth` 报错，维度不匹配（768 vs 4096）

**根因分析**：
- 原始 `.pth` 文件使用自定义 key 命名（如 `encoder.embed_tokens.weight`）
- ComfyUI 期望 HuggingFace 标准命名（如 `shared.weight`, `encoder.block.0.layer.0.SelfAttention.q.weight`）
- 关键的 `spiece_model`（SentencePiece tokenizer）数据缺失

**解决方案**：
```python
# 1. 加载原始权重
state_dict = torch.load("models_t5_umt5-xxl-enc-bf16.pth")

# 2. 构建 key 映射表（自定义名 → HF标准名）
key_mapping = {
    "encoder.embed_tokens.weight": "shared.weight",
    "encoder.block.0.layer.0.SelfAttention.q.weight": "encoder.block.0.layer.0.SelfAttention.q.weight",
    # ... 完整映射约200+条
}

# 3. 读取 SentencePiece tokenizer 二进制数据
with open("spiece.model", "rb") as f:
    spiece_data = f.read()

# 4. 保存为 safetensors（含嵌入tokenizer）
safetensors.torch.save_file(converted_state, output_path)
```

**产物**：`models/clip/umt5xxl_encoder.safetensors`（10.59GB，4096维输出）

#### 问题2：VAE模型路径
**处理**：将 `Wan2.1_VAE.pth` 复制到 `models/vae/` 目录

---

### 阶段二：ComfyUI服务启动

#### 启动命令
```bash
cd D:\ai_projects\ComfyUI
python main.py --lowvram --listen 0.0.0.0 --port 8188
```

#### 低显存模式说明
由于 RTX 4060 Ti 仅 16GB 显存，Wan2.1 14B 模型必须使用 `--lowvram` 模式：
- 模型权重按需加载到 GPU，不常驻显存
- 每次推理时临时加载相关层
- 推理速度较慢但可运行

---

### 阶段三：输出目录与网络共享

#### SMB共享配置
```cmd
net share ComfyUI-Output=D:\ai_projects\ComfyUI\output /GRANT:Everyone,READ
```

**访问地址**：
| 网络 | 地址 | 说明 |
|------|------|------|
| 局域网 | `\\192.168.1.9\ComfyUI-Output` | 速度快 |
| WireGuard | `\\10.8.0.4\ComfyUI-Output` | 速度慢 |

#### 项目目录结构
```
\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸\
├── zgs_00001.mp4          # 原始生成视频
├── zgs_00002.mp4
└── ...

\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸_成品\
├── tts\                   # TTS配音文件
│   ├── scene_01.mp3
│   ├── scene_02.mp3
│   └── ...
├── subtitled\             # 带字幕视频
│   ├── scene_01_sub.mp4
│   └── ...
├── final\                 # 最终成品（配音+字幕）
│   ├── scene_01_final.mp4
│   └── ...
├── episodes\              # 拼接后完整剧集
│   ├── EP1_初遇.mp4
│   ├── EP2_同行.mp4
│   ├── EP3_危机.mp4
│   └── EP4_守候.mp4
└── scripts\
    └── zombie_girlfriend_script.json
```

---

### 阶段四：剧本与台词

#### 剧本结构
20个场景，分为4集：

| 集数 | 场景 | 主题 |
|------|------|------|
| EP1 初遇 | S1-S5 | 废弃超市偶遇丧尸女友，决定同行 |
| EP2 同行 | S6-S10 | 末日路上的甜蜜与危险 |
| EP3 危机 | S11-S15 | 女友身份暴露，团队面临抉择 |
| EP4 守候 | S16-S20 | 感染加剧，男主不离不弃 |

#### 台词示例（徐州方言元素）
```json
{
  "scene_id": 1,
  "title": "废弃超市偶遇",
  "prompt": "...east asian young woman, messy dark hair, torn pink hoodie...",
  "dialogue": "俺滴个娘来！丧尸还怪好看嘞！",
  "subtitle": "我的天！丧尸还挺好看的！"
}
```

#### 人物一致性策略
由于无参考图片，采用**统一描述提示词**保持人物一致：
```
east asian young woman, age 20, messy shoulder-length dark black hair, 
pale skin with subtle grey undertone, wearing torn pink hoodie and 
dark jeans, slightly zombie-like but still beautiful, 
large dark eyes, delicate features
```
所有场景共用同一人物描述，仅改变动作和场景背景。

---

### 阶段五：工作流配置

#### ComfyUI API工作流
通过 HTTP API 提交工作流到 ComfyUI：

```python
import requests, json, uuid

workflow = json.load(open("workflows/zombie_girlfriend.json"))

# 动态修改提示词
workflow["6"]["inputs"]["text"] = prompt_text  # 正向提示词
workflow["3"]["inputs"]["seed"] = random_seed   # 随机种子

# 提交到 ComfyUI
response = requests.post(
    "http://127.0.0.1:8188/prompt",
    json={"prompt": workflow, "client_id": str(uuid.uuid4())}
)
```

#### 生成参数
| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | Wan2.1 T2V 14B | 主力模型 |
| 分辨率 | 832×480 | 16:9 宽屏 |
| 帧数 | 421 | ≈25秒视频（后期FFmpeg拼接） |
| 步数 | 25 | 质量与速度平衡 |
| CFG | 7.0 | 提示词引导强度 |
| 采样器 | uni_pc_bh2 | Wan推荐采样器 |
| 调度器 | beta | Wan推荐调度器 |

---

### 阶段六：TTS配音生成

#### 方案选择
使用 **Edge TTS**（微软免费在线TTS）：
- 支持中文多方言
- 音质好，免费无限制
- Python库 `edge-tts`，一行代码生成

#### 实现
```python
import edge_tts, asyncio

async def generate_tts(text, output_path, voice="zh-CN-XiaoyiNeural"):
    communicate = edge_tts.Communicate(text, voice, rate="-10%", pitch="+0Hz")
    await communicate.save(output_path)

# 批量生成20条配音
for scene in scenes:
    asyncio.run(generate_tts(scene["dialogue"], f"tts/scene_{scene['id']:02d}.mp3"))
```

**结果**：20/20 全部成功，总时长约1分32秒

---

### 阶段七：后期处理流水线

#### 7.1 字幕叠加
```bash
ffmpeg -i input.mp4 -vf \
  "drawtext=fontfile=C:/Windows/Fonts/msyh.ttc:text='字幕内容':\
   fontcolor=white:fontsize=28:borderw=2:bordercolor=black:\
   x=(w-text_w)/2:y=h-60" \
  -c:a copy output_sub.mp4
```

#### 7.2 配音合并
```bash
ffmpeg -i video_sub.mp4 -i audio.mp3 \
  -filter_complex "[0:a]volume=0.3[orig];[1:a]volume=1.0[tts];[orig][tts]amix=inputs=2:duration=first" \
  -c:v copy output_final.mp4
```

#### 7.3 剧集拼接
```bash
# 生成文件列表
echo "file 'scene_01_final.mp4'" > list.txt
echo "file 'scene_02_final.mp4'" >> list.txt
# ...

# 拼接
ffmpeg -f concat -safe 0 -i list.txt -c copy EP1_初遇.mp4
```

---

## 四、最终产物清单

### 已完成产物

| 类别 | 文件 | 数量 | 说明 |
|------|------|------|------|
| 模型 | `umt5xxl_encoder.safetensors` | 1 | 自转换CLIP模型（10.59GB） |
| 工作流 | `workflows/zombie_girlfriend.json` | 1 | ComfyUI完整工作流 |
| 剧本 | `zombie_girlfriend_script.json` | 1 | 20场景+台词+提示词 |
| TTS配音 | `tts/scene_*.mp3` | 20 | 全部20条配音完成 |
| 测试视频 | `zgs_00001.mp4` | 1 | 832×480, 41帧测试 |
| 自动化脚本 | `tools/zombie_pipeline.py` | 1 | 批量生成+后期处理 |
| 字幕脚本 | `tools/add_subtitles.py` | 1 | FFmpeg字幕叠加 |

### 待生成产物

| 类别 | 文件 | 数量 | 说明 |
|------|------|------|------|
| 视频片段 | `zgs_*.mp4` | 20 | 421帧/段，共约8分钟素材 |
| 带字幕视频 | `*_sub.mp4` | 20 | 叠加字幕后的版本 |
| 成品视频 | `*_final.mp4` | 20 | 配音+字幕完整版 |
| 剧集 | `EP1-EP4.mp4` | 4 | 拼接后完整剧集 |

---

## 五、已解决问题汇总

| # | 问题 | 根因 | 解决方案 |
|---|------|------|----------|
| 1 | CLIP模型加载失败 | key命名不兼容 + 缺tokenizer | key映射转换 + 嵌入spiece_model |
| 2 | 显存不足 | 14B模型 + 16GB VRAM | `--lowvram`模式 |
| 3 | 人物不一致 | 无参考图 | 统一人物描述提示词 |
| 4 | 视频太短 | 81帧≈5秒 | 改为421帧≈25秒 |
| 5 | 无字幕 | 未处理 | FFmpeg drawtext自动叠加 |
| 6 | 无配音 | 未处理 | Edge TTS + FFmpeg合并 |

---

## 六、操作指南

### 一键启动
```bash
# 1. 启动 ComfyUI
cd D:\ai_projects\ComfyUI && python main.py --lowvram --listen 0.0.0.0 --port 8188

# 2. 运行批量生成（含TTS+视频+后期）
python projects/我的女友是丧尸/zombie_pipeline.py
```

### 手动单场景生成
```python
# 通过API提交单个场景
import requests, json
wf = json.load(open("workflows/zombie_girlfriend.json"))
wf["6"]["inputs"]["text"] = "your prompt here"
requests.post("http://127.0.0.1:8188/prompt", json={"prompt": wf})
```

---

*文档生成时间：2026-06-24*
*项目路径：D:\ai_projects\ComfyUI\projects\我的女友是丧尸\*
*输出共享：\\192.168.1.9\ComfyUI-Output\wan2\我的女友是丧尸_成品\*
