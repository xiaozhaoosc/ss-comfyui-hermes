# 会话总结：LoRA 训练器选型与 ComfyUI-FluxTrainer 集成（2026-10-01）

## 一、会话目标与背景
- 用户（16GB 卡、ComfyUI 重度使用者）在评估本地 LoRA 训练方案，之前已用 **ai-toolkit** 训练过 FLUX LoRA（`ohwx woman`，1200 步 1h47m）。
- 本次会话：① 对比新下载的 Lora-scripts 与上次用的训练器；② 盘点开源训练器；③ 在 ComfyUI 中集成 **ComfyUI-FluxTrainer**（kijai）。

## 二、Lora-scripts v1.10.0 与 ai-toolkit 的区别
| 维度 | ai-toolkit（上次） | Lora-scripts v1.10.0（本次下载） |
|---|---|---|
| 框架 | ostris/ai-toolkit | kohya sd-scripts 封装（秋葉 WebUI） |
| 目标模型 | FLUX 系及新模型（FLUX.2/Qwen/Wan） | SD1.5 / SD2.1 / SDXL（**不支持 FLUX 底座**） |
| 界面 | 命令行 + 看门狗脚本 | 本地 Web UI（Gradio，双击 `A启动脚本.bat` 即用） |
| 显存 | 16GB 需大量调优（量化/卸载/T5 等） | SD 系小模型，2~6GB 即可，16GB 很轻松 |
| 位置 | `D:\BaiduNetdiskDownload\lora训练器\lora-scripts-v1.10.0\`（2.7GB 压缩包，内置 python/git，免安装） |

**已更新至最新**：目录本身是官方仓库完整 clone，通过官方国内加速（`assets\gitconfig-cn` 把 GitHub 改写为 jihulab 镜像）完成 `pull`，本地 main `30659f3`（v1.10.0 标签）→ **`ec505d8`**（最新官方提交，含 flux-lora/sd3-lora/lumina 等新 schema，161 文件 +21320 行）。子模块 frontend、dataset-tag-editor 已同步。
- 默认配置 `config\default.toml`：SD1.5（`model.ckpt`）、dim32/alpha16、AdamW8bit、512px、fp16。

## 三、开源 LoRA 训练器清单（2026-10 快照）
- **核心引擎**：`kohya-ss/sd-scripts`（全系标准，SD/SDXL/FLUX.1，无 FLUX.2）；`ostris/ai-toolkit`（新模型首选，FLUX.2/Qwen/Z-Image/Wan，本地 UI :8675，断点续训）。
- **GUI 封装**：Lora-scripts（秋葉，自带打标/TensorBoard）、bmaltais/kohya_ss（Gradio，教程多）、Nerogar/OneTrainer（统一 UI）、cubiq/FluxGym（FLUX 低显存最傻瓜）、kijai/ComfyUI-FluxTrainer（ComfyUI 节点版）。
- **其它**：SimpleTuner（调参最细）、x-flux（FLUX 轻量分叉）。
- **选型建议**：FLUX 续练 → ai-toolkit 或 ComfyUI-FluxTrainer；SD/SDXL 入门 → 现成的 Lora-scripts；FLUX 不想碰命令行 → FluxGym。

## 四、ComfyUI-FluxTrainer 集成进展（进行中，等待用户下载 ZIP）
### 已完成
- 定位目标目录 `d:\ai_projects\ComfyUI\custom_nodes\ComfyUI-FluxTrainer`。
- 确认 ComfyUI 已有 venv：`d:\ai_projects\ComfyUI\venv\Scripts\python.exe`；已装 `ComfyUI-KJNodes`（kijai 系列，兼容风格一致）。
- 系统 PATH 无 git，使用内置 git：`D:\BaiduNetdiskDownload\lora训练器\lora-scripts-v1.10.0\git\cmd\git.exe`。

### 遇到的阻塞（网络）
- **GitHub 直连及约 30 个代理镜像全部不通**（ghproxy 系、ghfast、kkgithub、moeyy、gitclone、gitcode mirrors 等）。
- 能连通：gitee、gitcode.com（主站）、jihulab、清华源、pypi 清华镜像、百度网盘；但这些站上**没有 kijai/ComfyUI-FluxTrainer 的镜像/fork**（与 lora-scripts 有官方搬运不同）。
- 已清理 jihulab 克隆产生的空目录。

### 已与用户商定的方案（用户选择）
用户**手动从浏览器下载 ZIP**：`https://github.com/kijai/ComfyUI-FluxTrainer/archive/refs/heads/main.zip`
（若浏览器也不通，可试 `https://ghproxy.net/https://github.com/.../main.zip`）

### 下一步（ZIP 到位后执行）
1. 解压到 `d:\ai_projects\ComfyUI\custom_nodes\ComfyUI-FluxTrainer`（解压后内层目录名通常是 `ComfyUI-FluxTrainer-main`，需确保 custom_nodes 下目录名正确）。
2. 校验 `nodes.py` / `requirements.txt` / `example_workflows` 齐全。
3. 用 venv 装依赖：`d:\ai_projects\ComfyUI\venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`（依赖走清华源）。
4. 验证节点加载：重启 ComfyUI 后确认 `FluxTrainer` 节点组出现；如有报错按 kijai 依赖要求补装。
5. 训练依赖：该节点基于 kohya 脚本，首次训练会下载 flux 训练脚本/模型，需 hf-mirror 或代理，届时再处理。

## 五、关键路径速查
- Lora-scripts：`D:\BaiduNetdiskDownload\lora训练器\lora-scripts-v1.10.0\`（启动 `A启动脚本.bat`；更新 `A强制更新-国内加速.bat`）
- 内置 git：`...\git\cmd\git.exe`
- ComfyUI venv：`d:\ai_projects\ComfyUI\venv\Scripts\python.exe`
- 目标插件目录：`d:\ai_projects\ComfyUI\custom_nodes\ComfyUI-FluxTrainer`

## 六、待办
- [ ] 用户下载 `ComfyUI-FluxTrainer-main.zip` 并告知路径
- [ ] 解压、校验、装依赖、验证节点加载
- [ ] （可选）归档本知识到 obsidian `研究档案\ComfyUI\`
