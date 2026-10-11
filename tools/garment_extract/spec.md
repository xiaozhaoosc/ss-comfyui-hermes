# Spec: 视频服装提取工作流（garment_extract）

## 目标
从 `output/2026-10-11/instagram_ayano_fj/` 的 2 个视频中提取"纯净的服装"——
即去掉人物/背景、只保留服装本身的透明底 PNG（并附带白底版本），用于后续参考图 / 试穿 / 训练用途。

## 输入
| 文件 | 规格 |
|---|---|
| 2026-10-07_12-56-14_DeMaIN9gB3Q_1.mp4 | 720×1280, 30fps, 10.2s |
| 2026-10-09_12-54-23_DeRjgPHgZAK_1.mp4 | 720×1280, 30fps, 14.6s |

## 输出
`output/2026-10-11/garment_extract/<视频名>/` 下：
- `keyframes/` — 每视频抽取的清晰候选帧（JPEG）
- `person_cutout/` — BiRefNet 抠出的人物透明图
- `garment/` — 最终纯净服装图：`garment_<n>_transparent.png` + `garment_<n>_white.png`
- `manifest.json` — 每张图的来源视频、帧号、清晰度得分、mask 面积

## 流水线（4 阶段，ComfyUI API 驱动）

### Stage 1 — 关键帧抽取（ffmpeg，不经 GPU）
- 均匀采样 + sharpness(拉普拉斯方差) 打分，每视频取 Top-N（N=12）
- 过滤：近似重复帧（相邻帧差 < 阈值则去重）

### Stage 2 — 人像抠图（BiRefNet-general）
- 输入候选帧 → `BiRefNet-general` 得到人物前景 alpha
- 输出人物透明 cutout，同时留下 alpha mask 供 Stage 3 裁剪范围

### Stage 3 — 服装区域分割（SAM2）
- `face_yolov8m` 检测人脸框 → 推算躯干锚点（人脸下沿 0.5~1.2 倍脸高处取 2~3 个正样本点）
- `Sam2Segmentation`（sam2_hiera_base_plus）用锚点分割服装区域
- 与 Stage 2 alpha 相交，去除非人物区域噪声
- 逻辑回退：锚点分割失败（mask 过小/过大）→ 用 alpha mask 躯干包围盒裁剪

### Stage 4 — 纯净服装合成
- 服装 mask ∩ 人像 alpha → 只保留服装像素
- 以 mask 包围盒加 8% 边距裁剪
- 输出：透明底 PNG + 白底 PNG；每个视频选 mask 清晰度/面积最优的前 3 张

## 实现物
1. `tools/garment_extract/workflow_garment.json` — ComfyUI API 工作流（LoadImage → BiRefNet → YOLO → SAM2 → 合成 → Save）
2. `tools/garment_extract/extract_garment.py` — 驱动脚本：ffmpeg 抽帧 → 提交工作流（单帧循环）→ 收集整理输出 → manifest
3. 运行方式：`python extract_garment.py "output/2026-10-11/instagram_ayano_fj" --top 3`

## 验收标准
- [ ] 两个视频各产出 ≥3 张纯净服装图（透明底 + 白底）
- [ ] 服装完整、无手臂/脸部/背景残留（人工抽检）
- [ ] manifest.json 记录来源可追溯
- [ ] 脚本可复用于其他视频目录

## 风险与对策
| 风险 | 对策 |
|---|---|
| 遮挡/侧身导致 SAM2 分割不完整 | Top-3 多帧候选兜底；manifest 记录 mask 面积便于筛选 |
| BiRefNet 把深色服装与背景混淆 | alpha 相交裁剪 + 多帧候选 |
| 多套服装出现在同一视频 | 按 mask 连通域分组输出（数量>1 时分别保存） |
