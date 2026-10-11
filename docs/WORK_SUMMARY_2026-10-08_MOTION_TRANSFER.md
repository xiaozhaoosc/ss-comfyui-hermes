# 2026-10-08 工作总结：Wan2.2 动作迁移与人物融合全链路开发与全时长落地

---

## 一、工作概述与目标达成

今日核心任务围绕 **基于 Wan2.2 Animate 14B + DWPose 纯净姿态解耦** 构建通用的 **“任意人物图片 + 任意参考视频 -> 动作迁移与人物融合”** 工业化生产链路，并完成从 **短切片单帧融合** 到 **100% 完整时长（6~7秒）自动多 Chunk 切片与无缝缝合** 的全流程落地验证。

### 核心达成指标
1. **纯净姿态与表情解耦管道**：实现从任意参考视频中自动提取肢体动作（`pose_video`）与面部表情（`face_video`），集成单人最大 BBox 过滤算法，彻底杜绝水印、贴纸与路人多肢体干扰，抽取资产支持永久可复用。
2. **双模式工作流交付**：
   - **模式一（Web UI 交互流）**：提供直观可视化工作流，支持拖拽替换图片与视频，已同步至 ComfyUI 用户目录。
   - **模式二（无头 CLI 脚本流）**：支持一键参数化执行（姿态提取 -> 显存适配注入 -> 提交渲染 -> 结果校验），提供干跑与资产仅提取模式。
3. **基准测试交付**：双模式各 3 个、共计 6 套 10 秒级动作融合测试视频全部高保真出片并完成音频混录。
4. **用户自定义素材 1:1 全时长还原**：针对用户提供的真实业务素材（Instagram14 6.07秒 / Instagram18 7.07秒）与人物定妆照（`005-822807425_...jpeg`），实现 **100% 逐帧对齐（182帧 & 212帧）** 的全时长还原，并完成同屏对比与背景音乐合成。

---

## 二、架构设计与核心技术实现

### 1. 纯净姿态解耦与过滤算法
* **痛点**：原生参考视频常含有贴纸小人、背景路人或复杂肢体交叉，直接输入 WanAnimate 易导致模型产生“第三只手”或肢体畸变。
* **解决方案**：在 [`tools/ootd_study/extract_pure_pose.py`](file:///d:/ai_projects/ComfyUI/tools/ootd_study/extract_pure_pose.py) 中采用 **DWPose (YOLOX-L + DWPose-384)** 关键点检测器，动态计算画面内所有人体的包围盒（BBox）面积，仅保留面积最大者为主体舞者，其余全部剔除。
* **通道分流**：
  - 导出 `_pose_pure.mp4`：仅包含主体身体骨骼与双手骨架（无面部关键点）；
  - 导出 `_face_pure.mp4`：仅包含主体面部五官表情点（无肢体骨架）；
  - 成果归档至 `input/motion_poses/<项目名>/`，后续任意人物穿搭均可秒级调用，无需重复计算。

### 2. 硬件约束下的多 Chunk 切分与缝合拓扑
针对本机 **RTX 4060 Ti 16GB (`--lowvram`)** 的显存特点，Wan2.2 14B 模型采用注意力机制时，单次推演帧数存在显存上限。
* **分块约束**：单 Chunk 帧数采用金牌参数 `Length = 49`（满足 Wan 模型 `(length - 1) % 4 == 0`，推演 170 秒，单块显存占用峰值稳定在 13~14GB，零 OOM 风险）；
* **运动连续性**：两 Chunk 间保留 4~5 帧重叠区（利用 `video_frame_offset` 与 `continue_motion_max_frames` 保持运动初速度一致）；
* **时间轴缝合算法**：
  - **Instagram14 (182帧 / 6.07s)**：
    $$\text{Chunk 0 [0..45)} + \text{Chunk 1 [0..44)} + \text{Chunk 2 [0..44)} + \text{Chunk 3 [0..49)} = 182 \text{ 帧 (100\%)}$$
  - **Instagram18 (212帧 / 7.07s)**：
    $$\text{Chunk 0 [0..45)} + \text{Chunk 1 [0..44)} + \text{Chunk 2 [0..44)} + \text{Chunk 3 [0..30)} + \text{Chunk 4 [0..49)} = 212 \text{ 帧 (100\%)}$$
  - 逐分块帧级去重裁切后，通过 FFmpeg concat 协议进行帧无损缝合，接缝处动作平滑、无瞬移抖动。

---

## 三、工程产物与代码资产沉淀

### 1. 工作流与核心脚本
| 文件类别 | 路径 | 功能说明 |
| :--- | :--- | :--- |
| **Web UI 工作流** | [`workflows/v3/motion_transfer_wan_animate_ui.json`](file:///d:/ai_projects/ComfyUI/workflows/v3/motion_transfer_wan_animate_ui.json) | 适配 ComfyUI 界面加载的中文交互工作流（已同步至 user 目录） |
| **API 模板工作流** | [`workflows/v3/wan_animate_pure_pose_api.json`](file:///d:/ai_projects/ComfyUI/workflows/v3/wan_animate_pure_pose_api.json) | 无头自动化渲染的参数注入模板 |
| **端到端 CLI 流水线** | [`tools/motion_transfer_pipeline.py`](file:///d:/ai_projects/ComfyUI/tools/motion_transfer_pipeline.py) | 接收图+视频，自动提取管道并提交人物融合渲染 |
| **纯净姿态提取工具** | [`tools/ootd_study/extract_pure_pose.py`](file:///d:/ai_projects/ComfyUI/tools/ootd_study/extract_pure_pose.py) | DWPose 单人纯净化、解耦双轨视频导出核心脚本 |
| **全时长自动化编排器** | [`tools/auto_full_duration_pipeline.py`](file:///d:/ai_projects/ComfyUI/tools/auto_full_duration_pipeline.py) | 监听骨骼就绪 -> 分批提交各 Chunk -> 轮询渲染 -> 自动裁切去重缝合 |
| **同屏对比视频生成器** | [`tools/create_full_comparisons.py`](file:///d:/ai_projects/ComfyUI/tools/create_full_comparisons.py) | 生成原驱动视频 vs 融合视频的 1:1 双联/三联同屏对比 MP4 |
| **产物质量检验工具** | [`tools/verify_final_results.py`](file:///d:/ai_projects/ComfyUI/tools/verify_final_results.py) | 提取音视频分辨率、帧数、帧率、编码规格与文件大小 |

### 2. 视频交付成果
所有交付产物严格遵循当日归档规范：

#### ① 1:1 全时长还原成片（终极交付物）
* **Instagram14 全长成片**：[`output/2026-10-08/motion_transfer_full/ig14_1to1_full_duration.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-08/motion_transfer_full/ig14_1to1_full_duration.mp4)  
  *参数：480×832，30.0 fps，182/182 帧（6.07秒），含 BGM 音轨，体积 0.92MB*
* **Instagram14 全长同屏对比**：[`output/2026-10-08/motion_transfer_full/ig14_full_side_by_side.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-08/motion_transfer_full/ig14_full_side_by_side.mp4)  
  *参数：960×832 超宽同屏（左: 原视频 \| 右: 005融合），182 帧，体积 1.48MB*
* **Instagram18 全长成片**：[`output/2026-10-08/motion_transfer_full/ig18_1to1_full_duration.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-08/motion_transfer_full/ig18_1to1_full_duration.mp4)  
  *参数：480×832，30.0 fps，212/212 帧（7.07秒），含 BGM 音轨，体积 0.81MB*
* **Instagram18 全长同屏对比**：[`output/2026-10-08/motion_transfer_full/ig18_full_side_by_side.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-08/motion_transfer_full/ig18_full_side_by_side.mp4)  
  *参数：960×832 超宽同屏（左: 原视频 \| 右: 005融合），212 帧，体积 1.24MB*

#### ② 用户双案例连贯串联与三联屏评测片
* **双案例无缝串联成片**：[`output/2026-10-08/motion_transfer/instagram_user_combined_stitched.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-08/motion_transfer/instagram_user_combined_stitched.mp4)
* **Instagram14 三联屏对比**：[`output/2026-10-08/motion_transfer/ig14_side_by_side_comparison.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-08/motion_transfer/ig14_side_by_side_comparison.mp4)
* **Instagram18 三联屏对比**：[`output/2026-10-08/motion_transfer/ig18_side_by_side_comparison.mp4`](file:///d:/ai_projects/ComfyUI/output/2026-10-08/motion_transfer/ig18_side_by_side_comparison.mp4)

#### ③ 6 套 10 秒级基准评测视频
存放在 [`output/2026-10-04/motion_transfer_test/`](file:///d:/ai_projects/ComfyUI/output/2026-10-04/motion_transfer_test/)：
* 模式一：`mode1_case1_look1_10s.mp4`, `mode1_case2_bathroom_10s.mp4`, `mode1_case3_sailor_10s.mp4`
* 模式二：`mode2_case4_redslip_10s.mp4`, `mode2_case5_refimage_10s.mp4`, `mode2_case6_model1_10s.mp4`

---

## 四、工程规范与执行纪律回顾

1. **工作流隔离原则**：所有学习参考目录（`workflows/v2学习/comfyui/`）保持严格只读，新研发工作流统一建立于 `workflows/v3/`。
2. **产物归档规范**：全部分块中间帧、拼接成片、同屏对比视频及日志严格按当日日期分目录归档至 `output/2026-10-08/`。
3. **成本与执行纪律**：
   - 长渲染任务（7个 Chunk，耗时约 20 分钟）通过后台守护进程提交，彻底与对话交互解耦；
   - 未在对话上下文中进行无效轮询（sleep+check），严格控制 Token 消耗；
   - 解决了 Windows 环境下 GBK 字符编码与 FFmpeg 复杂参数排序问题，保障了流水线端到端自主闭环。

---

## 五、后续演进建议

1. **超分与插帧集成**：当前 480×832 分辨率适合高吞吐生产，后续可将现成的 RIFE 插帧（16fps -> 30/60fps）及 CCSR/SeedVR 超分节点挂接于最终缝合后的成片上，实现 1080P/4K 高清交付。
2. **批量化素材库接入**：提取好的 `input/motion_poses/` 姿态库已固化为通用标准资产，可批量挂接不同的服装或电商模特图片，实现“一舞多穿”与“多角色批量分身”的内容矩阵生产。
