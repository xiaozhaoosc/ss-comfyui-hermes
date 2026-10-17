# 🗺️ PROJECT MAP — ComfyUI 项目地图

> **性质**：本项目的主索引与归档地图。新人接手 / 快速定位「某件事的文档在哪、进度到哪」请看这里。
> **建立日期**：2026-10-11
> **本次归档范围**：2026-10-09 ~ 2026-10-11（近 3 天，共 29 份文档）
> **待办清单**：[todos/2026-10-11/README.md](file:///D:/ai_projects/ComfyUI/todos/2026-10-11/README.md) ← 未完成事项全部登记在此

---

## 1. 项目定位

本地 ComfyUI（RTX 4060 Ti 16GB）驱动的**AI 内容生产线**，当前主要有三条业务线：
1. **《北宋杨家将》竖屏短剧**（最成熟，已交付 EP01–04，规划 24 集）
2. **换装 / 换脸视频**（WanAnimate 动作迁移 + IDM-VTON 试穿换装）
3. **动漫短剧本地落地**（角色资产 → 分镜 → 视频链路）
4. **配套能力**：多模型出图质量评测体系、云端 Flow/Veo 生片、下载器与基础设施

---

## 2. 仓库结构与文档约定

| 路径 | 用途 | 约定 |
|---|---|---|
| `docs/` | **正式工作文档**（日报/复盘/评测/交接） | 文件名带 `_YYYY-MM-DD` 后缀 |
| `todos/` | **待办与阶段归档** | 按 `todos/<主题或日期>/` 建目录，内放 `README.md` 作索引（见 [2026-09-08 范式](file:///D:/ai_projects/ComfyUI/todos/2026-09-08/README.md)） |
| `.agent/wiki/` | **长期知识库（Project Brain）** | 见 [📇 知识库索引 _index.md](file:///D:/ai_projects/ComfyUI/.agent/wiki/_index.md)：JOURNAL / CHRONICLE / DEBT_LEADGER / INBOX |
| `tools/` | **脚本工具集** | ⚠️ 会被 ComfyUI 升级重置，写完请立即提交 git；清单见 `tools/SCRIPTS_INVENTORY.md` |
| `output/` | **产物**，按 `output/<YYYY-MM-DD>/` 分日 | 评测类另建 `output/<日期>_wb/` |
| 根目录 | **交接文档散落区**（历史原因） | 本轮起建议新交接文档统一进 `docs/` |
| `models/` | 模型权重 | ATR/IDM-VTON/SAM2 等见第 6 节 |

**长期知识库入口**：`.agent/wiki/`（当前内容偏「工作流分析」，2026-07 建立，尚未覆盖近期业务线，属待补强项）

---

## 3. 主线项目地图

| # | 主线 | 状态 | 核心产物 / 入口 | 进度 |
|---|---|---|---|---|
| A | **《北宋杨家将》短剧** | 🟡 进行中 | [EP01-07 前期交接](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_YANGJIAJIANG_EP01-07_PREPRODUCTION.md) | **7/24 集**；EP01–04 已交付，EP05–07 资产就绪 |
| B | **换装视频（WanAnimate）** | 🟡 进行中 | [831959 B方案批处理](file:///D:/ai_projects/ComfyUI/交接_WanAnimate_831959换装视频_B方案全量批处理_2026-10-11.md) · [仅换装工作流](file:///D:/ai_projects/ComfyUI/仅换装视频工作流_交接文档_2026-10-11.md) | 831959：23/23 渲染完、裁剪 4/23；22 视频干跑通过 |
| C | **动漫短剧本地落地** | 🟡 进行中 | [动漫短剧本地落地](file:///D:/ai_projects/ComfyUI/交接文档_动漫短剧本地落地_2026-10-11.md) | 4 套角色资产就绪；**分镜→视频闭环未跑通** |
| D | **服装提取（garment_extract）** | 🟢 可用 | [视频服装提取流水线](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_视频服装提取流水线.md) | v5 交付 4 视频 ×Top-3（24 PNG） |
| E | **出图质量评测体系** | 🟡 进行中 | [多模型评测交接](file:///D:/ai_projects/ComfyUI/2026-10-10_多模型出图质量评测与Z-Image皮肤LoRA补偿_交接文档.md) | 5 模型/三模式 2K/四模型评测均已落盘；补测收尾中 |
| F | **基础设施与平台工具** | 🟢 可用 | [SQLite 队列](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-10_ComfyUI_SQLite队列与资产持久化.md) · [Flow SOP](file:///D:/ai_projects/ComfyUI/docs/2026-10-10_Google_Flow_标准操作流程与使用指南_SOP.md) · [Hitomi 下载器](file:///D:/ai_projects/ComfyUI/交接文档_Hitomi下载器配置与站点支持_2026-10-11.md) | 队列持久化、Flow SOP v1.0、多站点下载器 |

---

## 4. 近 3 天工作归档（2026-10-09 ~ 2026-10-11）

### 4.1 2026-10-09 — EP03 投产 + 双平台基准 + 动作迁移经验沉淀

| 文档 | 主题 | 状态 |
|---|---|---|
| [DAILY_WORK_SUMMARY_AND_RETROSPECTIVE](file:///D:/ai_projects/ComfyUI/docs/DAILY_WORK_SUMMARY_AND_RETROSPECTIVE_2026-10-09.md) | EP03 资产筹备、双平台实测、纯净生产线重构复盘 | 进行中 |
| [EP03_PRODUCTION_LAUNCH_REPORT](file:///D:/ai_projects/ComfyUI/docs/YANGJIAJIANG_EP03_PRODUCTION_LAUNCH_REPORT_2026-10-09.md) | EP03 正式开机（5 幕 54 镜 214.0s） | 进行中 |
| [BENCHMARK SHOT01 Flow vs Muse](file:///D:/ai_projects/ComfyUI/docs/BENCHMARK_REPORT_EP03_SHOT01_FLOW_VS_MUSE_2026-10-09.md) | 战旗武戏双平台对比 → 定「Muse 主力 + Flow 原画」 | 仅调研 |
| [BENCHMARK ROUND2 Flow vs Muse](file:///D:/ai_projects/ComfyUI/docs/BENCHMARK_REPORT_EP03_ROUND2_FLOW_VS_MUSE_2026-10-09.md) | 朝堂文戏二轮对比（含本地 H3） | 仅调研 |
| [EXPERIENCE_SUMMARY_MOTION_TRANSFER_WAN_ANIMATE](file:///D:/ai_projects/ComfyUI/docs/EXPERIENCE_SUMMARY_MOTION_TRANSFER_WAN_ANIMATE_2026-10-09_1715.md) | **Wan2.2 Animate 动作迁移全链路经验指南**（16GB 黄金参数） | ✅ 完成 |
| [EP03_LOCAL_COMFY_QUALITY_AUDIT_REPORT](file:///D:/ai_projects/ComfyUI/docs/EP03_LOCAL_COMFY_QUALITY_AUDIT_REPORT.md) | EP03 54 镜画质审计，合格率 100% | ✅ 完成 |

### 4.2 2026-10-10 — 多模型评测 + Wan Animate 交付 + Flow SOP + 队列持久化

| 文档 | 主题 | 状态 |
|---|---|---|
| [多模型出图质量评测与 Z-Image 皮肤 LoRA 补偿](file:///D:/ai_projects/ComfyUI/2026-10-10_多模型出图质量评测与Z-Image皮肤LoRA补偿_交接文档.md) | 5 模型横评 + LoRA 补偿 A/B（**结论：皮肤 LoRA 无效**） | 进行中 |
| [PHOTO_REALISM_AND_MULTI_MODEL_UPSCALE](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-10_PHOTO_REALISM_AND_MULTI_MODEL_UPSCALE.md) | 九宫格切片规整 + 1:1 2K 重绘四路线 | ✅ 完成 |
| [ComfyUI_SQLite 队列与资产持久化](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-10_ComfyUI_SQLite队列与资产持久化.md) | 重启防丢：SQLite 队列断点续跑 | ✅ 完成 |
| [WAN_ANIMATE_MOTION_TRANSFER 交接](file:///D:/ai_projects/ComfyUI/docs/HANDOVER_DOCUMENT_WAN_ANIMATE_MOTION_TRANSFER_2026-10-10.md) | 动作克隆单入口 + 1:1 缝合（Production Ready） | ✅ 完成 |
| [HANDOVER_EP03_TO_EP04](file:///D:/ai_projects/ComfyUI/docs/HANDOVER_EP03_TO_EP04_2026-10-10.md) | EP03 交付 → EP04 启程 | ✅ 完成 |
| [Google Flow Veo 自动化生片与一致性技术方案](file:///D:/ai_projects/ComfyUI/docs/2026-10-10_Google_Flow_Veo自动化生片与一致性技术方案.md) | 四大一致性锁 + 100 积分风控 | ✅ 完成 |
| [Google Flow SOP 使用指南](file:///D:/ai_projects/ComfyUI/docs/2026-10-10_Google_Flow_标准操作流程与使用指南_SOP.md) | Flow 工业级生片 SOP v1.0 + 脱敏对照表 | ✅ 完成 |
| [北宋杨家将 云端Flow与本地接力交接](file:///D:/ai_projects/ComfyUI/docs/2026-10-10_北宋杨家将_云端Flow与本地ComfyUI接力交接文档.md) | 前 2 段 1080P/48fps 母带交付 | 进行中 |
| [杨家将第3集 前2段路线A实操复盘](file:///D:/ai_projects/ComfyUI/docs/2026-10-10_杨家将第3集_前2段路线A生成实操与验收复盘报告.md) | 路线 A 实操，查清合规拦截与退款机制 | ✅ 完成 |
| `output/2026-10-10_wb/` [交付报告·三模式2K重绘](file:///D:/ai_projects/ComfyUI/output/2026-10-10_wb/2026-10-10_交付报告_三模式2K重绘量化评测与选型.md) · [四模型评测](file:///D:/ai_projects/ComfyUI/output/2026-10-10_wb/2026-10-10_四模型出图质量综合评测.md) · [Qwen21补测](file:///D:/ai_projects/ComfyUI/output/2026-10-10_wb/2026-10-10_Qwen21补测与LoRA补偿实验_提交说明.md) · [技能精简台账](file:///D:/ai_projects/ComfyUI/output/2026-10-10_wb/2026-10-10_技能精简与权重补齐台账.md) · [技能安全审计](file:///D:/ai_projects/ComfyUI/output/2026-10-10_wb/2026-10-10_技能装载安全审计报告.md) · [出图脚本接入](file:///D:/ai_projects/ComfyUI/output/2026-10-10_wb/2026-10-10_出图脚本体系接入说明.md) | 评测与治理六件套 | 多数完成 |

### 4.3 2026-10-11 — 角色资产链路 / 换装批处理 / 服装提取（今日）

| 文档 | 主题 | 状态 |
|---|---|---|
| [动漫短剧本地落地](file:///D:/ai_projects/ComfyUI/交接文档_动漫短剧本地落地_2026-10-11.md) | 角色资产链路打通（4 套资产表）+ ComfyUI v0.39.1 迁移 | 进行中 |
| [Hitomi 下载器配置与站点支持](file:///D:/ai_projects/ComfyUI/交接文档_Hitomi下载器配置与站点支持_2026-10-11.md) | IG cookie 修复、多站点支持验证、cookie 模板套件 | 进行中 |
| [仅换装视频工作流](file:///D:/ai_projects/ComfyUI/仅换装视频工作流_交接文档_2026-10-11.md) | 三段式「换衣不换脸」链路 | 进行中 |
| [WanAnimate 831959 B方案批处理](file:///D:/ai_projects/ComfyUI/交接_WanAnimate_831959换装视频_B方案全量批处理_2026-10-11.md) | 23/23 渲染完成，片头裁剪 4/23 | 裁剪进行中 |
| [杨家将前四集切片对比与EP04剧情修复](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_杨家将前四集镜头切片对比与EP04剧情一致性修复.md) | EP04 修复 4 处，评分 9.8 | ✅ 完成 |
| [YANGJIAJIANG EP01-07 前期](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_YANGJIAJIANG_EP01-07_PREPRODUCTION.md) | EP01/05/06/07 新建，进度 7/24 集 | 进行中 |
| **[视频服装提取流水线](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_视频服装提取流水线.md)** | **本文档新增**：视频→纯净服装图 v5 流水线 | 🟢 可用（有阻塞） |

---

## 5. 关键节点与结论（避免重复踩坑）

- **服装分割**：不要用 BiRefNet / SAM2 点提示做主服装分割（会分出整个人 / 漏检透视装）；改用 **ATR 人体解析**（`parsing_atr.onnx`）直出服装类别掩码 + SAM2 精修。详见 [服装提取 spec](file:///D:/ai_projects/ComfyUI/tools/garment_extract/spec.md)
- **云平台策略**：视频端用 **Muse.ai 主力**，**Flow 出概念原画**，音频用本地 **Edge-TTS**（`zh-CN-YunjianNeural`）
- **Flow 风控**：每日 100 积分硬上限，账本 `flow_credit_ledger.json`；敏感人物需去名化
- **Wan Animate 16GB 黄金参数**：480×832 / Length=49 / 4 步 / CFG 1.0
- **本地 API 调用**：必须绕代理（`ProxyHandler({})`）；健康检查用 `/queue` 而非 `/system_stats`
- **解释器分工**：`D:\ai_projects\ComfyUI\venv`（本地推理）｜`anaconda3`（tools/CDP 脚本）｜`.workbuddy/envs/default`（ig_download.py）
- **`tools/` 易失**：ComfyUI 升级会重置，备份 commit `4d7c00747`，恢复 `git checkout <commit> -- tools/<路径>`

---

## 6. 关键模型与资产索引

| 资产 | 路径 / 标识 | 用途 |
|---|---|---|
| ATR 人体解析 | `models/IDM-VTON/humanparsing/parsing_atr.onnx` | 服装类别掩码（服装提取） |
| SAM2 | `models/sam2/sam2_hiera_base_plus.safetensors` | 掩码边缘精修 |
| IDM-VTON | `models/IDM-VTON/`（约 27GB / 24 文件） | 试穿换装 |
| Z-Image | 三件套 19.26GB | 出图（构图第一，皮肤偏磨皮） |
| Counterfeit-V3.0 | `Counterfeit-V3.0_fp16`（4.24GB） | 动漫短剧底模 |
| Qwen-Image 2.1 | Q4_K_M GGUF，`CLIPLoader type=qwen_image` | 2K 重绘（清晰度第一，560s/张） |
| 杨家将资产 | `output/2026-10-11/`、`input/` | 54 镜/集 · 6 组九宫格 · 214.0s/集 |

---

## 7. 横切风险与阻塞（⚠️ 接手持手必看）

| 优先级 | 阻塞 | 影响面 | 处理 |
|---|---|---|---|
| 🟢 已定位 | ~~ComfyUI 服务器 DOWN~~ → **根因＝`comfy_aimdo` 版本错配** | 所有需服务器出图/出视频的任务 | venv 为 0.5.6（含 `storage.py`）✅ ／ anaconda 为 0.4.11（**缺**）❌。**统一用 `start_comfyui_lowvram.bat`（venv）启动**；若必须用 anaconda 则 `pip install -U "comfy_aimdo>=0.5.6"`。详见 [todos §A](file:///D:/ai_projects/ComfyUI/todos/2026-10-11/README.md) |
| 🔴 P0 | **飞书 App Secret 曾明文入库** | 安全 | 去飞书后台**轮换 App Secret**，旧密钥视为已泄露。另：Agent 终端进程命令行中亦出现明文 Lark 用户 token，建议一并轮换 |
| 🟢 已修复 | ~~换装流水线关键帧缺失~~（9/10） | 22 视频铺量前置 | 2026-10-12 修复：根因＝Stage 4 不校验产物数 + Stage 5 静默用 `None` 插值；已加双重校验并实测修复 `wanB_00`。详见 [todos §C](file:///D:/ai_projects/ComfyUI/todos/2026-10-11/README.md) |
| 🟢 已完成 | ~~WanAnimate 片头裁剪剩余 19 条~~ | 831959 批处理交付 | 2026-10-12 补齐，**23/23 完成**，逐条核验通过 |
| 🟡 P1 | 动漫短剧「分镜→视频」闭环未跑通 | 业务线 C | `_checkv.py` 目录硬编码需重写 |
| 🟡 P1 | Qwen 2K 有 1 个损坏 PNG（53/54） | 交付完整性 | 重跑补齐 |

> 完整未完成项（含命令与优先级）→ **[todos/2026-10-11/README.md](file:///D:/ai_projects/ComfyUI/todos/2026-10-11/README.md)**

---

## 8. 索引互链

- 待办清单：[todos/2026-10-11/README.md](file:///D:/ai_projects/ComfyUI/todos/2026-10-11/README.md)
- 长期知识库：[.agent/wiki/_index.md](file:///D:/ai_projects/ComfyUI/.agent/wiki/_index.md)（JOURNAL / CHRONICLE / DEBT_LEADGER / INBOX）
- 工作流清单：[WORKFLOW_INVENTORY.md](file:///D:/ai_projects/ComfyUI/WORKFLOW_INVENTORY.md)
- 脚本清单：`tools/SCRIPTS_INVENTORY.md`
- 历史交接（10-08 及更早）：`docs/`
