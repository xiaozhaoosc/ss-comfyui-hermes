# 新 Agent 接入指南（ComfyUI 工作区）

> 读者：即将接手本工作区任务的 AI Agent
> 配套档案：[SCRIPTS_INVENTORY.md](./SCRIPTS_INVENTORY.md)（全量脚本清单，动手前先查，避免重复造轮子）
> 更新时间：2026-10-10

---

## 1. 工作区在做什么

- 本机是 **16GB 显存** 的 ComfyUI 工作站（Windows），根目录 `d:\ai_projects\ComfyUI`
- 三条出片路线并行：
  - **本地 ComfyUI**（免费、慢）：H3 / Wan2.2 / Qwen-Image / Z-Image / FLUX
  - **Google Flow**（Veo 3.1，10 积分/镜，每日 100 熔断）：CDP 接管真实 Chrome
  - **Muse.ai**（720P 云端）：CDP 接管同一 Chrome
- 当前主线：《北宋杨家将》短剧流水线（EP01~EP03：九宫格分镜 → 切片 → 渲染 → 审计 → 三轨母带）
- 副线：Qwen 图片修复定稿、Wan Animate 动作迁移两段式、PC 出图评测矩阵

## 2. 环境入口（先记住这 4 个）

| 入口 | 地址 / 命令 | 说明 |
|---|---|---|
| ComfyUI API | `http://127.0.0.1:8188` | **必须绕代理访问**（HTTP_PROXY 会劫持成 502） |
| CDP Chrome | `tools\launch_flow_cdp_chrome.bat` | 9222 端口 + 独立 profile + 代理 7897；Flow/Muse 自动化的唯一入口 |
| ffmpeg | `C:\Users\kenzhao\scoop\apps\ffmpeg\8.1.1\bin\ffmpeg.exe` | 拼接/抽帧/混音全靠它（PATH 里通常也有） |
| nvidia-smi | `C:\WINDOWS\System32\nvidia-smi.exe` | 受限 shell 中不在 PATH，用完整路径 |

**CDP 接管原理**：bat 以 `--remote-debugging-port=9222` 启动独立 profile 的 Chrome；Agent 用 Playwright `connect_over_cdp("http://127.0.0.1:9222")` 附加到已运行实例，枚举 `contexts[0].pages` 操作已打开标签页。普通双击打开的 Chrome **无法**后补接管；同一 profile 禁止双开。

## 3. 常用任务的标准做法

### 3.1 云端出片（Flow 路线 A/B）
```powershell
# 1. 先启动 CDP Chrome（若未运行），人工完成一次 Google 登录（长期有效）
tools\launch_flow_cdp_chrome.bat
# 2. 自检接管状态
python tools/check_chrome_status.py
# 3. 提交前合规预检（Veo 知名人物政策会拦人名）
python tools/prompt_safety_linter.py
# 4. 跑路线（内置每日 100 积分硬熔断 + 账本 output/<日期>/flow_credit_ledger.json）
python tools/pipeline_route_a_flow_native.py        # 首帧直出
python tools/pipeline_route_b_moodboard_director.py # 九宫格情绪板导演流
```

### 3.2 本地批量出片（长任务）
```powershell
python tools/yangjiajiang_ep03_pipeline.py --submit-only   # 只提交，绝不轮询等待
python tools/comfy_sqlite_queue.py status                  # 查队列
python tools/comfy_sqlite_queue.py resume                  # 崩溃/重启后续跑
python tools/comfy_sqlite_queue.py backfill                # 回填绕过队列的历史产物
```

### 3.3 图片修复（Qwen 定稿链路）
```powershell
python tools/qwen_v4_submit.py restore --image <源图> --run --verify --lightning 8
# --verify 出图自动体检；--auto-grain ⑧不达标按 0.004→0.008→0.012 阶梯重试
# finalize_grain.py --sigma 1.5 仅作 fallback，正稿是 in-workflow 颗粒 0.008
```

### 3.4 动作迁移（两段式，服装可控）
```powershell
python tools/wan_stage1_redraw.py         # SDXL 重绘全身参考图（服装只能靠图像先验，提示词无效）
python tools/wan_stage1b_reactor.py       # ReActor 锁源脸到参考图
python tools/wan_batch_generate.py        # 按驱动视频帧数自动分块批量迁移
python tools/wan_stage3_facelock_video.py # 成片逐帧锁脸
python tools/wan_face_qa.py               # 身份一致性 QA（直连 RetinaFace，禁 torch）
```

### 3.5 质检与闸门
- 阶段切换前：`python tools/_drama_gate.py --proj <项目> --date <YYYY-MM-DD> --stage <assets|video|post>`（防资产不完整浪费积分）
- 视频逐镜审计：`comfy_shot_quality_auditor.py`；图片修复体检：`restore_qa.py`（**⑧纹理形态是最终裁决项**）
- 批量产物浏览：`flat_gallery.py <目录>`（已内置到批量脚本末尾，生成 `_gallery.html`）

## 4. 铁律（违反 = 翻车，均有真实教训）

1. **只提交不轮询**：长任务一律 `--submit-only` 提交后结束回合，完成靠后台通知/定时任务；历史 40+ 次轮询烧掉大量积分。
2. **单实例纪律**：16GB 卡上 ComfyUI 禁止双实例（卡死在 Model Initializing 的真实根因，T3 实验失败两次）。
3. **积分风控**：Flow 每日 100 credits 硬熔断；提交前必读 UI 实际成本 + 跑 linter。
4. **输出归档**：所有产物进 `output/<YYYY-MM-DD>/<项目名>/`，禁止散落。
5. **先落库再执行**：批量任务先入 SQLite 队列再提交，崩溃可续跑。
6. **挂首帧必须核验**：Flow Start Frame 曾"从未真正生效"（实为纯 t2v，画风漂移），用 `flow_frame_lock.py` 并核验生效。
7. **本机 API 绕代理**：8188 一律 `ProxyHandler({})`，否则 502。
8. **sd.py 补丁**：`comfy/sd.py` 有 Qwen-Image 手工补丁（`CLIPType.QWEN_IMAGE + QWEN3VL_8B` 的 prefix_replace），**ComfyUI 升级会覆盖**，升级后需重打；编辑必须用非 GGUF 编码器（GGUF 视觉塔形状错误）。
9. **敏感信息不出域**：不把本机路径/token/账号传到远程仓库。
10. **改脚本前先查清单**：tools/ 里同功能多代并存（探针→主引擎、v1→v2→v3），先查 `SCRIPTS_INVENTORY.md` 找现行版本，别在废弃脚本上叠加。

## 5. 常见坑速查（症状 → 处置）

| 症状 | 根因 | 处置 |
|---|---|---|
| ComfyUI 资产面板重启后为空 | 0.30 原生设计限制（只读内存历史） | 不是丢数据；用 Browser 插件画廊或 `flat_gallery.py` |
| 访问 8188 得到 502 | HTTP_PROXY 劫持 | 绕代理 opener |
| 任务卡 Model Initializing | 双 ComfyUI 实例争显存 | 杀掉多余实例，单实例重跑 |
| OOM（大图/长视频） | 整批张量过大 | 降采样再超分（ESRGAN 270x480 案例）、分块 32 帧（BiRefNet 案例）、`status_str=error` 快速失败 |
| Veo 拒绝生成 | Prominent People Policy | linter 前置审查，改写提示词 |
| 成片画风与首帧不符 | 首帧未挂载成功 | `flow_frame_lock.py` + 核验 |
| 拼接后丢音/叠影 | merge 未映射音频 / crossfade 残帧 | `-map [aout]` + acrossfade 0.3；过渡默认硬切 |
| 人脸"塑料感" | Pass2 扩散重绘平坦底 | 先测源图基线（磨皮图 flat≈0.64 属正常），⑧ < max(0.6, 源图-0.1) 才算塑料；in-workflow 颗粒修复 |
| 服装改不动 | WanAnimateToVideo 无服装输入 | 两段式：重绘参考图 → 锁脸 |
| PowerShell 下载大文件不可靠 | 输出/编码问题 | 用 `tools/_dl_weights.py`（断点续传+进度落盘） |
| 裁掉人体 / 裁错帧 | ImageScale crop=center；分块偏移硬编码 | 保持 9:16 比例；帧偏移递推 0,49,93…（Wan 输出比 length 多 4 帧 reference，裁前 4 帧） |

## 6. 会话纪律（与用户协作约定，user_confirmed）

- 后台任务完成会自动通知，**不做 sleep+check 循环**；必要时挂定时任务按递进间隔查（5min → +10min → +5h），完成即取消
- 小修复直接改，不开子代理；子代理只用于大块新代码，单任务 ≤1~2 个
- 巨型日志/JSON/traceback 用命令抽关键字段（`Select-Object -Last 5`），不整段读入上下文
- 一个大阶段完成后 `new_context` 交接（含后台任务清单、验收指令、关键路径）
- 渲染/训练提交后立即结束回合或转其他会话，跑片与对话解耦

## 7. 新任务决策树

```
要出视频/图片？
├─ 追质量 & 有积分 → Flow 路线A（单图）/ 路线B（风格统一）【linter → 熔断 → 下载核验】
├─ 免费本地 → 查清单选管线：
│   ├─ 视频 → h3_fast_submit(H3快) / yangjiajiang_*_pipeline(短剧) / wan 两段式(动作迁移)
│   └─ 图片 → qwen_v4_submit(修复) / _pc_gen.py(Z-Image 默认) / t2i_flux_v2
└─ 要相似动作 → 用户视频先 extract_full_poses → wan_batch_generate

改脚本 / 写新脚本？
└─ 先查 SCRIPTS_INVENTORY.md → 找现行版本复用 → 新脚本在清单对应日期分区登记一行

出结果后？
└─ 归档 output/<日期>/ → 质检(auditor/restore_qa/face_qa) → flat_gallery 浏览 → 重要结论回写项目记忆
```