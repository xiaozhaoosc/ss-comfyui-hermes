# 动作迁移终局交接文档（2026-10-15）

> 本文档是「实拍舞蹈视频 → 参考人物动作/表情/身份复刻」项目的**最终交接**。
> 覆盖：架构定论、A/B 双路线全部实测数据、三处静默失效 bug 的完整复盘、工具链使用手册、复现步骤、已知限制与下一步。
> 历史过程文档：`docs/v6_routeA_fix_and_dual_white_model.md`（A 路线修复与双人白模）、`docs/HANDOVER_DOCUMENT_WAN_ANIMATE_MOTION_TRANSFER_2026-10-10.md`（B 路线早期）。

---

## 0. 一页结论

1. **A 路线（H3 ref2va + 白模法线）已被救活**：修复两处静默失效 bug 后，158 帧 / 6.6s 样片**首次通过全部五道闸门**（动作 traj 0.624 / turn 0.526 / pose_err 0.114 + 身份 0.563 + 表情 0.782/0.875/0.085）。
2. **B 路线（Wan2.2 Animate ours 模式）仍为最强正解**：全长 11.4s 母带全项 PASS，且身份 0.918 远强于 A 的 0.563。
3. **架构定论（user confirmed）**：身体动作走骨架/法线（白模本职）；表情走独立面捕通道（DWPose face70）+ 原生音频轨；**微表情塞不进法线/白模**（MoGe 平滑掉毫米级起伏，视线/眨眼/牙齿非表面几何）。
4. **本项目最大教训 = 三处静默失效**：条件"提交成功"≠"被消费"。只有客观闸门（动作/身份/表情）能判定产物真伪，肉眼与文档声明都不可信。
5. A/B 均已交付可直接使用的提交器 + UI 工作流 + 验收工具，见 §4。

---

## 1. 最终验收数据（五道闸门对照表）

### 1.1 现役产物

| 产物 | 帧数/画幅 | 动作 traj≥0.50 | turn≥0.50 | pose_err≤0.30 | 身份 cos≥0.50 | 表情 traj/active≥0.50, err≤0.35 | 判定 |
|---|---|---|---|---|---|---|---|
| **B 母带 v2**（Wan ours，7 窗合并+49/53 重定时+回灌音频） | 341f / 544×960 / 30fps | **0.693** | **0.566** | **0.087** | **0.918** | **0.736 / 0.794 / 0.084** | **全 PASS（正解）** |
| **A 调优片 tune1**（H3 SelfLift，白模法线双通道） | 158f / 544×960 / 24fps | **0.624** | **0.526** | **0.114** | **0.563**（压线，均值 0.451） | **0.782 / 0.875 / 0.085** | **全 PASS（复活）** |
| A 旧全长片（扁平键已修，1 帧坍缩未修） | 277f / 0.3MP | 0.246 | 0.399 | 0.139 | 0.366 | 0.472 / 0.551 / 0.110 | 全 FAIL |

产物路径：
- B：`output/2026-10-13/motion_optimize/jia_wan_full_master_v2.mp4`
- A（新）：`output/2026-10-14/motion_optimize/h3_selflift_tune1/jia_selflift_00001-audio.mp4`（QA 结果同目录 `qa_motion.json` / `qa_face.json`）
- A（旧）：`output/2026-10-14/motion_optimize/h3_selflift_full/jia_selflift_00001-audio.mp4`（`qa_face.json` 为本轮补测）

### 1.2 A 路线历史失败轮（供对照，全部已被 §3 的 bug 解释）

| 轮次 | 配置 | traj | 身份 | 失败真因 |
|---|---|---|---|---|
| v1（4步简化链） | 法线直喂 CN 0.45 | 0.085 | 0.207 | ① Autogrow 嵌套键被丢弃 ② 1 帧坍缩 |
| v2（8步+双LoRA） | 白模 ref + CN 0.6 | 0.040 | 0.152 | 同上 |
| v3（SelfLift 完整链） | 73 帧隔离矩阵 T1~T3 | 0.036~0.18 | 0.086~0.18 | Autogrow 嵌套键（T1/T4b 单变量实锤） |
| v3 全长 | 277f 扁平键、real ref | 0.246 | 0.366 | 1 帧坍缩（control_video 仍是单帧广播） |
| **v3 调优** | **158f + 白模 ref + CN0.6/0.9 + 0.5MP** | **0.624** | **0.563** | **无——全 PASS** |

### 1.3 关键行为差异（A vs B）

| 维度 | A（H3 ref2va） | B（Wan2.2 Animate） |
|---|---|---|
| 时间对齐 | **与源逐帧 1:1**（对齐搜索 +0 最优，无时间膨胀） | 有时间膨胀（49 控制帧→53 产物帧），需重定时 |
| 音频 | **直出自带**（音频 latent 组 + LTXVConcatAVLatent） | 需 ffmpeg 回灌源音频 |
| 渲染方式 | 单次直出（157 帧一段） | 7 窗分段渲染 + 合并 |
| 身份强度 | 0.563（短板） | **0.918** |
| 显存压力 | 高（SelfLift 双阶段，16GB 需 ≤0.5MP） | 中（ours 模式 544×960 稳定） |
| 表情来源 | ref2va 语义条件（间接） | ours 模式 face 通道（DWPose face70 显式驱动） |

---

## 2. 架构定论（user confirmed，2026-10-14）

```
源表演视频（runcha_dance.mp4）
   │
   ├─ 身体通道 ── DWPose body+hand 骨架 / BiRefNet 抠图+MoGe 法线（白模）
   │                └─ A: FunControlNet(control_video) + ref_video 几何语义
   │                └─ B: Wan Animate ours 模式 pose 通道
   │
   ├─ 表情通道 ── DWPose face70 构型（嘴/眼/眉）
   │                └─ B: ours 模式 face 通道（显式）
   │                └─ A: ref2va 语义条件（间接，实测也能跟上，0.782）
   │
   └─ 音频通道 ── 源音频轨
                    └─ A: 音频 latent 组（直出）
                    └─ B: 成片后 ffmpeg 回灌
```

**为什么微表情进不了法线/白模**：MoGe 单目几何会把毫米级皮肤起伏平滑掉；视线方向、眨眼、牙齿张合根本不是"表面几何"能编码的内容。表情复刻必须走关键点/面捕通道，验收必须用 `face_expression_qa.py` 比对面部构型时序。

**双人场景**：BiRefNet 与 MoGe 均为整帧模型，一次推理同时输出两人法线，零额外适配；白模素材（Aiden 原版视频里的双人白模）本身是外部 3D 绑骨成品，工作流只负责"实拍→白模法线"转换。

---

## 3. 三处静默失效 bug（血泪复盘，务必先读）

### 3.1 Autogrow 输入键格式（影响：所有历史 A 提交）
- **现象**：ref_video / ControlNet / 身份"全部无效"，产物≈随机 + 身份崩坏。
- **根因**：`MiniMaxH3ReferenceToVideo` 的 V3 动态输入（`ref_images` / `ref_videos` / `ref_video_audios`）在服务端要求**扁平点号键**（`ref_videos.ref_video_0`）；写成嵌套字典 `{"ref_video_0": [...]}` **被静默丢弃且不报错**。
- **实锤**：单变量 T1（嵌套）vs T4b（扁平，其余全同）→ 产物 MD5 不同，traj 0.036→0.363。
- **规则**：V3 动态输入一律扁平点号键。

### 3.2 ImageCompositeMasked「1 帧坍缩」（影响：所有带 CN 的 A 提交 + 本 UI 工作流）
- **现象**：白模 ref_video 报 `reference videos need at least 5 frames`；strength 0.45→0.9 调参毫无改善。
- **根因**：[nodes_mask.py](file:///d:/ai_projects/ComfyUI/comfy_extras/nodes_mask.py#L12-L47) 的 `composite()` **返回 destination**，输出批长 = destination 批长（source 被 `repeat_to_batch_size` 广播对齐）。灰底用 `SolidMask→MaskToImage` 只有 1 帧 → 白模支路（抠图→MoGe→合成）整条坍缩成 1 帧 → control_video 实为"单张图广播到整段" = 静态约束，逐帧几何控制从未生效。
- **修复**：灰底改 `EmptyImage(width, height, batch_size=帧数, color=0x878787)`（`tools/run_h3_selflift_transfer.py` 已改，节点 39→38）。
- **规则**：替换批量运算节点必须核对**输出批长语义**。

### 3.3 「冒烟 completed ≠ 生效」（方法论）
- 两轮"渲染成功、画面正常"的提交，闸门一跑全是随机水平。**新工作流/新配置必须过全长客观闸门**；定位静默失效最快的方法是**单变量 + 产物 MD5 对比**的隔离矩阵。
- QA 性能：两个 QA 进程并行会因 DWPose GPU 争用互相拖慢 4~5 倍 → **必须串行**；`--every 2` 隔帧抽取在 96 时间桶下无指标损失、耗时减半。

---

## 4. 交付物清单

### 4.1 产物视频
| 文件 | 说明 |
|---|---|
| `output/2026-10-13/motion_optimize/jia_wan_full_master_v2.mp4` | **B 母带（正解）**：341f/544×960/30fps/11.4s，全闸门 PASS |
| `output/2026-10-14/motion_optimize/h3_selflift_tune1/jia_selflift_00001-audio.mp4` | **A 复活样片**：158f/544×960/24fps/6.6s，全闸门 PASS，直出带音频 |

### 4.2 提交器（API 构建器，可参数化复现）
| 脚本 | 路线 | 要点 |
|---|---|---|
| `tools/run_h3_selflift_transfer.py` | A | 完整 Aiden 链 38 节点：SelfLiftAvatarH3TST(0.2) + SelfLiftAvatarH3Sampler(6/8 双阶段) + FunControlNet + 音频 latent 组；**扁平点号键** + **EmptyImage 批长灰底**（两处修复都在内）；缺失插件用本机等价物替代 |
| `tools/motion_clone/render_wan_animate.py --pose-mode ours` | B | pose=身体+双手 / face=仅脸 双通道输出；internal 模式画幅跟随目标分辨率 |

### 4.3 UI 工作流（手工操作入口，各存 `workflows/` 与 `user/default/workflows/` 两份）
| 文件 | 路线 | ⚠️ 注意 |
|---|---|---|
| `motion_transfer_B_wan_animate_9x16_ui.json` | B | 可直接用 |
| `motion_transfer_A_h3_controlnet_normal_ui.json`（及 `workflows/v6/h3_controlnet_normal_motion_ui.json`） | A | **仍带 1 帧坍缩 bug**（SolidMask 灰底），手工跑 A 请用提交器；便签已写明 |

### 4.4 验收工具
| 脚本 | 闸门 | 阈值 |
|---|---|---|
| `tools/motion_fidelity_qa.py` | 动作三项 + 身份 | traj≥0.50 / turn≥0.50 / pose_err≤0.30 / 身份 cos≥0.50（自检 4/4） |
| `tools/face_expression_qa.py` | 表情三项 | face_traj≥0.50 / active≥0.50 / face_err≤0.35（自检 3/3；本轮新增 `--ref-window`） |
| `tools/wait_prompt.py` | （辅助） | 挂后台等 prompt 完成，成功 0 / error 1 / 超时 2 |

### 4.5 模型与插件（均已就位，无需下载）
- `models/model_patches/`：FunControlNet union 2.0（4.53GB）、MoGe、BiRefNet、双 LoRA（Motion_Repair_V2 + DMAD）、h3_upscaler_lms
- `custom_nodes/selflift-Avatar`（SelfLiftAvatarH3Sampler / H3TST / ImageSampler）
- H3 主模型：`minimax_h3_ref2va_pruned_int8_convrot` + `qwen3vl_32b_minimax_h3_int8_convrot` + 视频/音频 VAE

---

## 5. 工具使用手册

### 5.1 A 路线提交器
```powershell
d:\ai_projects\ComfyUI\venv\Scripts\python.exe tools\run_h3_selflift_transfer.py `
    --length 157 --mp 0.5 --steps 8 --transition-step 6 `
    --cn-strength 0.6 --cn-end 0.9 `
    --ref-video-mode white_model --prompt-mode natural `
    --tag h3_selflift_tune1
```
参数速查：
- `--length`：帧数，**必须 17n+5**（H3 内部会向下取整到该形式；73/157/277 可用，277=17n+5 但 0.5MP 显存未验证）
- `--mp`：画幅（0.3=416×736 保守；0.5=544×960 已验证 158 帧）
- `--cn-strength / --cn-end`：0.6 / 0.9 为验证过的组合（0.45/0.75 偏弱）
- `--ref-video-mode white_model|real`：白模法线（正解）/ 原始视频（隔离实验用）
- `--prompt-mode natural|geometry`：natural 描述舞蹈语义；geometry 的白模描述会污染身份，勿用
- `--no-controlnet` / `--dump-api` / `--dry-run`：实验开关
- 长任务只提交不轮询：拿 `prompt_id` 后 `python tools\wait_prompt.py <prompt_id>`

### 5.2 验收闸门（串行！GPU 单实例）
```powershell
# 动作四闸门（窗长 = 产物帧数/产物fps×源fps；源 keypoints 已有则用 --ref-kp 免重复抽骨架）
venv\Scripts\python.exe tools\motion_fidelity_qa.py `
    --ref-kp output\2026-10-13\motion_optimize\ref\keypoints.json `
    --ref-window 0:197 --ref-search 6 --smooth `
    --cand-video <产物.mp4> --identity-ref input\jia_ref.jpg `
    --every 2 --json <产物目录>\qa_motion.json

# 表情三闸门
venv\Scripts\python.exe tools\face_expression_qa.py `
    --ref-kp output\2026-10-13\motion_optimize\ref\keypoints.json `
    --ref-window 0:197 `
    --cand-video <产物.mp4> --every 2 --json <产物目录>\qa_face.json
```
要点：
- **窗长换算**：产物 N 帧 @24fps ↔ 源 30fps → 窗长 = N/24×30（158 帧→197；277 帧→346）。不给窗则两边都全长重采样，时间轴错位比对无效。
- `--ref-search 6`：±6 帧对齐搜索（B 有时间膨胀必须开；A 实测 +0 最优，开了也无害）。
- `--smooth`：两侧同参数卡尔曼平滑，统一口径（推荐恒开）。
- 自检：`--self-test` 离线跑，不占 GPU。

### 5.3 B 路线复现（概要）
1. `render_wan_animate.py --pose-mode ours` 生成骨架/脸控制视频（544×960）
2. 按 7 窗分段提交（每窗 length=49，实产 53 帧）
3. 合并 + 裁头 3 帧 + 49/53 重定时 + ffmpeg 回灌源音频
细节见 `docs/HANDOVER_DOCUMENT_WAN_ANIMATE_MOTION_TRANSFER_2026-10-10.md` 与 B UI 工作流便签。

---

## 6. 复现步骤（从零到验收，以 A 路线为例）

1. **前置检查**：ComfyUI 8188 在跑（`--lowvram`）；`/queue` 为空；`tools\run_h3_selflift_transfer.py --dry-run` 无缺失节点。
2. **提交渲染**：§5.1 命令 → 记下 `prompt_id`。
3. **后台等待**：`venv\Scripts\python.exe tools\wait_prompt.py <prompt_id>`，完成自动通知。
4. **验收**：§5.2 两条命令（先动作后表情，串行），看最终判定行。
5. **判定标准**：五项全 OK = 可交付；任何一项 FAIL = 回到 §3 排查（先怀疑键格式/批长，再怀疑调参）。

---

## 7. 已知限制与下一步

1. **A 全长母带未做**：277 帧 @0.5MP 的 SelfLift 显存未验证（16GB 风险高）。两条路：① `--mp 0.3` 跑 277 帧（保守，画质降）；② 分段渲染后拼接。**当前 A 样片仅 6.6s**，交付全长正解仍用 B。
2. **A 身份 0.563 压线**（均值 0.451）：max-cos 判定达标但余量小。可试方向：提高 ref_image 分辨率/质量、`ref_image_size` 调整、negative prompt——但每次改动必须重新过全套闸门。
3. **表情/口型上限**：A 的表情走语义条件（间接）；若要求口型逐音素对齐，用 B（face 通道显式驱动）。
4. **双人白模**：方案已在 `docs/v6_routeA_fix_and_dual_white_model.md`，整帧一次推理即可，无需拆分。
5. **UI 版 A 工作流**待按提交器重构（EmptyImage 批长灰底 + SelfLift 双阶段节点），当前以提交器为准。

---

## 8. 教训汇编（写给下一个人）

1. **"提交成功"≠"输入被消费"**：V3 Autogrow 用扁平点号键；嵌套字典静默丢弃。任何"条件无效"先查键格式。
2. **复合节点有隐藏批长语义**：`ImageCompositeMasked` 返回 destination，单帧 destination 会把整条支路压成 1 帧，且多数场景不报错。
3. **一切以客观闸门为准**：动作/身份/表情三套闸门是这个项目最值钱的资产；肉眼、文档声明、历史"成功"记录都不可信。
4. **定位静默失效 = 单变量隔离矩阵 + 产物 MD5 对比**，比任何猜测都快。
5. **GPU 任务单实例串行**：QA 并行因 DWPose 争用慢 4~5 倍；长任务只提交 + 后台 waiter 通知，不轮询。
6. **图像/视频处理一律 GPU 优先**（user 规则）：DWPose CUDA、insightface CUDAExecutionProvider、MoGe/BiRefNet 由 ComfyUI 自动 GPU。
7. **部分时长产物验收必须做时间窗对齐**（`--ref-window`，窗长按帧率换算），否则归一化时间轴错位、比对无效。

---

## 9. 文件索引

- 提交器：`tools/run_h3_selflift_transfer.py`（A）／`tools/motion_clone/render_wan_animate.py`（B）
- 闸门：`tools/motion_fidelity_qa.py`／`tools/face_expression_qa.py`／`tools/wait_prompt.py`
- QA 结果 JSON：`output/2026-10-14/motion_optimize/h3_selflift_tune1/{qa_motion,qa_face}.json`、`output/2026-10-14/motion_optimize/h3_selflift_full/qa_face.json`
- 源骨架：`output/2026-10-13/motion_optimize/ref/keypoints.json`（347 帧 @30fps，body18+hand21×2+face70，卡尔曼平滑）
- UI 工作流：`user/default/workflows/motion_transfer_{A_h3_controlnet_normal,B_wan_animate_9x16}_ui.json`
- 脚本台账：`tools/SCRIPTS_INVENTORY.md` §十/§十一B/C/D（含全部修复记录）
- 项目记忆：`A 路线复活终局（2026-10-15）`章节
