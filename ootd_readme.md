# OOTD 卡点换装全自动流水线 & ComfyUI 纯净姿态工作流操作指南

> **版本**：v3.0.0 (生产交付版)  
> **更新时间**：2026-10-04  
> **适用硬件**：NVIDIA RTX 4060 Ti (16GB) 及以上显卡  
> **核心引擎**：Wan2.2 Animate 14B (Move 模式) + lightx2v 4步极速蒸馏 + RIFE 1080P 超分补帧 + BiRefNet 离线透明立绘 + 单轨纯净原创 BGM

---

## 目录
- [一、 生产全景与技术架构](#一-生产全景与技术架构)
- [二、 纯净单人骨骼体系与目录规范 (彻底根除多出手)](#二-纯净单人骨骼体系与目录规范-彻底根除多出手)
- [三、 模式 A：一键端到端工业化流水线 (run_ootd.bat)](#三-模式-a一键端到端工业化流水线-run_ootdbat)
- [四、 模式 B：ComfyUI Web 可视化交互工作流 (UI 画布)](#四-模式-bcomfyui-web-可视化交互工作流-ui-画布)
- [五、 常见报错与排查指南 (FAQ)](#五-常见报错与排查指南-faq)
- [六、 核心参数约束与优化规范](#六-核心参数约束与优化规范)

---

## 一、 生产全景与技术架构

本项目旨在实现高水准、商业化落地的 **OOTD 多套服装卡点换装大片**。全流程将前置模型生成、主体骨骼提取、4步蒸馏视频渲染、高清插帧及动态四角贴纸合成打通，提供**「命令行一键批量交付」**与**「Web 界面可视化调试」**双轨支持。

```
                    ┌──────────────────────────────┐
                    │  5 张换装模特参考图 (Looks)   │
                    └──────────────┬───────────────┘
                                   │
                     BiRefNet 离线抠图 (10秒快速生成)
                                   │
                    ┌──────────────▼───────────────┐
                    │    RGBA 透明无背景贴纸小人    │
                    └──────────────┬───────────────┘
                                   │
┌──────────────────────────────┐   │   ┌──────────────────────────────┐
│     原始驱动舞蹈视频 (MP4)    │   │   │     原创纯净时尚单轨 BGM      │
└──────────────┬───────────────┘   │   └──────────────┬───────────────┘
               │                   │                  │
    单人 BBox 面积最大值过滤       │                  │
               │                   │                  │
┌──────────────▼───────────────┐   │                  │
│  纯净骨骼序列 (Pose / Face)  │   │                  │
└──────────────┬───────────────┘   │                  │
               │                   │                  │
     Wan2.2 Animate 14B 采样       │                  │
      (4步极速蒸馏, 剪枝9分块)     │                  │
               │                   │                  │
┌──────────────▼───────────────┐   │                  │
│    RIFE 16→30fps 1080P 插帧  │   │                  │
└──────────────┬───────────────┘   │                  │
               │                   │                  │
               └───────────┐       │       ┌──────────┘
                           ▼       ▼       ▼
                    ┌──────────────────────────────┐
                    │  多版本顺时针递减状态机合成  │
                    │   (4 -> 3 -> 2 -> 1 -> 0)    │
                    └──────────────┬───────────────┘
                                   ▼
                    ★ 商业级 12s OOTD 卡点成片交付 ★
```

---

## 二、 纯净单人骨骼体系与目录规范 (彻底根除多出手)

### 1. 痛点根因分析（为什么传统工作流会“多长出一只手”？）
- **传统痛点**：源舞蹈视频如果四角带有小人贴纸、角标、水印或背景路人，直接在工作流内运行 `DWPreprocessor` 会将四周贴纸人物误检。
- **畸变发生**：当舞者手臂运动划过贴纸区域时，多目标骨骼产生混叠，Wan2.2 误将角标贴纸骨骼当作主舞者的副手臂，导致视频在胸前或身体侧面凭空生成**“第三只手/双重手臂”**。

### 2. 解决方案：单人最大 BBox 面积动态过滤算法
我们通过 Python 脚本前置对 DWPose 检测结果进行几何拓扑分析：
- **主舞者 BBox 面积**：约 $1,310,000\text{ px}$；
- **角标贴纸 BBox 面积**：约 $130,000\text{ px}$（仅为主舞者的 1/10）；
- **动态过滤**：每帧仅保留面积最大的唯一主体，将骨架彻底解耦为：
  - **肢体骨骼 (`pose_pure.mp4`)**：只绘制身体与双手，关闭面部；
  - **面部骨骼 (`face_pure.mp4`)**：只绘制面部 70 个关键点，关闭身体与双手。

### 3. 骨骼文件目录归档结构
所有纯净骨骼视频现已按**“分舞蹈分类归档”**规范存放在 `input/motion_poses/<舞蹈名称>/` 目录下：

```
D:\ai_projects\ComfyUI\input\
├── motion_poses\
│   └── ootd_dance\                     # 专属舞蹈分类目录
│       ├── chunk0_pose_pure.mp4        # 分块 0 纯净肢体骨骼 (帧 0~48)
│       ├── chunk0_face_pure.mp4        # 分块 0 纯净面部关键点
│       ├── chunk1_pose_pure.mp4        # 分块 1 纯净肢体骨骼 (帧 41~89)
│       ├── chunk1_face_pure.mp4        # 分块 1 纯净面部关键点
│       ├── chunk2_pose_pure.mp4        # 分块 2 纯净肢体骨骼 (帧 81~129)
│       ├── chunk2_face_pure.mp4        # 分块 2 纯净面部关键点
│       ├── chunk3_pose_pure.mp4        # 分块 3 纯净肢体骨骼 (帧 121~169)
│       └── chunk3_face_pure.mp4        # 分块 3 纯净面部关键点
├── ootd_chunk0_pose_pure.mp4           # 根目录保留副本 (方便 ComfyUI UI 快速检索)
├── ootd_chunk0_face_pure.mp4
└── ...
```

### 4. 全新舞蹈视频一键提取工具
当您拿到任意一段新的舞蹈视频时，运行通用提取工具即可 1 秒生成规范的纯净骨骼：

- **工具路径**：[`tools/ootd_study/extract_pure_pose.py`](file:///D:/ai_projects/ComfyUI/tools/ootd_study/extract_pure_pose.py)
- **命令语法**：
  ```cmd
  cmd /c python tools/ootd_study/extract_pure_pose.py --video input/my_new_dance.mp4 --dance my_new_dance --frames 49
  ```
- **输出成果**：脚本会自动在 `input/motion_poses/my_new_dance/` 与 `input/` 下输出 `my_new_dance_pose_pure.mp4` 和 `my_new_dance_face_pure.mp4`，可直接供 UI 或管线消费。

---

## 三、 模式 A：一键端到端工业化流水线 (run_ootd.bat)

适合批量交付整套大片，无需人工介入。

- **启动脚本**：[`run_ootd.bat`](file:///D:/ai_projects/ComfyUI/run_ootd.bat)
- **底层驱动**：[`tools/ootd_study/run_ootd_pipeline.py`](file:///D:/ai_projects/ComfyUI/tools/ootd_study/run_ootd_pipeline.py)

### 常用运行命令：
```bat
:: 1. 默认全自动端到端跑完全链路 (使用预置 5 款穿搭与舞步)
run_ootd.bat

:: 2. 指定全新的项目名称与全新的 5 张服装参考图目录
run_ootd.bat --project autumn_fashion --looks input/my_autumn_looks/

:: 3. 已有渲染分块，仅调整角标贴纸位置或重新更换 BGM (耗时仅需 30 秒)
run_ootd.bat --stage compose --project autumn_fashion
```

### 执行阶段参数 (`--stage`)：
- `all`：默认全流程（抠图 -> 9块渲染 -> RIFE插帧 -> 白蒙版直通 -> 状态机合成 -> 音频封装）。
- `stickers`：仅执行 BiRefNet 透明立绘提取。
- `render`：仅执行 Wan2.2 Animate 14B 4 步分块渲染。
- `enhance`：仅执行分块拼接与 RIFE 16→30fps 1080P 超分插帧。
- `compose`：仅执行 4→3→2→1→0 顺时针递减状态机合成与单轨纯净 BGM 封装。

---

## 四、 模式 B：ComfyUI Web 可视化交互工作流 (UI 画布)

适合在浏览器中单步调试、更换单套服装或观察节点输出。

- **工作流文件**：[`workflows/v3/ootd_wan_animate_pure_pose_ui.json`](file:///D:/ai_projects/ComfyUI/workflows/v3/ootd_wan_animate_pure_pose_ui.json)
- **使用方法**：
  1. 启动 ComfyUI 服务（默认 `http://127.0.0.1:8188`）；
  2. 将上述 JSON 文件**直接拖入浏览器画布窗口**；
  3. 画布呈现 8 大彩色功能分区：

| 分组编号 | 分组名称 | 包含核心节点 | 职能说明 |
| :---: | :--- | :--- | :--- |
| **①** | 核心模型加载 (蓝色) | UNETLoader, CLIPLoader, VAELoader, 4步蒸馏 LoRA, Relight LoRA, Shift 8.0 | 4060 Ti 16GB 专属 4 步极速蒸馏配置 |
| **②** | OOTD 换装模特 (橙色) | LoadImage, CLIPVisionEncode | 上传单套服装或模特参考图，提取服装外观特征 |
| **③** | 纯净单人骨骼驱动 (绿色) | LoadVideo, GetVideoComponents (x3) | 分别接入原舞步视频、纯净肢体骨骼、纯净面部骨骼 |
| **④** | 提示词工程 (紫色) | CLIPTextEncode (Positive / Negative) | 正向自然微表情与松弛双手，负向排除畸变多肢 |
| **⑤** | Wan2.2 核心采样 (金色) | WanAnimateToVideo, KSampler, VAEDecode | Move 模式核心动作迁移，4 步 Euler 采样出片 |
| **⑥** | 16fps 基础导出 (青色) | CreateVideo, SaveVideo | 生成 480×832 基础分块成片 |
| **⑦** | RIFE 高清补帧 (翠绿) | ImageScale, RIFEInterpolation, VHS_VideoCombine | Lanczos 1080P 超分 + 16→30fps 平滑插帧 (可选) |
| **⑧** | 操作指引便签 (深灰) | Note (x2) | 画布内置操作规范与防多手原理解析便利贴 |

---

## 五、 常见报错与排查指南 (FAQ)

### Q1：导入 UI 工作流后提示“所需的媒体输入未选择文件 (12. 纯净单人肢体骨骼 / 14. 纯净单人面部骨骼 - file)”？
- **原因**：ComfyUI Web 前端对视频节点要求 `[文件名, 模式]` 结构。若前端缓存未同步，会暂时标记为未选定。
- **解法**：
  - **解法 1**：重新拖入已修复的最新版 [`ootd_wan_animate_pure_pose_ui.json`](file:///D:/ai_projects/ComfyUI/workflows/v3/ootd_wan_animate_pure_pose_ui.json)；
  - **解法 2**：在节点 12 的下拉菜单中点选 `ootd_chunk0_pose_pure.mp4`，在节点 14 的下拉菜单中点选 `ootd_chunk0_face_pure.mp4`，红框即刻解除。

### Q2：为什么成片中偶尔听到原视频的杂音？
- **原因**：早期的实验版本采用了原声 (0.85) + BGM (0.65) 的双轨混音，将现场底噪收录了进来。
- **解法**：当前流水线已全面切换为**单轨纯净原创 BGM 机制**（曲目：`Calling_Through_The_Screen (1).mp3`），彻底切断原舞步声音通道，成片音质纯净通透。

### Q3：换了新的舞蹈视频后又出现了“第三只手”？
- **原因**：新舞蹈视频四角带有贴纸或背景路人，且没有经过单人骨骼纯化。
- **解法**：对新视频执行 `python tools/ootd_study/extract_pure_pose.py --video <新视频路径>`，将生成的纯净骨骼文件接入节点 12 与 14 即可 100% 杜绝畸变。

---

## 六、 核心参数约束与优化规范

| 参数项 | 标准设定 | 设计原因与工程约束 |
| :--- | :--- | :--- |
| **分辨率 (Width × Height)** | **480 × 832** | 必须为 16 的整数倍；9:16 竖屏手机最佳比例，确保 RTX 4060 Ti 显存稳定不爆 |
| **片段帧数 (Length)** | **49 帧** | Wan2.2 Animate 约束：必须满足 `(length % 4 == 1)`，49 帧约对应 16fps 下的 3 秒循环 |
| **采样步数 (Steps)** | **4 步** | 挂载 `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16`，Euler 采样器，CFG 1.0 |
| **光影重打 (Relight LoRA)** | **强度 1.0** | 挂载 `WanAnimate_relight_lora_fp16`，显著增强棚拍立体质感与真实阴影 |
| **采样流位移 (Shift)** | **8.0** | `ModelSamplingSD3` 设定 shift 8.0，大幅提升蒸馏后画面的细节锐利度 |
| **RIFE 插帧与超分** | **16fps → 30fps** | 采样阶段以 16fps 降本提速，后期由 RIFE 补帧至 30fps 1080×1920，达成丝滑观感 |
| **产物输出目录** | **`output/YYYY-MM-DD/`** | 严格遵循每日归类规范，严禁直接散落在根目录 |

---
*文档归档路径：[`D:\ai_projects\ComfyUI\ootd_readme.md`](file:///D:/ai_projects/ComfyUI/ootd_readme.md)*
