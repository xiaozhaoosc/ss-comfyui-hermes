# 📋 待办清单 — 2026-10-11（近 3 天未完成事项汇总）

> **来源**：2026-10-09 ~ 2026-10-11 共 29 份工作文档的全量提取
> **上游地图**：[PROJECT_MAP.md](file:///D:/ai_projects/ComfyUI/PROJECT_MAP.md)
> **维护方式**：完成后请勾选并在行尾标注完成日期；跨天沿用请复制到新日期目录
> **共计**：🔴 P0 × 5 ＋ 🟡 P1 × 17 ＋ ⚪ P2 × 13
> **最新执行**：2026-10-12 —— P0-④ 已完成 ✅ ｜ P0-③ 已完成 ✅（23/23）｜ P0-① 已定位根因 🔍 ｜ P0-⑤ 关键帧缺陷**已修复并验证** ✅

---

## 一、🔴 P0 阻塞项（需优先处理）

| # | 事项 | 状态 | 说明 / 命令 | 来源 |
|---|---|---|---|---|
| 1 | **ComfyUI 服务器崩溃根因** | 🔍 **已定位** | 根因＝`comfy_aimdo` 版本错配（详见下方 A） | [服装提取](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_视频服装提取流水线.md) · [动漫短剧](file:///D:/ai_projects/ComfyUI/交接文档_动漫短剧本地落地_2026-10-11.md) |
| 2 | **轮换飞书 App Secret** | ⏳ 待处理 | App Secret 曾明文入库，**旧密钥视为已泄露**，需去飞书后台轮换 | `.workbuddy/memory/2026-10-11.md` |
| 3 | **WanAnimate 831959 片头裁剪剩余 19 条** | ✅ **已完成** | 2026-10-12 补齐 19 条，23/23 全部完成；帧数精确=原帧数−drop，19/19 无失败。质量核验 20/23 ≤1.8×，3 条偏高经查为近静态视频的比值假象（详见该文档 §3.2） | [831959 B方案](file:///D:/ai_projects/ComfyUI/交接_WanAnimate_831959换装视频_B方案全量批处理_2026-10-11.md) |
| 4 | **服装提取 stale 文件清理** | ✅ **已完成** | 24 个 `frame_*_gmraw.png` + 废弃 `workflow_pass1.json` 均已删除 | [服装提取 §7](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_视频服装提取流水线.md) |
| 5 | **仅换装视频：验证跑目检** | ✅ **缺陷已修复** | 根因＝Stage 4 不校验产物数 + Stage 5 静默用 `None` 插值；已加双重校验并实测修复 `wanB_00`（详见下方 B / C）。**铺量前仍需定服装分配策略** | [仅换装工作流](file:///D:/ai_projects/ComfyUI/仅换装视频工作流_交接文档_2026-10-11.md) |

### A. P0-① 根因结论：`comfy_aimdo` 版本错配 🔍

**症状**：ComfyUI 启动即崩，`ModuleNotFoundError: No module named 'comfy_aimdo.storage'`

**根因（已实证复现）**：`comfy/storage.py:7` 是无保护的硬导入 `import comfy_aimdo.storage`，而该子模块只在较新版本中存在：

| 环境 | `comfy_aimdo` 版本 | 含 `storage.py`？ | 能否启动 ComfyUI |
|---|---|---|---|
| `D:\ai_projects\ComfyUI\venv` | **0.5.6** | ✅ 有（还有 `malloc_graph.py`） | ✅ 可 |
| `C:\Users\kenzhao\anaconda3` | **0.4.11** | ❌ **无** | ❌ 崩于此 |

实测：`venv\Scripts\python.exe -c "import comfy_aimdo.storage"` → OK；`anaconda3\python.exe -c "import comfy_aimdo.storage"` → **ModuleNotFoundError**（复现成功）

诱因：`comfy/storage.py` 于 **2026-10-11 22:37** 刚被更新（随 v0.39.1 迁移），引入了这个新依赖要求。

**处置（二选一）**：
1. ✅ **推荐**：统一用 venv 启动 —— `start_comfyui_lowvram.bat` 已正确使用 `venv\Scripts\python.exe`，**不要再手工用 anaconda 起 ComfyUI**
2. 若必须用 anaconda：`C:\Users\kenzhao\anaconda3\python.exe -m pip install -U "comfy_aimdo>=0.5.6"`

**次要项（非致命）**：`comfy_kitchen` 亦存在版本偏斜（venv 0.2.33 / anaconda 0.2.26），报 `cannot import name 'AsymW4A8Int8Layout'`，但该异常被捕获，仅导致 fp8/fp4 支持不可用，不影响启动。

**✅ 进程链之谜已解开（2026-10-12）**：实测 `Get-CimInstance` 显示 **venv 进程(48464) 派生了 anaconda 子进程(5272)**，最终监听 8188 的是 anaconda 那个。原因应是 venv 启动时把自身 site-packages 传给了子进程，故 anaconda 子进程能取到 **venv 的 `comfy_aimdo` 0.5.6**。这解释了此前「anaconda 直连失败、但 venv 启动成功且监听者是 anaconda」的矛盾 —— **结论不变且更强：必须经由 venv 启动**，直接 `anaconda3\python.exe main.py` 必崩。

### B. P0-⑤ 换装验证目检结论 —— 关键帧缺陷已修复 ✅（2026-10-12 更新）

**样本**：`output/2026-10-11/outfit_only/wanB_00/wanB_00_outfit.mp4`（480×832 / 30fps / 263 帧 / 8.77s）

| 检查项 | 修复前 | 修复后 |
|---|---|---|
| 服装已换？ | ✅ 是（灰 NY 连衣裙 → 灰上衣+**白蕾丝束身衣**+白短裤） | ✅ 同左 |
| 关键帧完整？ | ❌ **9/10**，末帧未换装 | ✅ **10/10** |
| 片尾画面 | ⚠️ 只剩淡影、束身衣几乎不可见 | ✅ 束身衣**清晰渲染** |
| 人脸/闪烁 | ⚠️ 存疑 | 前 3 个时间点逐字节不变 → 属运动模糊，**已排除为缺陷** |

**结论：缺陷已修复，`wanB_00` 已重跑为完整版。** 剩余的「是否铺量 22 条」仍需先定服装分配策略（见主线 B）。

### C. 关键帧缺失缺陷 —— 根因与修复记录 🔧

**现象**：`4_swapped_kf` 只有 9 个，而 `kf_indices` 有 10 个；成片仍生成。

**根因**（[tools/pipeline_faceswap_outfit.py](file:///D:/ai_projects/ComfyUI/tools/pipeline_faceswap_outfit.py) 两处叠加）：
1. **Stage 4 `stage_outfit_swap`**：循环结束后**不校验实际文件数**就直接 `mark_done`，且 `n_swapped` 记的是 `len(kf_indices)`（**期望值**）。于是「跑到第 10 帧被中断」的残缺状态被标记为**成功**，状态文件骗过了后续阶段。
2. **Stage 5 `stage_interpolate`**：读关键帧时若文件缺失，`img` 为 `None` 仍被 `append` 进 `swapped_kf`，**静默参与光流插值**——不报错、不提示，只产出降质画面。

**旁证**：ComfyUI 原始产物 `output/outfit_kf_*` 只有 `kf_0000`–`kf_0008`，**不存在 `outfit_kf_0009`**；9 个产物时间戳 23:14:25→23:20:00（约 40s/帧），第 10 帧恰在中断点缺失——与「中断后被误判成功」完全吻合。

**修复内容**：
- Stage 4：循环后统计真实产物数，`!= len(kf_indices)` 即 **raise**（保留已有产物，便于重跑续传）；新增 `n_fallback_original` 计数，显式提示「有几个关键帧回退成了原帧（未换装）」——这正是潜在闪烁的来源。
- Stage 5：缺帧即 **raise** 并列出缺失文件路径，**绝不把 `None` 交给插值**。

**验证**（真实重跑 `wanB_00`，非仅语法检查）：
- 从 IDM-VTON 输出 PNG 的内嵌元数据**还原出原参数**：`garment_desc = "a white lace corset bustier top and white high-waisted slim pants"`、steps 15、seed 42、768×1024、`garment_ref1.png`
- 重跑 Stage 4–6：跳过已有 9 帧、补齐第 10 帧（Frame 262），校验通过，插值 263 帧、合成 mp4，总耗时 256s
- **哈希比对**（旧 vs 新，同时间点）：`0.3s` / `2.9s` / `5.8s` **逐字节相同**，`8.5s` 改变 → 证明修复**只影响尾部**、前段零扰动
- 目视：尾部由「淡影」变为「束身衣清晰」

**剩余**：`wanB_05` 仍待续跑（需 `ref2` + 取回其原 `garment_desc`）。

### D. `wanB_05` 续跑 —— ✅ 已就绪，可立即执行（2026-10-12 09:41 队列已空）

**前置已齐备**：`2_frames` 441 帧、`3_masks` 16 个、`4_swapped_kf` 0 个（Stage 4 从未跑过），状态停在 `2_extract`/`3_masks` done。

**阻塞已解除**：昨夜占满队列的 `output/2026-10-12/hitomi_batch/` ReActor 批处理（峰值 pending 约 290）今晨队列已空（`running=0 pending=0`）。⚠️ 但该批 **mp4 产物为 0**，疑似任务被清空/取消，**需向相关同事核实去向**。

**⚠️ 仅剩业务前提**：服装分配策略（ref1/ref2 ↔ 22 视频）确认后即可跑；单跑 `wanB_05` 用 ref2 无依赖。命令（`_trim` 优先，参数已与原验证跑对齐）：

```powershell
$env:PATH = "C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin;" + $env:PATH
D:\ai_projects\ComfyUI\venv\Scripts\python.exe -u tools\pipeline_faceswap_outfit.py run `
  --video  "output\2026-10-11_wb\wanB_05__你来与不来我都在等你_00001__trim.mp4" `
  --skip-faceswap `
  --garment "output\2026-10-11\outfit_only\garments\garment_ref2.png" `
  --garment-desc "a red and pink chinese hanfu style top with scalloped petal sleeves, pink sash and green floral embroidery" `
  --output-dir  "output\2026-10-11\outfit_only\wanB_05" `
  --output-name "wanB_05_outfit.mp4" `
  --keyframe-interval 1.0 --steps 15 --protect-expand 5 --feather 3 --comfy-port 8188
```

> ⚠️ **`--garment-desc` 是「重建值」，非原始值**：wanB_05 的 Stage 4 从未跑过，ComfyUI 输出目录里没有任何 `outfit_kf_*` 产物，原描述**无法从元数据还原**（其原图 `garment_ref2.png` 又被内容策略拦截、无法读取）。上述描述是我依据 `sheet_ref2.png` 速览图目视重建的（红/粉汉服风交领上装、花瓣袖口、粉腰带、绿花刺绣）。
> **因 Stage 4 是全新运行、16 个关键帧会统一使用同一描述，不存在新旧帧不一致的问题**；但描述与原始值若有差异，成片观感可能与预期略有出入 —— 建议跑完目检，必要时调整描述重跑（结果可整体重算，不受影响）。




---

## 二、🟡 P1 高优先级

### 主线 A：《北宋杨家将》短剧
- [ ] **人工验收 EP01/05/06/07 速览图** —— 重点看 EP06 grid5、EP07 grid1、EP01 grid1，不满意可单组重抽（[EP01-07 前期](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_YANGJIAJIANG_EP01-07_PREPRODUCTION.md)）
- [ ] **确认七郎归宿** → 据此决定 EP04 结尾字幕「七子去，六子回」是否保留（[EP04 剧情修复](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_杨家将前四集镜头切片对比与EP04剧情一致性修复.md)）
- [ ] **EP04 两张可视化对照卡落盘** —— 目前仅会话内联渲染，需生成 HTML/PNG 存入 `output/2026-10-11/`
- [ ] **obsidian 归档文件复制** —— 当前不存在，需按该文档 §8 执行复制命令
- [ ] **更正资产清单口径** —— EP02/03/04 首帧在 `input/`，output 为视频产物
- [ ] **清理旧图备份** —— EP01、EP06 各 1 个 `grids/*.prev_*.png`
- [ ] **补推 EP03 剩余镜头** —— Shot03~09（用 `tools/yangjiajiang_ep03_metadata.py` + 去名化），余 80 积分 = 约 8 镜
- [ ] **EP03 全幕大总成** —— 复用 `pipeline_route_a_postprocess_relay.py`
- [ ] **新集数登记** —— 在 `tools/SCRIPTS_INVENTORY.md` 单独登记

### 主线 B：换装视频
- [x] **🐞 修复关键帧缺失缺陷** —— 已完成（2026-10-12）。根因：`stage_outfit_swap` 循环完成后**不校验实际产物数**就 `mark_done`（`n_swapped` 记的是期望值），中断残留被当作成功；下游 `stage_interpolate` 又把缺失帧**静默 append 成 `None`** 参与插值。已加双重校验（Stage 4 数量不符即 raise；Stage 5 缺帧即报错并列出路径）+ 回退计数。**实测修复 `wanB_00`**：补齐第 10 帧，前 3 个时间点逐字节不变、仅尾部改变且明显变好（详见 §C）
- [ ] **🐞 续跑 `wanB_05`** —— **已就绪，被外部批处理阻塞**（2026-10-12 核实）。前置齐备（441 帧 / 16 遮罩 / Stage 4 未跑）；原 `garment_desc` 无法还原，已依速览图重建；**因 ComfyUI 队列被 290 个外部 ReActor 任务占满而暂缓**。可复现命令见 **§D**
- [ ] **视频级闪烁复核** —— ~~静帧 2.9s 束身衣不可见~~ 经复核**该帧修复前后逐字节相同**，属运动模糊而非缺陷（已排除）；如需进一步确认建议做整片逐帧差分
- [ ] **确定服装分配策略** —— 2 套服装映射 22 个视频，**需向需求方确认**
- [ ] **清理 `wanB_02~13` 旧版预跑产物** —— 间隔 2.0 版本，与当前 1.0 不兼容
- [ ] **确认 WanAnimate B 方案 22 条是否全跑完** —— 起服务后查 `/history` 或 `output/2026-10-11/`，未完成的用 `tools/trim_opening.py --auto` 收尾
- [x] **裁剪后质量抽查** —— 已完成（2026-10-12）：23/23 生成 `_trim.mp4`，帧数/音画核验通过；3 条比值偏高的已查明为近静态视频假象。仅 `wanB_15` 建议人工瞄一眼
- [ ] **[可选] 归档重命名** —— 去掉内部索引 / `_00001` 后缀

### 主线 C：动漫短剧
- [ ] **打通「角色资产→分镜→视频」闭环（Step4/5）** —— 前置：`_checkv.py` 目录硬编码旧路径需重写
- [ ] **LoRA 接入** —— `char_ref.json` 的 `lora` 字段已预留，`_pc_gen_sd15.CONFIG` 未配 lora 路径
- [ ] **资产表质量阈值校验** —— 接入 `tools/_drama_gate.py` 的 `assets` 关卡（目前仅查存在性）
- [ ] **多角色批量自动化** —— 当前为单角色串行

### 主线 E：出图质量评测（收尾）
- [ ] **生成 lora_ab 对比拼图** —— `make_pc_matrix_sheet.py` 加组
- [ ] **写实 LoRA 权重试 0.5–0.6**
- [ ] **Qwen-Image 2.1 色彩曝光核查** —— 疑点 1.65/1.64
- [ ] **Qwen 提速** —— 560s/张 → 试 Q5/Q6 量化或更换 TE
- [ ] **修 P5 `EVAL_DIR` 按天分裂**
- [ ] **回填五模型最终版报告**
- [ ] **重跑补齐 1 个损坏 PNG** —— `output/2026-10-08/qwen21_2k/阳光户外淋浴九宫格人像_R2C3_06_2k_00001_.png`（Qwen 有效 53/54）

### 主线 F：基础设施
- [ ] **SQLite 队列 Web 界面验证** —— 启动 `start_comfyui.bat` 走通 Browser 按钮画廊
- [ ] **存量脚本接入 `enqueue_task`** —— `yangjiajiang_*.py` / `batch_faceswap.py`
- [ ] **Hitomi 安全清理** —— 删除含 sessionid 的 `D:\instagram_cookies.txt`、`instagram.txt`、`instagram2.txt`
- [ ] **Hitomi 逐站实跑** —— 抖音/TikTok/Facebook/X 目前仅确认「支持」，未逐站验证

### 主线 D：服装提取
- [ ] **人工复核全部 12 张 Top-3** —— 本次仅目检每视频 top1，rank2/rank3 未逐张确认（[服装提取 §7](file:///D:/ai_projects/ComfyUI/HANDOVER_2026-10-11_视频服装提取流水线.md)）
- [ ] **`local_garment.py` 参数化** —— `--top` / `--frames` / `--fps` 目前硬编码

---

## 三、⚪ P2 一般 / 优化

- [ ] **服装提取：失败帧日志落盘** —— 输出 `errors.jsonl`（当前仅打印 stdout）
- [ ] **服装提取·多套服装自动分离输出** —— 按连通域分组，各自裁剪命名
- [ ] **服装提取·过渡帧前置过滤** —— 帧间差异剔除场景切换帧（从源头避免碎片）
- [ ] **服装提取·半透明布料 alpha 保真** —— 输出软 alpha，还原透视纱质感
- [ ] **服装提取·服装平铺矫正** —— 姿态估计后 warp 到正面平铺视图
- [ ] **服装提取·批量目录递归** —— 一次处理 `output\*\instagram_*`
- [ ] **服装提取·PBR 辅助图** —— 法线/深度/粗糙度贴图
- [ ] **补验 `faceswap_tryon_combo_v1`** 换衣闭环
- [ ] **清理垃圾文件** —— 早期失败 run 产物、`wanB_05` 残留
- [ ] **WanAnimate 归档重命名** —— 去掉内部索引 / `_00001`
- [ ] **分块接缝 ColorMatch 色彩一致性**
- [ ] **成片输出前加超分 / CodeFormer 后处理**
- [ ] **视频流水线前置合规审查器** —— 敏感词正则字典（Flow 提审前拦截）
- [ ] **失败自愈重试 + 废卡清理** —— `clean_failed_card.py`（方案已提，未落地）
- [ ] **精选取舍后缝 4K/6K 九宫格** —— 并做 1~2px 羽化重叠
- [ ] **技能：`comfyui-imagegen` 底模授权** —— Flux2 Klein 9B 返回 401，需 HF 接受协议 + token，或换公开 4B
- [ ] **新建跨集剧情连续性校验器** —— 建议 `yangjiajiang_canon.json` 单源 canon + 脚本化校验，防设定漂移
- [ ] **可视化 / 台账产物落盘标准化** —— 内联卡片无法交付，改为生成自包含 HTML/PNG；`asset_manifest.md` 改脚本生成

---

## 四、🗓️ 已明确路线（非阻塞，按计划推进）

| 路线 | 内容 | 节奏 |
|---|---|---|
| **EP08~EP24 续产** | 共 17 集；EP08《汴京审潘》可直接开跑 | 逐集约 30 分钟 / 0 积分 |
| **换装视频铺量** | 22 条视频（P0-5 验证通过后） | 依赖验证结论 |
| **Muse.ai 解封** | 额度耗尽，封存至 **10-15** 重置 | 到期复查 |
| **Flow 积分排期** | 每日 100 分硬上限；EP03 余 80 分 | 账本 `flow_credit_ledger.json` |

---

## 五、🧹 本轮已完成（供对照，避免重复劳动）

- [x] 服装提取流水线 v5 交付：4 视频 × Top-3（24 张 PNG），48/48 帧无失败 — 2026-10-11
- [x] EP03 母带交付：720P/24fps/214.04s/111.96MB + 5 幕成片 — 2026-10-10
- [x] EP04 剧情一致性修复 4 处，综合评分 9.8 — 2026-10-11
- [x] Wan2.2 Animate 动作迁移链路 Production Ready（DWPose 提速 1400ms→39ms）— 2026-10-10
- [x] ComfyUI SQLite 队列持久化（4 项测试 100% PASS）— 2026-10-10
- [x] 831959 B 方案 23/23 渲染完成 — 2026-10-11
- [x] Google Flow SOP v1.0 + Veo 自动化方案沉淀 — 2026-10-10
- [x] 动漫短剧角色资产链路端到端打通（4 套资产表）— 2026-10-11
- [x] EP03 本地 54 镜画质审计：合格率 100% — 2026-10-09

---

## 六、⚠️ 已知口径冲突（接手时注意）

1. **出图耗时**：`45 秒/张`（技能台账/出图脚本）与 **稳态 21s**（交接文档修正）不一致 —— 以交接文档为准
2. **皮肤 LoRA**：四模型报告提出「Z-Image 需皮肤补偿」，但 10-10 交接文档 **实测证伪（LoRA 无效）** —— 不要重复投入
3. **IG 下载器状态**：动漫短剧文档记「已建成可用」，服装提取文档记「ComfyUI DOWN 为唯一阻塞」—— 二者不矛盾（本地直连推理不受影响），但解释器不同：`ig_download.py` 用 `.workbuddy/envs/default`，`local_garment.py` 用 `D:\ai_projects\ComfyUI\venv`
