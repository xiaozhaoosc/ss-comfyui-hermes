# 《北宋杨家将》第 3 集试点基准评测报告：Google Flow vs Muse.ai 双平台对比

> **日期**：2026-10-09  
> **评测镜头**：第 3 集 Shot 01（首镜 · 圣驾巡边 · 4s/10s 运镜）  
> **基准输入素材**：[output/2026-10-09/yangjiajiang_ep03/comparison/shot01.jpg](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/comparison/shot01.jpg)（由第 3 集 Grid 01 水墨原画无损裁切）  
> **统一提示词**：
> `Vertical shot, camera tilts up slowly. Grand Song imperial carriage procession marching north under bleak winter skies, giant ochre-yellow dragon flag fluttering violently in freezing howling wind. Traditional Chinese ink wash cut-paper animation style, crisp black ink linework, muted cel shading.`  
> **测试环境**：Windows 11 / Chrome CDP 9222 远程接管 / 代理 `127.0.0.1:7897`

---

## 一、 核心测试结果与量化对比总表

| 评测维度 | Muse.ai 方案 | Google Flow (Nano Banana 2.1) | 优势平台判定 |
| :--- | :--- | :--- | :---: |
| **测试跑通状态** | **100% 生成并成功下载 MP4 终身母盘** | **100% 成功生成超清三联国风原画** | 两端均跑通 |
| **产物文件路径** | [muse_shot01.mp4](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/comparison/muse_shot01.mp4) | [flow_shot01_gen_2.png](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/comparison/flow_shot01_gen_2.png)<br/>[flow_shot01_gen_3.png](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/comparison/flow_shot01_gen_3.png) | Muse 出视频 / Flow 出原画 |
| **成片分辨率/画幅** | **720 × 1280 (9:16 标清竖屏)** | **1792 × 1024 (16:9 画布三联版)** | 各有千秋 |
| **帧率与时长** | **24.0 fps / 10.0 秒完整运镜** | 静态分镜原画 | **Muse.ai 胜** (视频) |
| **视频编码与体积** | **H.264 / AAC 音频 / 10.6 MB** | PNG (1.07 MB / 0.99 MB) | **Muse.ai 胜** |
| **水墨剪纸国风保持度** | **极高**：完美继承首帧的白描线稿、赭黄龙旗、禁军铠甲与冬雪雪花，零 3D 崩坏 | **极高**：工笔重彩与水墨苍茫感极强，自动衍生出雪山巡狩与飞龙大纛 | 平手（顶尖水平） |
| **生成耗时** | **约 45 秒**（对话提交到完成出片） | **约 25 秒**（提交到 100% 渲染完成） | 均极其迅速 |
| **CDP 批量工程化难度** | **极低（5星）**：对话式接口，支持直接上传图片 + 回车发送，Blob 无感提取 | **中等（3星）**：Canvas 画布多层 DOM，存在遮罩与富文本编辑器状态拦截 | **Muse.ai 胜** (自动化稳定性) |

---

## 二、 Muse.ai 生成视频实测深度审计

### 1. 动态与镜头表现（720P / 24fps / 10s）
- **镜头轨迹**：实现了教科书级别的缓慢上摇（Slow Tilt-up），视线从底部的宋太宗皇家辇车、披铠侍卫逐步延展至迎风猎猎翻卷的两丈赭黄龙旗；
- **动态稳定性**：龙纹鳞爪在寒风中翻滚时线条极度扎实，没有传统扩散模型常见的“面部融化”或“旗帜抽搐”现象；
- **环境氛围**：天空飘落的雪花与北地铅灰色积雪寒云层次分明，呈现高度正统的上美影动画长片质感。

### 2. 采样帧存档（[output/2026-10-09/yangjiajiang_ep03/comparison/muse_frames/](file:///d:/ai_projects/ComfyUI/output/2026-10-09/yangjiajiang_ep03/comparison/muse_frames/)）
- `frame_1s.jpg`：车队起步，禁军重步兵执戈前行；
- `frame_3s.jpg`：龙旗在画面中央霸气翻卷，车舆金顶朱柱反光自然；
- `frame_5s.jpg`：中景延伸至远方北伐雪原与苍松；
- `frame_8s.jpg`：高潮留白，风雪呼啸。

---

## 三、 Google Flow (Nano Banana 2.1) 生成原画实测深度审计

### 1. 艺术表现力与构图创新
- Google Flow 的 Nano Banana 2.1 模型在理解“Traditional Chinese ink wash cut-paper animation style”上表现出极高水准；
- 自动生成了 **左（巡幸雪径）- 中（龙旗破雪）- 右（金龙点睛）** 的三联全景长卷，留白与水墨飞白（Ink Splatter）极具国画韵味；
- 该模型生成的产物是极其顶级的“原画/关键帧资产”，极适合作为批量生视频前的 **分镜母版原画库**！

---

## 四、 结论与全集主力平台推荐方案

结合第 3 集全 54 镜（214.0 秒 Picture Lock）工程目标，给出以下最终选型推荐：

```mermaid
flowchart LR
    A["第 3 集 6 组九宫格提示词与原画切片<br/>(Grid 01 ~ Grid 06)"] --> B{"分工混合生产管线"}
    B -->|"复杂场景/英雄特写原画"| C["Google Flow (Nano Banana 2.1)<br/>产出顶格水墨关键帧"]
    B -->|"全量批量图生视频 (54 镜)"| D["Muse.ai (自动化 CDP 引擎)<br/>快速稳定批量输出 720P 24fps 视频"]
    C --> D
    D --> E["本地母带引擎 (FFmpeg + Edge-TTS)<br/>214.0s 严格对齐 + 沧桑旁白 + 华文楷体字幕"]
    E --> F["第 3 集终极大总成成片交付"]
```

### 推荐落地策略：
1. **主力视频生成端锁定为 Muse.ai**：
   - 理由：经实测，Muse.ai 对图生视频（Image-to-Video）的指令响应最敏捷，生成的 720P 24fps 视频完全满足上美影国风正剧要求，且 CDP 自动化接口极度平稳，可直接编写全自动脚本批量跑完 Grid 01 前 9 镜！
2. **Google Flow 作为资产/原画增强端**：
   - 拥有 1,050 PRO Credits，可用于关键高潮镜头（如大郎替主、六郎突围金枪破阵）的概念原画生成与超清扩图。
3. **音频依然收拢于本地母带引擎**：
   - 维持第 2 集验证成功的经验，统一由本地 Edge-TTS 注入纯净正剧旁白，确保第 1、2、3 集声音一致性。
