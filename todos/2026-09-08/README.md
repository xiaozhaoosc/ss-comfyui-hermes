# 2026-09-08 任务成果归档与待办索引

本目录归档了 2026-09-08 针对 **FLUX.1 亚洲人像选型、本地训练环境部署与虚拟数据集生成** 的全部成果文档与行动指南。

---

## 📂 今日产出文档清单

| 文档名称 | 对应功能与核心内容 | 知识库对应位置 |
| :--- | :--- | :--- |
| **[1. flux_myhuman_and_asian_lora_guide.md](file:///d:/ai_projects/ComfyUI/todos/2026-09-08/flux_myhuman_and_asian_lora_guide.md)** | **底模与 LoRA 选型指南**：MYHuman 与 t8star Abliterated-V2 GGUF 选型（RTX 4060 Ti 16GB 推荐 Q6_K）、Civitai 8 款热门亚洲人像 LoRA 评测与下载直链。 | docs/ & .agent/wiki/ |
| **[2. flux_lora_training_guide.md](file:///d:/ai_projects/ComfyUI/todos/2026-09-08/flux_lora_training_guide.md)** | **本机 16GB 炼丹全流程实操指南**：ai-toolkit 安装、显存优化配置、打标规范、触发词策略与 ComfyUI 加载使用方法。 | docs/ & .agent/wiki/ |
| **[3. flux_synthetic_dataset_plan.md](file:///d:/ai_projects/ComfyUI/todos/2026-09-08/flux_synthetic_dataset_plan.md)** | **虚拟训练集生成与提示词库**：用 FLUX 生成 25 张高质量训练集的黄金比例，中英文提示词底层原理解析，25 组即拷即用的专业英文自然语言提示词库。 | docs/ & .agent/wiki/ |

---

## 🛠️ 今日环境搭建成果 (Done)
- [x] **ai-toolkit 本地环境部署**：成功克隆至 d:\ai_projects\ai-toolkit，共用 ComfyUI 虚拟环境。
- [x] **底层依赖深度修复**：
  - 编译并安装 diffusers 最新特性分支（解决 AnimaTextConditioner 缺失问题）；
  - 修复 PyTorch custom op 的 typing 兼容性问题 (convrot_quant.py)；
  - 降级解决 
umpy 2.x 与 scipy 的 ABI 冲突，固定为 1.26.4。
- [x] **空跑测试 (Dry Run)**：使用虚拟单图与 5-step 配置全流程跑通，确认代码与训练逻辑 100% 正常。

---

## 📝 后续行动待办 (TODOs)
1. **生成候选训练图**：
   - 打开 ComfyUI 载入 FLUX 工作流；
   - 使用 lux_synthetic_dataset_plan.md 中的 25 组英文提示词批量生成 50~75 张图片；
   - 人工挑选 20~25 张面容一致、手部无畸形的图片，存放到 d:\ai_projects\ai-toolkit\my_dataset\。
2. **打标签 (Captioning)**：
   - 使用本地 Qwen3 或提示词精简版为每张图片生成同名 .txt 标注，前缀带上触发词（如 ohwx woman）。
3. **正式启动微调**：
   - 在 PowerShell 中设置 $env:HF_ENDPOINT = "https://hf-mirror.com"；
   - 执行 d:\ai_projects\ComfyUI\venv\Scripts\python.exe run.py config\my_flux_lora.yaml 启动炼丹。