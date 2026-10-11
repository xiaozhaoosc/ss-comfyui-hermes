# 批量视频换脸 + AI水印 + 语录叠加

## 概述
一键完成：ComfyUI批量换脸 → AI生成水印 → 底部语录叠加 → 语录重命名

## 文件结构
```
D:\ai_projects\ComfyUI\
├── tools\
│   ├── batch_faceswap_overlay.py    # 一键启动脚本（换脸+水印+语录+重命名）
│   ├── add_text_overlay.py          # 单独后处理脚本（水印+语录+重命名）
│   └── quotes.json                  # 语录库（52条：国学/鸡汤/热梗）
├── workflows\v1\
│   ├── batch_faceswap_video_api.json  # ComfyUI API工作流（视频换脸）
│   └── faceswap_video_reactor.json    # ComfyUI GUI工作流
```

## 一键启动（推荐）

```bash
# 完整流程：换脸 + 水印 + 语录 + 重命名
python D:\ai_projects\ComfyUI\tools\batch_faceswap_overlay.py \
  --input "D:\ai_projects\ComfyUI\input\Ms.琪大宝er" \
  --face "D:\ai_projects\ComfyUI\input\todo\face\ken4.png" \
  --output "D:\ai_projects\ComfyUI\output\final"

# 跳过换脸（已有结果时），只做水印+语录+重命名
python D:\ai_projects\ComfyUI\tools\batch_faceswap_overlay.py \
  --input "D:\ai_projects\ComfyUI\output\aken4" \
  --face "xxx" \
  --output "D:\ai_projects\ComfyUI\output\final" \
  --skip-faceswap

# 只用国学类语录
python batch_faceswap_overlay.py --input ... --face ... --output ... --category 国学
```

## 参数说明

| 参数 | 必填 | 说明 |
|------|------|------|
| `--input` | ✅ | 输入视频目录（ComfyUI input 相对路径或绝对路径） |
| `--face` | ✅ | 人脸图片路径 |
| `--output` | ✅ | 最终输出目录 |
| `--skip-faceswap` | ❌ | 跳过换脸步骤 |
| `--category` | ❌ | 语录分类：国学/鸡汤/热梗 |
| `--comfyui-url` | ❌ | ComfyUI API地址（默认 http://127.0.0.1:8188） |

## 工作流程

```
Step 1: ComfyUI 批量换脸
  ├── 扫描 input 目录中的所有 .mp4
  ├── 每个视频提交到 ComfyUI API（ReActorFaceSwap）
  ├── 队列监控（每10秒检查进度）
  └── 等待全部完成

Step 2: FFmpeg 后处理
  ├── 左下角 "AI生成" 水印（前5秒）
  ├── 底部居中语录（半透明黑底白字）
  ├── 语录来源标注（如"— 李白"）
  └── 输出文件以语录文字命名（如"路漫漫其修远兮.mp4"）
```

## 语录库 quotes.json

52条语录，3个分类：
- **国学** (18条): 孔子、老子、李白、杜甫、苏轼等
- **鸡汤** (16条): 生活感悟、励志语录
- **热梗** (18条): 网络流行语、当下热词

扩充语录：直接编辑 `quotes.json`，格式：
```json
{"text": "语录内容", "source": "来源", "category": "分类"}
```

## 单独使用后处理

```bash
# 对已有视频添加水印+语录+重命名
python add_text_overlay.py <输入目录> [输出目录] [--category 国学]
```

## 依赖

- Python 3.10+
- FFmpeg（scoop install ffmpeg 或 conda install ffmpeg）
- ComfyUI + ReActor 插件（换脸步骤）
- VHS (Video Helper Suite) 插件（视频加载/输出）

## 输出示例

```
输出目录/
├── 路漫漫其修远兮，吾将上下而求索.mp4
├── 格局打开.mp4
├── 双向奔赴才有意义.mp4
├── 把期待降低，把依赖变少，你会过得很好.mp4
├── 长风破浪会有时，直挂云帆济沧海.mp4
├── 天生我材必有用，千金散尽还复来.mp4
└── ...（每个视频都有AI水印+底部语录）
```

## 注意事项

1. ComfyUI 需要以 `--highvram` 模式运行以获得最佳性能
2. 视频换脸单个约 5-15 分钟（取决于视频长度和 GPU）
3. FFmpeg 后处理单个约 1-2 分钟
4. 25个视频全流程预计 3-6 小时
