# 北宋杨家将项目 · 2026-10-09 工作清单与工程深度复盘报告

**文档日期**：2026-10-09  
**工程目标**：第 3 集《金沙滩赴会》（又名《邠阳城救驾》）前期视听资产筹备、双平台实测对比、云端/本地双轨跑片验证、深度质量溯源与纯净电影级生产线重构。  
**关联剧本大纲**：`d:\ai_projects\ComfyUI\todos\北宋杨家将` 连环画第二册救驾大纲与短剧 B 方案规范。

---

## 一、今日核心工作清单 (What We Did)

### 1. 前期视听工程与全量资产 100% 入库
- **九宫格原画全集生成**：成功生成 6 组九宫格原画大图（Grid 01 ~ Grid 06，涵盖全 5 幕 54 镜），归档至 `output/2026-10-09/yangjiajiang_ep03/grids/`。
- **54 句母带旁白音频**：采用微软 Edge-TTS 云健沧桑正剧男声（`zh-CN-YunjianNeural`，微调语速 `-3%`、音调 `-2Hz`），入画 `0.35s` 延迟、尾音留白 `0.40s`，全 54 句无损音频全部生成至 `output/2026-10-09/yangjiajiang_ep03/audio/`。
- **54 镜金石战局注疏名片**：采用华文楷体与半透明宣纸黑底+金石烫金边框（`420x72` PNG），生成至 `output/2026-10-09/yangjiajiang_ep03/cards/`。
- **全集及分幕精准 SRT 字幕**：毫秒级绝对时序排布，生成全集 214.0 秒总 SRT 及 5 幕独立分幕字幕，存放在 `output/2026-10-09/yangjiajiang_ep03/final/`。

### 2. 双平台（Google Flow vs Muse.ai）实测对比与基准评测
- **第一轮实测（Shot 01 战旗武戏）**：
  - Muse.ai 生成 720P 24fps 竖屏视频（`muse_shot01.mp4`）；
  - Google Flow 生成三联宽画幅高精原画（`flow_shot01_gen_2.png`）；
  - 沉淀技术报告：[BENCHMARK_REPORT_EP03_SHOT01_FLOW_VS_MUSE_2026-10-09.md](file:///d:/ai_projects/ComfyUI/docs/BENCHMARK_REPORT_EP03_SHOT01_FLOW_VS_MUSE_2026-10-09.md)。
- **第二轮实测（Shot 02 寇准苦谏文戏）**：
  - Muse.ai 生成朝堂文戏视频（`muse_shot02.mp4`，5.97MB）；
  - Google Flow 生成殿堂全景与近景双方案高精概念原画（`flow_shot02_gen_1.png` 1.11MB, `gen_2.png` 1.07MB）；
  - 沉淀技术报告：[BENCHMARK_REPORT_EP03_ROUND2_FLOW_VS_MUSE_2026-10-09.md](file:///d:/ai_projects/ComfyUI/docs/BENCHMARK_REPORT_EP03_ROUND2_FLOW_VS_MUSE_2026-10-09.md)。

### 3. 双轨自动化管线开发与并发推进
- **本地 ComfyUI 流水线**：优化 [yangjiajiang_ep03_pipeline.py](file:///d:/ai_projects/ComfyUI/tools/yangjiajiang_ep03_pipeline.py)，支持智能断点续跑与全 54 镜一键非阻塞提交（Submit-Only）。
- **云端 Muse.ai 自动化管线**：编写 [batch_muse_pipeline.py](file:///d:/ai_projects/ComfyUI/tools/batch_muse_pipeline.py)，通过 Chrome 远程调试 CDP 端口（`9222`）实现首帧上传、提示词发送与视频自动下载。
- **后道母带大总成引擎**：编写 [yangjiajiang_ep03_master_engine.py](file:///d:/ai_projects/ComfyUI/tools/yangjiajiang_ep03_master_engine.py)，集成 Lanczos 720P 超分、-an 剥噪、旁白贴合、金石名片叠加与分幕/全集成片拼接。

---

## 二、重大问题定位与深度技术复盘 (Retrospective & Root Causes)

今日在测试全集交付阶段，用户精准敏锐地指出了成片中暴露的严重质量缺陷：
> *“生成的 muse_720P 版本有大量的 muse logo，画面缺少太多，云端全集问题太多；生成完成全要先检查完成后才行，有问题需要及时修复”*

经深度抽样截帧与底层代码逆向排查，查实了以下**两大核心致命问题**：

### 🔴 痛点 1：Muse.ai 周额度耗尽导致平台下发官方 Logo 占位视频
- **表面现象**：视频中大量出现毛茸茸的卡通小娃娃抱着水晶球（Muse 官方吉祥物 Logo），且伴随 480x480 正方形上下大黑边。
- **根本原因**：Muse.ai 免费/标准周额度已耗尽。平台在超额请求时未报错阻断，而是静默返回了平台官方宣传用的预置占位循环视频。
- **应对决策**：
  - **果断封存云端**：遵照用户指示，15 号额度重置前彻底停止 Muse.ai 一切调用；
  - **全面转战本地**：将整部第 3 集的生产重心 100% 切换并收敛至本地 RTX 4060 Ti 16GB 独显 ComfyUI 纯本地离线流水线。

### 🔴 痛点 2：旧切片脚本暴力截取，导致“粗黑线框 + 英文乱码 + 强行拉伸变形”
- **表面现象**：画面内容只占画面中央一小部分（“画面缺少太多”），画面四周有生硬黑线，底部伴有英文动态乱码，人物身材严重纵向拉长变形。
- **根本原因**：
  1. 原始九宫格大图中，每个子格包含【外围白留白 + 黑色矩形画框 + 底部 3 行英文说明文字】；
  2. 原切片脚本采用简单网格等分截取，未剔除黑线和英文，且直接调用 `resize((544, 960))` 强行拉伸！4:3 横图被拉伸为 9:16 竖图，导致人物形体滑稽畸变；
  3. 扩散模型将底栏英文字符识别为图像内容去动态扩散，导致底部出现恶性乱码。

### 🟢 彻底根治方案：
1. **像素级纯净画芯智能提取算法**（[reprocess_clean_ep03_slices.py](file:///d:/ai_projects/ComfyUI/tools/reprocess_clean_ep03_slices.py)）：
   - 水平/垂直连续黑线阈值检测，内缩 4px，100% 剥离粗黑框；
   - 强制画框下限 $y \le 260$，彻底阻断 $y \ge 269$ 的英文字符行；
2. **电影级柔焦景深满幅延展（Cinema Blur Pad）**：
   - 彻底废除拉伸变形：画芯按原始比例居中展示，锐度与构图 100% 保全；
   - 上下采用原画高斯模糊柔焦景深自然延展铺满 544x960 画布，绝无单色黑边或白边，观感浑然天成；
   - 全 54 镜纯净输入首帧已 100% 刷新入库！

---

## 三、生产流水线最新状态与现状 (Current Status)

| 模块 / 环节 | 当前状态 | 详细指标 |
| :--- | :---: | :--- |
| **云端 Muse.ai** | **已全面停用** | 停止调用，等待 15 号额度重置 |
| **首帧素材净化** | **100% 达标** | 54 镜全新电影级无黑框无英文首帧全部刷新至 `input/` |
| **旧劣质视频隔离** | **已隔离** | 37 个带黑框旧视频已移动至 `legacy_bad_videos/` |
| **本地 ComfyUI** | **全速渲染中** | 全新 54 镜纯净任务已全量入队，RTX 4060 Ti 稳定运行中 |
| **逐镜自动质检系统** | **已部署守护** | [comfy_shot_quality_auditor.py](file:///d:/ai_projects/ComfyUI/tools/comfy_shot_quality_auditor.py) 实时抽帧质检 |
| **母带总装引擎** | **就绪待命** | [yangjiajiang_ep03_master_engine.py](file:///d:/ai_projects/ComfyUI/tools/yangjiajiang_ep03_master_engine.py) 待 54 镜出齐后一键成片 |

---

## 四、下一步执行计划 (Next Steps)

1. **无人值守渲染与全量机器质检**：
   - 本地 ComfyUI 预计在约 50 分钟内完成全 54 镜纯净视频渲染；
   - 运行质量审计系统，确保 54 镜全部达到 `[√ PASS]` 标准（无黑边、无黑屏、无拉伸、时长充足）。
2. **一键母带总装交付**：
   - 运行 `python tools/yangjiajiang_ep03_master_engine.py --assemble --source comfyui`；
   - 产出 **720P 214.0 秒《北宋杨家将》第 3 集纯净正剧母带成片** 及 5 幕独立成片。
3. **开启新会话推进第 4 集**：
   - 严格遵循《执行纪律与 Token 控制规范》，在成片最终交付后开启全新会话，直接复用成熟的“纯净九宫格切片 + 自动化质检 + 本地母带装配”工业级管线推进第 4 集！
