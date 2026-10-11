# ComfyUI 相关工具安装指南

## 项目信息

- **Superpowers 仓库**: `D:\OLLAMA_MODELS\superpowers`
- **ComfyUI Workflow Skill**: `D:\OLLAMA_MODELS\comfyui-workflow-skill`

---

## ComfyUI CLI 工具安装

### 1. comfy-cli (Python 版本) ✓

**状态**: 已安装
- 版本: 1.10.3
- 用途: ComfyUI 安装和管理工具

**命令**:
```bash
# 安装 ComfyUI
comfy install

# 查看帮助
comfy --help
```

### 2. @optima-chat/comfy-cli (Node.js 版本) ✓

**状态**: 已安装
- 版本: 0.9.10
- 用途: LLM 交互专用 CLI 工具，支持 `comfy generate` 等自然语言命令

**命令**:
```bash
# 查看帮助
comfy --help

# 使用示例
comfy generate "一个 FLUX 文生图工作流"
```

### 3. comfyui-workflow-skill ✓

**状态**: 已克隆到本地
- 位置: `D:\OLLAMA_MODELS\comfyui-workflow-skill`
- 包含 34 个工作流模板

**使用方法**:
1. 将项目链接为全局 skill
2. 在 Claude Code 中直接用自然语言描述需求

---

## 环境变量配置 ✓

已配置以下用户环境变量（需要重启终端生效）：
- `OLLAMA_MODELS` = `D:\OLLAMA_MODELS\models`
- `OLLAMA_CACHE` = `D:\OLLAMA_MODELS\cache`

---

## Superpowers 全局 Skills 安装

由于权限限制，需要手动完成以下步骤：

### 步骤 1：创建符号链接（推荐）

在**管理员权限**的 PowerShell 中运行：

```powershell
cmd /c mklink /D "c:\Users\kenzhao\.trae-cn\global\skills\superpowers" "D:\OLLAMA_MODELS\superpowers\skills"
```

### 步骤 2：验证安装

检查符号链接是否创建成功：

```powershell
Get-Item "c:\Users\kenzhao\.trae-cn\global\skills\superpowers"
```

---

## comfyui-workflow-skill 使用方法

### 安装为全局 Skill

```powershell
cmd /c mklink /D "c:\Users\kenzhao\.trae-cn\global\skills\comfyui-workflow" "D:\OLLAMA_MODELS\comfyui-workflow-skill"
```

### 使用示例

在 Claude Code 中直接输入：
```
"帮我生成一个 FLUX 文生图工作流"
"创建一个 Wan 2.2 图生视频工作流"
"生成一个 SDXL 重绘工作流"
```

生成的工作流 JSON 文件可以直接导入 ComfyUI 运行。

---

## 包含的 Skills 和工具

### Superpowers (13 个开发技能)
1. brainstorming - 头脑风暴和设计
2. test-driven-development - TDD 红绿重构
3. systematic-debugging - 系统化调试
4. subagent-driven-development - 子代理开发
5. writing-plans - 编写计划
6. executing-plans - 执行计划
7. requesting-code-review - 代码审查
8. receiving-code-review - 审查反馈
9. finishing-a-development-branch - 完成分支
10. dispatching-parallel-agents - 并行代理
11. using-git-worktrees - Git Worktrees
12. verification-before-completion - 完成验证
13. writing-skills - 编写 Skills

### ComfyUI Workflow Templates (34 个模板)
- SD 1.5 / SDXL / SD3 文生图、图生图
- FLUX 系列
- Wan 2.2 视频生成
- HunyuanVideo 视频
- LTXV / Mochi / Cosmos 视频
- Stable Audio 音频
- Hunyuan3D 3D 生成

---

## 重要路径

| 类型 | 路径 |
|------|------|
| Superpowers | `D:\OLLAMA_MODELS\superpowers` |
| ComfyUI Workflow Skill | `D:\OLLAMA_MODELS\comfyui-workflow-skill` |
| 模型存储 | `D:\OLLAMA_MODELS\models` |
| 缓存目录 | `D:\OLLAMA_MODELS\cache` |
| comfy-cli | Python 包 (pip 安装) |
| @optima-chat/comfy-cli | Node.js 全局包 |
