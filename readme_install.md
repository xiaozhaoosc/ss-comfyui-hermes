# ComfyUI 安装记录

> **日期**: 2026-05-31
> **硬件**: RTX 4060 Ti 16GB | 32GB RAM | CUDA 13.1 | Driver 591.86
> **目标**: 写实风格人脸/服装处理，全免费本地部署
> **工作区**: `D:\ai_projects\ComfyUI`

---

## 一、环境准备

### 1.1 ComfyUI 源码
```bash
cd D:\ai_projects
git clone https://github.com/comfyanonymous/ComfyUI.git
```
- 路径: `D:\ai_projects\ComfyUI`
- 状态: ✅ 完成

### 1.2 Python 虚拟环境
```bash
cd D:\ai_projects\ComfyUI
C:\Users\kenzhao\anaconda3\python.exe -m venv venv
```
- Python 版本: 3.12.7 (来自 Anaconda)
- 路径: `D:\ai_projects\ComfyUI\venv`
- 状态: ✅ 完成

### 1.3 PyTorch CUDA 安装

**⚠️ 问题**: PyTorch 官方 CDN 下载速度极慢（~50KB/s），2.5GB 文件需 14+ 小时

**解决方案**: 使用阿里云镜像（~1.5MB/s，30 分钟完成）

```bash
# 阿里云镜像下载 wheel 文件
curl -L -o D:\OLLAMA_MODELS\cache\torch_cu124.whl \
  "https://mirrors.aliyun.com/pytorch-wheels/cu124/torch-2.6.0+cu124-cp312-cp312-win_amd64.whl"

curl -L -o D:\OLLAMA_MODELS\cache\torchvision_cu124.whl \
  "https://mirrors.aliyun.com/pytorch-wheels/cu124/torchvision-0.21.0+cu124-cp312-cp312-win_amd64.whl"

curl -L -o D:\OLLAMA_MODELS\cache\torchaudio_cu124.whl \
  "https://mirrors.aliyun.com/pytorch-wheels/cu124/torchaudio-2.6.0+cu124-cp312-cp312-win_amd64.whl"

# 本地安装
venv\Scripts\pip.exe install torch_cu124.whl torchvision_cu124.whl torchaudio_cu124.whl

# 验证
venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

- 目标版本: torch 2.6.0+cu124, torchvision 0.21.0+cu124, torchaudio 2.6.0+cu124
- 镜像源: https://mirrors.aliyun.com/pytorch-wheels/cu124/
- 下载速度对比:
  - PyTorch 官方 CDN: ~50KB/s ❌
  - 清华源: ~25B/s ❌
  - **阿里云镜像: ~1.5MB/s ✅**
- 状态: ✅ 完成（约 25 分钟）

**遇到的坑**:
1. `pip install torch --index-url https://download.pytorch.org/whl/cu131` 失败 — CUDA 13.1 还没有 PyTorch wheel
2. `pip install torch --index-url https://download.pytorch.org/whl/cu124` 通过 pip 直接下载极慢 — pip 没有进度条，容易以为卡死
3. curl 下载 wheel 后 pip 安装报 `Invalid wheel filename (wrong number of parts)` — 因为文件名被简化为 `torch_cu124.whl`，必须用规范名 `torch-2.6.0+cu124-cp312-cp312-win_amd64.whl`
4. pip 本地安装 wheel 时仍需下载依赖，PyPI SSL 报错 — 加 `-i https://mirrors.aliyun.com/pypi/simple/` 解决
5. 最终方案: curl 从阿里云下载 wheel → 重命名为规范名 → pip 本地安装 + 阿里云 PyPI 镜像装依赖

**验证结果**:
```
torch: 2.6.0+cu124
CUDA compiled: 12.4
CUDA available: True
Device: NVIDIA GeForce RTX 4060 Ti
VRAM: 16.0 GB
cuDNN: 90100
```

---

## 二、模型共享架构

### 2.1 设计思路
- **所有 AI 模型**统一存放在 `D:\OLLAMA_MODELS\`（与 vLLM/llama.cpp 共享）
- **ComfyUI 工作区**在 `D:\ai_projects\ComfyUI`
- 通过 **Windows Junction**（目录联接）让 ComfyUI 能访问共享模型

### 2.2 Junction 创建
```powershell
# 模型目录 → D:\OLLAMA_MODELS\models
New-Item -ItemType Junction -Path D:\ai_projects\ComfyUI\models -Target D:\OLLAMA_MODELS\models -Force

# 缓存目录 → D:\OLLAMA_MODELS\cache
New-Item -ItemType Junction -Path D:\ai_projects\ComfyUI\.cache -Target D:\OLLAMA_MODELS\cache -Force

# 输出目录 → D:\OLLAMA_MODELS\output
New-Item -ItemType Junction -Path D:\ai_projects\ComfyUI\output -Target D:\OLLAMA_MODELS\output -Force
```

**⚠️ 注意**: Junction 不是 Symlink，不需要管理员权限。但 `Remove-Item` 删除时可能报错，用 `cmd /c rmdir` 或 `os.rmdir()` 清理。

### 2.3 extra_model_paths.yaml
```yaml
# 除了 junction，还通过 extra_model_paths.yaml 配置模型路径
# 文件位置: D:\ai_projects\ComfyUI\extra_model_paths.yaml
```

### 2.4 环境变量（启动脚本中设置）
```bat
set HF_HOME=D:\OLLAMA_MODELS\cache\huggingface
set HUGGINGFACE_HUB_CACHE=D:\OLLAMA_MODELS\cache\huggingface\hub
set TORCH_HOME=D:\OLLAMA_MODELS\cache\torch
set TRANSFORMERS_CACHE=D:\OLLAMA_MODELS\cache\transformers
set PIP_CACHE_DIR=D:\OLLAMA_MODELS\cache\pip
```

---

## 三、ComfyUI-Manager 安装

### 3.1 方法: zip 下载（git clone 超时）

```bash
# 下载 zip
curl -sL -o manager.zip "https://ghfast.top/https://github.com/ltdrdata/ComfyUI-Manager/archive/refs/heads/main.zip"

# 解压到 custom_nodes
unzip -o manager.zip -d D:\ai_projects\ComfyUI\custom_nodes\
mv ComfyUI-Manager-main ComfyUI-Manager
```

**⚠️ 问题**:
1. `git clone` 直接超时（GitHub 访问慢）
2. `ghfast.top` 镜像对某些仓库返回 404
3. 解决方案: 用 `ghfast.top` 镜像下载 zip，解压后重命名

- 状态: ✅ 完成

---

## 四、核心节点安装

全部通过 zip 下载（绕过 git 超时问题）

| 节点 | 仓库 | 镜像 | 状态 |
|------|------|------|------|
| ComfyUI-ReActor-Nodes | Gourieff/ComfyUI-ReActor | ghfast.top ✅ | ✅ |
| ComfyUI-Impact-Pack | ltdrdata/ComfyUI-Impact-Pack | master 分支 ✅ | ✅ |
| ComfyUI_essentials | cubiq/ComfyUI_essentials | ghfast.top ✅ | ✅ |
| WAS-Node-Suite | WASasquatch/WAS-node-suite-comfyui | ghfast.top ✅ | ✅ |

### 4.1 ReActor（换脸核心）
```bash
curl -sL -o reactor.zip "https://ghfast.top/https://github.com/Gourieff/ComfyUI-ReActor/archive/refs/heads/main.zip"
unzip reactor.zip -d custom_nodes/
mv ComfyUI-ReActor-main ComfyUI-ReActor-Nodes
```

**⚠️ 问题**: 仓库名是 `ComfyUI-ReActor` 不是 `comfyui-reactor-node`（GitHub 搜索结果误导）

### 4.2 Impact Pack（FaceDetailer）
```bash
curl -sL -o impact.zip "https://ghfast.top/https://github.com/ltdrdata/ComfyUI-Impact-Pack/archive/refs/heads/master.zip"
unzip impact.zip -d custom_nodes/
mv ComfyUI-Impact-Pack-Main ComfyUI-Impact-Pack
```

**⚠️ 问题**: 默认分支是 `master` 不是 `main`

### 4.3 Essentials
```bash
curl -sL -o essentials.zip "https://ghfast.top/https://github.com/cubiq/ComfyUI_essentials/archive/refs/heads/main.zip"
unzip essentials.zip -d custom_nodes/
mv ComfyUI_essentials-main ComfyUI_essentials
```

### 4.4 WAS Node Suite
```bash
curl -sL -o was.zip "https://ghfast.top/https://github.com/WASasquatch/WAS-node-suite-comfyui/archive/refs/heads/main.zip"
unzip was.zip -d custom_nodes/
mv was-node-suite-comfyui-main WAS-Node-Suite-ComfyUI
```

---

## 五、CLI 工具安装

### 5.1 官方 Python comfy-cli (推荐主力)

```bash
pip install comfy-cli --user

# 复制到 PATH（避免与 Node.js 版冲突）
cp C:\Users\kenzhao\AppData\Roaming\Python\Python312\Scripts\comfycli.exe D:\nodejs\comfycli.exe

# 配置
comfycli --skip-prompt tracking disable
comfycli set-default D:\ai_projects\ComfyUI
```

- 命令名: `comfycli`（区别于 Node.js 版 `comfy`）
- 版本: 1.10.3
- 配置路径: `~/.comfy/`
- 状态: ✅ 完成

### 5.2 @optima-chat/comfy-cli (Node.js, Claude Code 插件)

- 命令名: `comfy`
- 版本: 0.9.10
- 已有安装，配置更新指向本地: `http://127.0.0.1:8188`
- 输出目录: `D:\OLLAMA_MODELS\output`
- 配置路径: `C:\Users\kenzhao\AppData\Roaming\comfy-cli-nodejs\Config\config.json`
- 状态: ✅ 完成

---

## 六、Hermes Agent Skills

### 6.1 Builtin: comfyui
- 路径: `~/.hermes/skills/creative/comfyui/`
- 功能: 工作流执行、参数注入、依赖检查、批量生成
- 脚本: `run_workflow.py`, `check_deps.py`, `extract_schema.py` 等
- 状态: ✅ 内置

### 6.2 comfyui-workflow-master
- 来源: `D:\OLLAMA_MODELS\comfyui-workflow-skill\`
- 路径: `~/.hermes/skills/comfyui-workflow-master/`
- 功能: 自然语言→工作流 JSON 生成
- 需手动添加 YAML frontmatter
- 状态: ✅ 安装

### 6.3 superpowers (obra/superpowers)
- 来源: `git@github.com:obra/superpowers.git`
- 路径: `~/.hermes/skills/`
- 14 个 skills，9 个新安装，4 个与内置重名（被内置版本覆盖）
- 安装方式: 通过 GitHub API 批量下载 SKILL.md + 支持文件
- 状态: ✅ 安装

---

## 七、启动配置

### 7.1 启动脚本
文件: `D:\ai_projects\ComfyUI\start_comfyui.bat`

```bat
@echo off
set HF_HOME=D:\OLLAMA_MODELS\cache\huggingface
set HUGGINGFACE_HUB_CACHE=D:\OLLAMA_MODELS\cache\huggingface\hub
set TORCH_HOME=D:\OLLAMA_MODELS\cache\torch
set TRANSFORMERS_CACHE=D:\OLLAMA_MODELS\cache\transformers
set PIP_CACHE_DIR=D:\OLLAMA_MODELS\cache\pip

cd /d D:\ai_projects\ComfyUI
venv\Scripts\python.exe main.py --highvram --listen 0.0.0.0 --port 8188
```

### 7.2 启动参数说明
| 参数 | 作用 | 适用场景 |
|------|------|----------|
| `--highvram` | 模型常驻 GPU | 16GB 显存 |
| `--fp16-unet` | 半精度推理 | 节省显存 |
| `--listen 0.0.0.0` | 局域网访问 | 远程使用 |
| `--port 8188` | 默认端口 | 与 CLI 一致 |

> ⚠️ `--xformers` 已不再是启动参数（ComfyUI 0.22.0 自动处理），加上会报 `unknown argument`。

---

## 八、LLM 模型架构（参考）

用户实际使用的是 **llama.cpp Docker**（不是 Ollama），通过 docker-compose 管理：

| 模型 | 容器名 | 端口 | 状态 |
|------|--------|------|------|
| Gemma 4 26B (Q3_K_M) | cpp-gemma4-26b | 8003 | 可用 |
| Qwen3.5-9B (Q8_0) | cpp-qwen3.5-9b2 | 8005 | 可用 |
| Qwen3.5-27B | - | - | ❌ 太重，不用 |
| Qwen3.6-35B | - | - | ❌ 太重，不用 |

- Docker 镜像: `ghcr.io/ggml-org/llama.cpp:server-cuda`
- 模型存储: `D:\OLLAMA_MODELS\<model_name>\`
- WSL 路径: `/mnt/d/OLLAMA_MODELS/<model_name>/`

---

## 九、待完成事项

### 9.1 AI 模型下载（必需）
```bash
# SDXL Base (6.5GB) - 主力生图
comfycli model download \
  --url "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors" \
  --relative-path models/checkpoints
```
- SDXL Base 1.0 (6.5GB): ✅ 已下载完成
- RealESRGAN x4plus (64MB): ✅ 已下载
- GFPGANv1.4 (333MB): ✅ 已下载
- SAM vit_b (358MB): ✅ 已下载
- InsightFace buffalo_l (300MB): 待下载（ReActor 首次使用可自动下载）

### 9.2 节点依赖安装
# 或首次运行时自动下载到 ~/.insightface/

# GFPGANv1.4 (340MB) - 面部修复
# 下载到: models/facerestore_models/GFPGANv1.4.pth

# RealESRGAN x4plus (64MB) - 4K 超分
# 下载到: models/upscale_models/RealESRGAN_x4plus.pth
```

### 9.2 节点依赖安装
各节点 Python 依赖已安装完成：
```bash
PIP="D:/ai_projects/ComfyUI/venv/Scripts/pip.exe"
MIRROR="-i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com"

cd D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-ReActor-Nodes
$PIP install -r requirements.txt $MIRROR

cd D:\ai_projects\ComfyUI\custom_nodes\ComfyUI-Impact-Pack
$PIP install -r requirements.txt $MIRROR

cd D:\ai_projects\ComfyUI\custom_nodes\WAS-Node-Suite-ComfyUI
$PIP install -r requirements.txt $MIRROR

cd D:\ai_projects\ComfyUI\custom_nodes\ComfyUI_essentials
$PIP install -r requirements.txt $MIRROR
```
- 状态: ✅ 全部完成
- Impact Pack 安装了 SAM-2、scikit-image 等
- essentials 安装了 rembg、timm、numba 等
- WAS 安装了 scikit-learn、fairscale、gitpython 等

### 9.3 测试验证
- [x] 启动 ComfyUI 无报错 ✅ 2026-05-31
- [x] Manager 显示所有节点已加载 ✅ 1265 节点
- [x] SDXL 文生图验证 CUDA 正常 ✅ 1024x1024, ~30s
- [ ] 测试 ReActor 换脸工作流
- [ ] 测试 FaceDetailer 面部增强

### 9.4 首次启动修复记录

| 问题 | 原因 | 解决 |
|------|------|------|
| `--xformers` unknown argument | ComfyUI 0.22.0 不再需要此参数 | 去掉 `--xformers` |
| ReActor 缺 onnxruntime | 未预装 onnxruntime-gpu | `pip install onnxruntime-gpu` |
| SDXL 生图 HTTP 500 | skill 内置工作流 JSON 含 `_comment` 字段，ComfyUI 当节点解析 | 去掉 `_comment` 字段 |

### 9.5 首次生图验证
```
模型: SDXL Base 1.0
分辨率: 1024x1024
步数: 25, CFG: 7.0
耗时: ~30 秒
输出: D:\OLLAMA_MODELS\output\sdxl_00001__1.png
结果: ✅ 成功，写实风格，细节优秀
```

---

## 十、目录结构总览

```
D:\ai_projects\
├── ComfyUI\                    ← 主工作区
│   ├── venv\                   ← Python 3.12 + CUDA PyTorch
│   ├── custom_nodes\
│   │   ├── ComfyUI-Manager\
│   │   ├── ComfyUI-ReActor-Nodes\    ← 换脸
│   │   ├── ComfyUI-Impact-Pack\      ← FaceDetailer
│   │   ├── ComfyUI_essentials\       ← 基础工具
│   │   └── WAS-Node-Suite-ComfyUI\   ← 综合处理
│   ├── models ──→ [Junction] ──→ D:\OLLAMA_MODELS\models\
│   ├── .cache ──→ [Junction] ──→ D:\OLLAMA_MODELS\cache\
│   ├── output ──→ [Junction] ──→ D:\OLLAMA_MODELS\output\
│   ├── extra_model_paths.yaml
│   ├── start_comfyui.bat
│   └── main.py
│
D:\OLLAMA_MODELS\               ← 共享存储
├── models\                     ← 所有 AI 模型（junction 源）
├── cache\                      ← HF/torch/pip 缓存
├── output\                     ← ComfyUI 输出
├── gemma4\                     ← llama.cpp Docker 模型
├── qwen3.5-gguf\              ← llama.cpp Docker 模型
└── ...
```

---

## 十一、经验总结

1. **网络问题**: 国内访问 GitHub/PyTorch CDN 很慢，优先用镜像
   - GitHub zip: `ghfast.top` 代理
   - PyTorch wheels: `mirrors.aliyun.com`
   - git clone: 基本不可用，改用 zip 下载

2. **Junction vs Symlink**: Windows Junction 不需要管理员权限，行为类似 Linux 的 symlink，适合模型共享

3. **CLI 冲突**: Node.js `comfy` 和 Python `comfycli` 共存，需要区分命令名

4. **PyTorch CUDA 版本**: CUDA 13.1 driver 向下兼容 CUDA 12.4 runtime，用 cu124 wheel 即可

5. **仓库名核实**: GitHub 搜索结果不一定准确，用 API 确认 `default_branch` 和仓库全名

6. **启动参数变化**: ComfyUI 0.22.0 不再需要 `--xformers`（自动处理），加上会报 unknown argument

7. **工作流 JSON 格式**: API 格式中不能有非节点字段（如 `_comment`），ComfyUI 会尝试解析导致 500 错误

8. **onnxruntime-gpu**: ReActor 换脸节点依赖 onnxruntime，必须手动安装 `pip install onnxruntime-gpu`

9. **首次生图耗时**: SDXL 1024x1024 25步约 30 秒（RTX 4060 Ti 16GB, --highvram）
