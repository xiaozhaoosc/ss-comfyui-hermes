# Superpowers 安装指南

## 项目信息

已成功克隆 Superpowers 仓库到: `D:\OLLAMA_MODELS\superpowers`

## 环境变量配置 ✓

已配置以下用户环境变量（需要重启终端生效）：
- `OLLAMA_MODELS` = `D:\OLLAMA_MODELS\models`
- `OLLAMA_CACHE` = `D:\OLLAMA_MODELS\cache`

## 全局 Skills 安装

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

## 包含的 Skills

Superpowers 包含 13 个开发技能：

1. **brainstorming** - 头脑风暴和设计
2. **test-driven-development** - TDD 红绿重构
3. **systematic-debugging** - 系统化调试
4. **subagent-driven-development** - 子代理开发
5. **writing-plans** - 编写计划
6. **executing-plans** - 执行计划
7. **requesting-code-review** - 代码审查
8. **receiving-code-review** - 审查反馈
9. **finishing-a-development-branch** - 完成分支
10. **dispatching-parallel-agents** - 并行代理
11. **using-git-worktrees** - Git Worktrees
12. **verification-before-completion** - 完成验证
13. **writing-skills** - 编写 Skills

## 重要路径

- **Skills 目录**: `D:\OLLAMA_MODELS\superpowers\skills`
- **模型存储**: `D:\OLLAMA_MODELS\models`
- **缓存目录**: `D:\OLLAMA_MODELS\cache`
- **全局 Skills 目标**: `c:\Users\kenzhao\.trae-cn\global\skills\superpowers`
