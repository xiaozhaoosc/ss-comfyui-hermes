# 《北宋杨家将》项目工程交接与新会话启程指南 (Handover Document)

**交接时间**：2026-10-10 09:58:07 (本地时间)  
**工程阶段**：第 3 集《金沙滩赴会》（邠阳城救驾）100% 交付验收完成 ➔ 即将开启第 4 集生产  
**工作空间**：`d:\ai_projects\ComfyUI`  
**核心参考文档**：`d:\ai_projects\ComfyUI\todos\北宋杨家将`  
**主要执行环境**：Windows 11 / 本地 RTX 4060 Ti 16GB 独显 / MiniMax H3 扩散引擎 / FFmpeg 8.1 / Python 3.10  

---

## 一、第 3 集已交付核心产物清单 (Deliverables)

所有产物严格遵循当日归档规范，完整就绪于 `output/2026-10-09/yangjiajiang_ep03/`：

### 1. 最终电影级母带成片 (Final Master Deliverables)
| 产物名称 | 文件大小 | 规格参数 | 绝对路径 / 访问链接 |
| :--- | :---: | :--- | :--- |
| **第 3 集全集正剧母带成片** | **111.96 MB** | **720×1280 竖屏 · 24fps · 214.04秒 · 双轨旁白 · 金石名片全覆盖** | [北宋杨家将_第03集_全集正剧母带_comfyui_720p.mp4](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/final/北宋杨家将_第03集_全集正剧母带_comfyui_720p.mp4) |
| **第 1 幕·盛极隐忧 五台还愿** | 18.36 MB | 720P · 24fps · 36.0s (Shot 01~09) | [Act1_盛极隐忧 · 五台还愿_comfyui_720p.mp4](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/final/Act1_盛极隐忧%20·%20五台还愿_comfyui_720p.mp4) |
| **第 2 幕·幽州暗伏 诱敌深入** | 19.49 MB | 720P · 24fps · 36.0s (Shot 10~18) | [Act2_幽州暗伏 · 诱敌深入_comfyui_720p.mp4](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/final/Act2_幽州暗伏%20·%20诱敌深入_comfyui_720p.mp4) |
| **第 3 幕·孤城合围 铁锁大闭** | 16.47 MB | 720P · 24fps · 36.0s (Shot 19~27) | [Act3_孤城合围 · 铁锁大闭_comfyui_720p.mp4](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/final/Act3_孤城合围%20·%20铁锁大闭_comfyui_720p.mp4) |
| **第 4 幕·箭创敌首 决死突围** | 19.53 MB | 720P · 24fps · 36.0s (Shot 28~36) | [Act4_箭创敌首 · 决死突围_comfyui_720p.mp4](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/final/Act4_箭创敌首%20·%20决死突围_comfyui_720p.mp4) |
| **第 5 幕·金刀赴难 绝地死局** | 38.11 MB | 720P · 24fps · 70.0s (Shot 37~54) | [Act5_金刀赴难 · 绝地死局_comfyui_720p.mp4](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/final/Act5_金刀赴难%20·%20绝地死局_comfyui_720p.mp4) |

### 2. 基础素材与标准资产基座
- **全 54 镜纯净无瑕首帧原画**：`input/yang_ep03_shot01.jpg` ~ `shot54.jpg`（已彻底剃除黑边框与英文字符，柔焦景深满幅无畸变）。
- **54 句 Edge-TTS 旁白音频**：`output/2026-10-09/yangjiajiang_ep03/audio/shot_01.mp3` ~ `shot_54.mp3`。
- **54 镜金石战局注疏名片**：`output/2026-10-09/yangjiajiang_ep03/cards/card_01.png` ~ `card_54.png`。
- **全集及分幕精准 SRT 字幕**：`output/2026-10-09/yangjiajiang_ep03/final/北宋杨家将_第03集_全集字幕.srt`。
- **全量 54 镜质量审计矩阵报告**：[EP03_LOCAL_COMFY_QUALITY_AUDIT_REPORT.md](file:///d:/ai_projects/ComfyUI/docs/EP03_LOCAL_COMFY_QUALITY_AUDIT_REPORT.md)（合格率 54/54 100%）。
- **全天工作清单与深度技术复盘**：[DAILY_WORK_SUMMARY_AND_RETROSPECTIVE_2026-10-09.md](file:///d:/ai_projects/ComfyUI/docs/DAILY_WORK_SUMMARY_AND_RETROSPECTIVE_2026-10-09.md)。

---

## 二、标准化工具链技术遗产 (Reusable Toolchain)

在第 3 集攻坚中沉淀出的一整套工业级脚本，均位于 `tools/` 目录，第 4 集可**直接复用或参数化调用**：

| 工具脚本 | 核心功能与工业标准 |
| :--- | :--- |
| **`tools/reprocess_clean_ep03_slices.py`** | **像素级智能画芯定位提取器**：通过连续线段探测自动内缩 4px 剥离粗黑框，强制 $y \le 260$ 剔除英文底栏，施加柔焦景深延展（Cinema Blur Pad）生成不拉伸的 544×960 9:16 标准首帧。 |
| **`tools/yangjiajiang_ep03_pipeline.py`** | **ComfyUI 本地生产流水线**：集成 4-step Turbo H3 极速工作流，支持 `--all --submit-only`，纯提交非阻塞，智能跳过已有视频，显存开销稳定在 13.8GB。 |
| **`tools/comfy_shot_quality_auditor.py`** | **自动化逐镜多维画质审计系统**：逐镜检测时长、544x960 规格，并在 1.5s 核心时序抽帧计算色彩方差，严防黑屏/死帧，自动生成 Markdown 审计矩阵。 |
| **`tools/yangjiajiang_ep03_master_engine.py`** | **全链路声画母带大总成引擎**：执行 Lanczos 720P 超分、`-an` 剔除原生白噪、混入 Edge-TTS 沧桑男声、右上角叠名片、烧录楷体字幕，串联全剧 214.0s 最终成片。 |
| **`tools/check_dual_pipeline_status.py`** | **实时生产看板查询器**：秒级汇报本地队列运行数、排队数及已出片比例。 |

---

## 三、关键避坑备忘 (Crucial Lessons Learned)

1. **云端平台额度与占位符陷阱**：
   - **Muse.ai**：周免费额度耗尽后不报错，而是返回带有平台 Logo 的毛绒吉祥物 480p 占位视频。**在 15 号额度刷新前坚决封存云端调用**，全流程优先锁定本地 RTX 4060 Ti 16GB。
2. **切片严禁机械等分**：
   - 九宫格原画自带粗黑画框与底部 3 行英文，直接等分截取会导致黑线变形和英文字符乱码动态扩散。必须统一走画芯探测与景深延展算法。
3. **执行纪律守则**：
   - Windows 终端必须加 `cmd /c`；
   - 生产任务只提交不轮询；
   - 每日产物必须严格归档于 `output/YYYY-MM-DD/` 子目录；
   - 阶段切换用新会话以节省每轮上下文 Token 开销。

---

## 四、新会话一键启程 Prompt 建议 (Copy & Paste to New Session)

在新会话开启时，您可以直接将以下内容复制发送给助手：

```text
你好！我们已经圆满完成了《北宋杨家将》第 3 集《金沙滩赴会》全链路 214.0 秒母带成片交付与全量质量审计（详见 docs/HANDOVER_EP03_TO_EP04_2026-10-10.md）。

现在我们正式启动【第 4 集】的制作：
1. 请阅读 docs/HANDOVER_EP03_TO_EP04_2026-10-10.md 了解全套标准化生产线与规程；
2. 参考 d:\ai_projects\ComfyUI\todos\北宋杨家将 中对应的分镜大纲与剧本；
3. 直接复用成熟的“纯净九宫格切片 + ComfyUI 本地流水线 + 自动化画质审计 + 母带大总成引擎”工具链，开展第 4 集的前期资产（九宫格、纯净首帧、Edge-TTS 旁白、金石名片）筹备与生产！
```
