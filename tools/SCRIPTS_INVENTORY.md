# tools 目录脚本清单（Script Inventory）

> 生成时间：2026-10-10 ｜ 来源：文件系统时间戳 + 脚本 docstring + 项目记忆档案
> 维护方式：新脚本入库时在对应日期分区追加一行；出问题/修复后补填后两列
> 列说明：`—` = 无记录/不适用（按约定允许留空）
> 说明：10 月分区为全列详表；9 月及更早为紧凑表（该时期仅个别脚本有档案，其余列留空）
> 探针/一次性试验脚本按系列合并成行（文件名全部列出，可 Ctrl+F 查找）

---

## 总览

| 分区 | 行数(含合并) | 主题 |
|---|---|---|
| 2026-10-11 | 2 | **EP04 前期准备**：54 镜元数据表 + Flow 九宫格生成/切片器 |
| 2026-10-10 | 21（上午 8 + 午后晚间 13 组） | Flow 路线A/B 引擎与积分熔断、shot02 端到端、首帧锁定、合规 linter、Wan 两段式、PC 评测矩阵、扁平画廊 |
| 2026-10-09 | 14 | SQLite 断点续跑队列、EP03 管线/审计/母带、Flow×Muse 双平台评测、切片定稿 |
| 2026-10-08 | 9 | EP02 全链路、全片动作迁移、CDP Chrome 入口、Flow CDP 试点 |
| 2026-10-01~07 | 24 | H3 快速/增强/分段提交、图片修复体检、EP01 管线、动作迁移、字幕 |
| 2026-09 | 55+ | H3 单片系列、LoRA 数据集、守护进程、fp8/写真批量 |
| 2026-08 及更早 | 140+ | 换脸/试衣/僵尸批量、模型下载、LTX 测试、头像冒烟、运维 |
| 子目录 | 14 | ootd_study / motion_clone / workflows 等 |

---

## 〇、2026-10-11

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 使用场景 | 依赖前提 | 限制 | 扩展方向 | 优化方向 | 后续规则 | 存在过的问题 | 修复记录 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| yangjiajiang_ep04_metadata.py | 10-11 | 10-11 | EP04《邠阳城·血》54 镜元数据表（6 幕 / 6 组九宫格 / 214.0s，含 sub/tag/visual/camera/sfx/bgm） | EP04 出片数据源（被管线/切片脚本 import） | 纯数据模块，无外部依赖 | 剧情按连环画册2 页38-74；切分表原为 34 镜，本表按既有 54 镜范式扩写 | 可参数化集数 | — | 新集数沿用 54镜/6组/214s 范式 | — | 自检通过（镜号连续、总时长 214.0s、6×9=54、字段完整）；同日修复 4 处剧情断点（开篇年份/文案、韩延寿左臂旧伤、二郎殒身镜、三旗归属） |
| yangjiajiang_ep01_metadata.py ／ yangjiajiang_ep05_metadata.py | 10-11 | 10-11 | EP01《北汉风雪》/ EP05《误卯牌》54 镜元数据表（54镜/6组/214.0s，与 EP04 范式完全对齐） | EP01/EP05 出片数据源 | 纯数据模块 | EP01 由旧 41镜/16:9 范式重制为 54镜/9:16；EP05 依据册3 页1-35 新建（切分表 31 镜扩写） | — | — | 新集数沿用 54镜/6组/214s 范式 | — | 自检通过（各 54 镜 / 214.0s / 6×9） |
| yangjiajiang_ep06_metadata.py | 10-11 | 10-11 | EP06《李陵碑·殉国》54 镜元数据表（54镜/6组/214.0s，由 EP05 流水线同范式生成；朱砂全片三处之一，仅镜43撞碑「黑白与一点朱砂」） | EP06 出片数据源 | 纯数据模块 | 依据册3 页36-70 新建（切分表 31 镜扩写 + OCR 3-64~3-70 增补芦林认尸/葬父断戈） | — | — | 新集数沿用 54镜/6组/214s 范式 | — | 自检通过（54 镜 / 214.0s / 6×9 / 朱砂仅镜43） |
| yangjiajiang_ep07_metadata.py | 10-11 | 10-11 | EP07《七郎之死》54 镜元数据表（54镜/6组/214.0s，由 EP05/EP06 流水线同范式生成；全片无朱砂、不给血：箭孔只见孔不见脸/棍打落马棍光一闪/甲片崩开侧写） | EP07 出片数据源 | 纯数据模块 | 依据册3 页64-88 新建（切分表 29 镜 4 场扩写 + OCR 3-86~3-88 增补登殿呈状/党进对质/呼延赞代帅） | — | — | 新集数沿用 54镜/6组/214s 范式 | — | 自检通过（54 镜 / 214.0s / 6×9 / 无朱砂） |
| yangjiajiang_flow_grid_prompts.py | 10-11 | 10-11 | EP01/EP05/EP06/EP07 共 24 组九宫格英文提示词（EP_GRID_PROMPTS[ep][grid]，STYLE_BASE/GRID_HEAD 与 EP04 逐字一致） | 被通用九宫格器 import | 纯数据模块 | 人物全脱敏（无真实人名，过 Veo 审查）；无朱砂红/不给血 | 后续集数往 dict 里加键即可 | — | full-bleed / no numbering 必须声明 | — | 自检通过（每集 6 组 × 9 panel） |
| yangjiajiang_flow_grids.py ＋ _flow_cdp.py | 10-11 | 10-11 | 通用「Flow 九宫格生成 + 3×3 切片」器（EP04 试点脚本参数化，支持任意集数）；_flow_cdp 为原生 CDP WebSocket 驱动 | EP01/EP05 九宫格与首帧生产 | CDP 9222 + Flow 已登录 + anaconda python | 依赖 Flow UI 结构（aria-label/overlay pane 类名） | 更多集数 / 逐镜独立高清 | --all 批量 | 切片 3% 内缩 + 自动 contact sheet | ① Playwright 1.61 对 Chrome 154 connect_over_cdp 卡死；② JS .click() 不触发 Angular 事件流（静默不生成）；③ 触发器含 'crop_9_16' 子串误判比例；④ 画廊缩略图域名 flow.google.com/asb 非 flow-content.google | 全部修复：① _flow_cdp 原生 WebSocket；② click_selector 坐标级真实鼠标；③ 按换行末行精确匹配；④ 选择器扩到 asb/googleusercontent 并过滤头像 |
| yangjiajiang_ep04_flow_pilot.py | 10-11 | 10-11 | EP04 六组九宫格 Flow 生成器 + 3×3 切片器（Nano Banana，0 积分） | 生成九宫格 → 切成 54 张 544×960 首帧 | CDP 9222 + Flow 已登录 + anaconda python(playwright) | 单格仅 256×459（源 768×1376），放大到 544×960 有画质损失 | 逐镜独立高清生成 | `--all` 批量生成 | 切片后自动出 contact sheet 供验收 | ① 默认 16:9 导致横屏拉伸；② 九宫格自带编号污染首帧 | ① `configure_generation` 切 Image+9:16（按钮文本按换行末行匹配）；② 提示词加 full-bleed/no numbering 重新生成；切片内缩定 3% |
| _fill_views_when_clear.py ＋ _drama_char_sheet.py(加断点续跑) | 10-11 | 10-11 | 角色资产「等待空闲窗口自动补齐」等待器：轮询 /queue，抓「0在跑+0待跑」空闲窗口调 `_drama_char_sheet.py` 断点续跑补缺；`_drama_char_sheet.py` 新增 `existing_view_png()` 复用已成功视图、只生成被队列打断的缺失张 | GPU 队列被用户批处理长期占满、face/height 排不进时自动补缺 | ComfyUI 8188 + `_pc_common`(绕代理) + anaconda3 python(含 PIL) | 等待器默认 3600s 超时(--max-wait)；轮询 15s；单角色一次 | 多角色并行补齐 | `_drama_char_sheet.py` wait 超时改 `DRAM_WAIT_TIMEOUT` 环境变量(默认900，等待器设180) | 单卡队列严格串行 | ①face/height 被用户批处理 `/queue clear` 整批干掉(history 无条目，从没真跑过)；②前台 Bash 420s 超时 SIGTERM | ①断点续跑[REUSE] 只补缺失张；②等待器抓空闲窗口自动补齐（实测 3609s 全程 R1/P2 无空闲，最终用户暂停批处理 2min 手推补齐 → 5/5 视图 ✅ 合成表 1063×1170） |
| ig_download.py | 10-11 | 10-11 | Instagram 博主主页下载器：**三引擎择优（gallery-dl 主 → yt-dlp → instaloader 兜底）**；从 Chrome 9222 CDP 抓 IG cookie（不碰密码）→ 转 Netscape 临时文件喂给 CLI 引擎，用完即删；支持 --count N（前N条，按 date_utc 倒序+置顶帖规避）／--days N（滚动时间窗）／默认全量；含 dry-run、图片/视频过滤、断点续传、文件头+验帧双重产物校验 | IG 素材归档（实测目标 ayano.fj：68帖/1.1万粉丝 | 隔离 venv `binaries/python/envs/default` 的 instaloader 4.15.3 + websocket-client + requests；Chrome 9222 已登录并有 IG 标签页，或用 `--cookies-file`（给了它则完全不碰 CDP） | instaloader 的 `web_profile_info` 仍账号级 429（已降为兜底引擎）；**gallery-dl 走 `graphql/query`（带 lsd+fb_dtsg token）不受该限制** | 多账号队列、Story/Highlight 自动化 | 三模式 dry-run 自检、产物抽样验帧 | ① 禁止保存密码或 cookie 文件，临时 cookie 落系统 temp 且 finally 删除；② 429 设 fatal 立即停机不轰炸；③ 单账号系统 Mutex 禁并发；④ Story/Highlight 默认关闭；⑤ `--sleep` 下限 1s，CLI 引擎 `--sleep-request` 不低于 3s | ① instaloader `Profile.from_username` 只走 `web_profile_info` 无回退 → 该端点 429 时整链断；② --simulate 输出行带 `#` 前缀，曾被误当注释过滤导致误判 0 条 | **已打通**：yt-dlp 升到 2026.08.19（instagram:user 的 BROKEN 标记已移除）+ 装 gallery-dl 1.32.16 当主引擎。实测 ayano.fj `--count 2` 成功下到 2 个 mp4（720×1280 / 305、438 帧，cv2 验帧通过），`--days 3` 正确命中 1 条，全量 dry-run 枚举 69 条 |
| media_dl/（__main__ + core/ + web/ + qt/） | 10-11 | 10-11 | **通用媒体下载器**：三端共用 core（CLI / 网页 / 桌面）。站点自动识别（HOST_RULES → gallery_dl.extractor.find 离线探测 → 兜底启发式）；引擎 gallery-dl（图库社交）/ yt-dlp（视频平台）择优；**9222 探测（可选·仅展示）**：core `probe_cdp()` + CLI `--probe-cdp` + `GET /api/cdp` + 网页按钮徽标 + 桌面按钮，四端齐备，探测到可用也**不自动**改变 `use_cdp` 行为；**Popen 流式执行**（替代阻塞的 subprocess.run）；进度唯一可信源 `Archive.count()`（gallery-dl 非 TTY 时 skip 与 success 输出同形，不能数 stdout）；统一续传（SQLite 主库 + yt-dlp 文本桥接 + `import_legacy()` 迁移旧归档）；cookie 支持 CDP 自动取 / --cookies-file / 网页粘贴，一律转临时 Netscape 文件用完即删 | 任意站点媒体归档；IG 续传实测：迁移 3 条旧记录 + 新增 1 条且旧的不重下 | venv `binaries/python/envs/default`（gallery-dl 1.32.16 / instaloader / websocket-client）；PySide6-Essentials 6.12.0（仅桌面端，可选）；yt-dlp exe 2026.08.19 | 网页端仅监听 127.0.0.1；全局 Semaphore(1) 串行（保护账号）；yt-dlp 是独立 exe 不在 PATH，须走 `default_ytdlp_exe()` | 多站点并发队列、SSE 断点重放、Web 端批量 | total 自动探测缓存 | ① cookie 不落 repo/产物目录，进程退出即删；② 目录名统一用下划线（与 ig_download.py 一致，否则续传断链）；③ 产物下载须 resolve() 前缀校验防穿越 | ① `core/__init__.py` 曾误 import 不存在的 `.events`（EventBus 其实在 model.py）；② 输出目录名一度生成 `instagram_ayano.fj` 与旧的 `instagram_ayano_fj` 不一致→续传断链；③ `--simulate` 输出带 `# ` 前缀污染 current_item；④ **22:06 升级 ComfyUI v0.39.1 时整个 `tools/` 被重置，本目录一度全丢** | ①②③ 均已修；④ 从备份提交 `4d7c00747` 用 `git checkout 4d7c00747 -- tools/media_dl/ tools/ig_download.py` 完整恢复；⑤ 新增 9222 探测功能（四端）+ `ig_download.py --probe-cdp`，实测 9222 可用时报出 Chrome 154 / IG 页面 / 登录账号 `ken.zhao.986`；⑥ ayano.fj `--count 4` 实测：archive 3→4、文件 3→4、**原 3 个文件 mtime 未变**（证明没重下）、无 `.part`；⑦ 已删除带点残留目录 `instagram_ayano.fj/` |

---

## 一、2026-10-10（今天）

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 使用场景 | 依赖前提 | 限制 | 扩展方向 | 优化方向 | 后续规则 | 存在过的问题 | 修复记录 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pipeline_route_a_flow_native.py | 10-10 | 10-10 | 路线A：Nano Banana 0积分首帧 → 挂 Start Frame → Veo 3.1 Lite 8s 渲染 | 整集云端出片主线 | Playwright + CDP 9222 + Flow 已登录 | 每镜10积分、每日100熔断 | 多集参数化 | 首帧批量抽卡 | 先跑 launch bat | — | — |
| pipeline_route_b_moodboard_director.py | 10-10 | 10-10 | 路线B：九宫格情绪板定调 → 各镜独立2K首帧 → Veo 3.1（导演流） | 风格一致性高的整集 | 同上 + 复用 FlowCreditLedger | 同上 | 情绪板模板库 | — | 先跑 launch bat | — | — |
| flow_video_automation.py | 10-10 | 10-10 | Flow 自动化核心：强制 Video 模式 + 每日积分账本硬熔断 + 批量调度下载 | 被路线A/B导入，或 `--batch`/`--shot` 直跑 | CDP 9222 | 每日100 credits（`--max-credits`可调），账本 `flow_credit_ledger.json` | 更多模型档位 | 选择器容错 | 提交前必读 UI 实际积分 | 曾默认进生图模式 | 已加模式锁定 |
| assemble_ep03_master_relay.py | 10-10 | 10-10 | EP03 母带接力合成：Muse 720P 优先 + ComfyUI 本地渲染回退，54镜满格+TTS+SRT | EP03 成片收口 | 10-09 历史资产目录 | 硬编码日期 2026-10-10 与项目根路径 | 日期/集数参数化 | — | — | — | — |
| finalize_grain.py | 10-10 | 10-10 | 图片修复定稿后处理：外挂叠胶片颗粒（事后救援） | in-workflow 颗粒不达标时的 fallback | PIL / numpy | σ=1.0 仅数值达标无感知意义 | — | — | 正稿已改为 in-workflow KJNodes 颗粒 0.008（flat 1.473）；本脚本 σ1.5→1.156 为 fallback | 塑料皮肤（Pass2 扩散重绘平坦底） | σ≥1.5 颗粒有效；prompt2/负向修正后同强度颗粒效率更高（grain 0.004→flat 0.90） |
| verify_flow_config.py | 10-10 | 10-10 | 校验/配置 Flow 档位（Veo 3.1 Lite、x1、6s） | 自动化前自检 | CDP 9222 | — | — | — | — | — | — |
| test_flow_costs.py | 10-10 | 10-10 | 读取 UI "Generating will use XX credits" 实际积分成本 | 熔断账本校准 | CDP 9222 | — | — | — | — | — | — |
| inspect_flow_live.py ／ inspect_flow_video.py ／ inspect_flow_models.py | 10-10 | 10-10 | Flow 实时页/视频页/模型列表 UI 探针（枚举元素+截图） | 自动化开发调试 | CDP 9222 | 一次性探针 | 可合并为一个 CLI | — | — | — | — |

跨期修改（10-10 深度升级）：`qwen_v4_submit.py`（09-30创建；新增 `--verify` 自动体检 / `--auto-grain` 阶梯重试 0.004→0.008→0.012（≤2次）/ `--lightning 8` 速度档 3.9x / `--batch-dir` 批量目录 / `submit_verify_loop` 可注入重构；正稿=官方链路 `restore --image <源图> --run --verify`，模板 `workflows/v4/qwen_image_2_1_restore_v5.json`）；`restore_qa.py`（10-01创建；⑧达标线改为 max(0.6, 源图-0.1)，`--min-flat` 可覆盖）；`flow_cdp_automation.py`（10-08创建）；`comfy_sqlite_queue.py`（10-09创建；新增 `backfill` 子命令，回填 19952 个历史资产——直接 POST /prompt 会绕过队列不入库；ComfyUI 0.30 原生资产面板重启必为空属原生设计限制，历史产物走 Browser 插件画廊或 flat_gallery）。另：T3 4MP 显存实验首跑失败两连——① R2 默认逻辑 min(2.5, 2×R1) 覆盖模板 4.0（实际只跑了 2MP）→ 用 `--final-mp 4.0` 强制；② 复跑遇双 ComfyUI 实例显存争用 → `wait_and_verify` 增加 `status_str=error` 实现 OOM 快速失败。

### 一B、2026-10-10 午后~晚间新增（11:00 后）

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 使用场景 | 依赖前提 | 限制 | 扩展方向 | 优化方向 | 后续规则 | 存在过的问题 | 修复记录 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| shot02 路线A 端到端系列：run_shot02_route_a.py ／ submit_shot02_video.py ／ check_shot02_live_progress.py ／ wait_and_save_shot02.py ／ probe_shot02_card.py ／ download_shot02_video.py ／ extract_shot02_video.py | 11:17~11:27 | 14:57 | shot02 路线A 全链路打通：提交→实时进度→等待→下载→抽帧验证 | 路线A 单镜验收 | CDP 9222 + ffmpeg | 一次性打通脚本 | 已验证流程并入主引擎 | — | — | 生成卡片残留/下载链路不稳 | 见下两行攻坚记录 |
| Flow 视频卡片探针+下载攻坚系列：probe_canvas.py ／ snap_live.py ／ inspect_video_card.py ／ get_newest_img.py ／ probe_all_imgs.py ／ find_cards.py ／ download_veo_video.py ／ handle_flow_video_download.py ／ download_via_browser_button.py ／ escape_to_canvas.py ／ clean_failed_card.py | 11:08~12:20 | 11:39 | 视频卡片 DOM 定位、blob 抓取下载、浏览器按钮下载（下载目录搬运）、Esc 回画布、失败卡片清理 | 下载链路攻坚 | CDP 9222 | 依赖前端 DOM | 并入 flow_video_automation | — | — | 卡片选择器难定位；Flow 下载按钮/blob 均有失效场景；失败卡片污染画布 | blob 抓取 + 浏览器按钮双方案兜底；clean_failed_card 清理残留 |
| pipeline_route_a_postprocess_relay.py | 12:17 | 12:17 | EP03 前2段 ComfyUI/FFmpeg 1080P 电影级后期接力总成 | 路线A 本地后期 | ffmpeg/ComfyUI | 前2段专用 | 全片化 | — | — | — | — |
| verify_final_master.py | 12:18 | 12:18 | 母带 fps/帧数/时长校验 | 成片验收 | cv2 | — | — | — | — | — | — |
| prompt_safety_linter.py | 14:50 | 14:57 | Flow/Veo 提示词前置合规审查器（Prominent People Policy） | 提交前预检 | 纯文本 | 词表需维护 | 扩充政策词表 | — | 提交前必跑 linter | 含知名/历史人物提示词被 Veo 平台策略拦截浪费积分 | 前置审查拦截后再提交 |
| flow_frame_lock.py | 17:02 | 17:11 | Google Flow 首帧锁定器（Start Frame Lock） | 路线A/B 首帧驱动 | CDP 9222 | — | — | — | 挂首帧后必须核验生效 | **路线A 声称的 Start Frame 挂载从未生效**（tools/ 无上传首帧代码，实为纯 t2v）→ 画风漂移（水墨剪纸→写实真人） | 本脚本实现首帧上传锁定并核验 |
| 午后集成更新：flow_cdp_automation.py ／ flow_video_automation.py ／ pipeline_route_a_flow_native.py ／ pipeline_route_b_moodboard_director.py ／ run_flow_shot02.py ／ yangjiajiang_ep01_part2_pipeline.py ／ yangjiajiang_ep03_pipeline.py ／ yangjiajiang_ep03_master_engine.py ／ verify_final_results.py ／ extract_frames.py ／ extract_exact_video.py ／ check_media_menu.py ／ check_chrome_status.py（创建于更早，14:50~17:13 修改） | — | 14:50~17:13 | 与首帧锁定、合规 linter、画廊接入同期的集成更新 | — | — | 具体 diff 未留档 | — | — | — | — | 见 flow_frame_lock / prompt_safety_linter 行 |
| skills 审计与权重下载系列：_list_skills.py ／ _list_market.py ／ _skillhub_search.py ／ _dump_skill.py ／ _scan_inject.py ／ _hollow_audit.py ／ _probe_urls.py ／ _probe_flux2.py ／ _wf_model_refs.py ／ _fix_wf_names.py ／ _chk_dl.py ／ _dl_weights.py | 17:14~17:40 | 23:24 | WorkBuddy skills 安全审计（命令注入扫描/提示注入扫描/空壳审计）+ 模型权重 URL 探测/工作流模型引用核对/断点续传下载 | 技能市场选型与权重准备 | 纯本地/urllib | 一次性 | — | — | — | PowerShell 下载输出不可靠 | 改用 _dl_weights（Python 断点续传+进度落盘 UTF-8） |
| test_auto_grain.py | 18:02 | 18:02 | auto-grain 自动触发离线断言（mock 三点注入，6 项场景：阶梯触发/重试上限/到顶停止） | qwen_v4_submit 回归 | 无 GPU | 离线层，GPU E2E 需另跑 | — | — | 改 submit_verify_loop 后必跑 | — | T1 验收 6/6 通过；GPU E2E grain 0→flat 0.55✘→自动升 0.004→0.90△ 通过 |
| Wan Animate 两段式系列：wan_batch_generate.py ／ wan_stage1_redraw.py ／ wan_stage1b_reactor.py ／ wan_stage3_facelock_video.py ／ wan_face_qa.py | 21:03~23:13 | 23:14 | 多分块批量迁移 + SDXL 重绘服装参考图 + ReActor 锁脸 + 成片逐帧锁脸 + 身份一致性 QA | 服装可控的动作迁移 | ComfyUI 8188 + ReActor + RetinaFace onnx | Stage1 候选需人工挑选 | — | — | — | ①ImageScale 512x512 crop=center 裁掉竖屏 44% 人体；②分块 start_index 恒 0；③服装提示词无效（图像先验压过文本）；④insightface FaceAnalysis.get() native 崩溃 | ①改保持 9:16；②帧偏移递推 0,49,93…；③两段式：先重绘参考图再锁脸；④直连 RetinaFace det_10g.onnx（该进程禁 import torch） |
| flat_gallery.py | 22:38 | 22:48 | 扁平画廊生成器：真实缩略图（PIL/ffmpeg poster）+ mtime 缓存，自包含 HTML | 批量产物浏览；已接入 3 个批量出片脚本末尾 | PIL + ffmpeg | — | — | — | 画廊失败不影响主流程（try-except） | 目录不存在时 SystemExit 中断主脚本 | 已修复；缩略图缓存 _thumbnails/ 按 md5+mtime 增量 |
| _drama_gate.py | 22:44 | 22:44 | 本地「路由闸门」：进下一步前强制校验前置产物存在（对应豆包强制顺序机制） | 防止资产不完整浪费积分跑视频 | 纯 glob，零依赖 | 只查存在性不查质量 | 质量阈值校验 | — | 每阶段切换前必跑 | — | — |
| PC 出图评测矩阵系列：_verify_weights.py ／ _probe_comfy_zimage.py ／ _zimage_test.py ／ _img_stat.py ／ _pc_gen_zimage.py ／ _pc_gen.py ／ _pc_run_matrix.py ／ eval_pc_models.py ／ make_pc_matrix_sheet.py ／ _peek_eval.py ／ _probe_qwen21.py ／ _pc_gen_qwen21.py ／ _probe_lora_repo.py（另更新 _pc_common/_pc_gen_flux/_pc_gen_sd15/_pc_prompts/_pc_sheet） | 22:22~23:23 | 23:23 | 权重校验 + Z-Image/Qwen-Image 2.1 可用性探测 + 实测出图 + 多模型对比矩阵（z_image_turbo/flux_dev_fp8/majicmix 等）+ 归一化打分 + 对比图 | 底模选型评测 | ComfyUI 8188 + 对应权重 | 各档位显存不同需单实例 | 接入更多底模 | — | — | ①HTTP_PROXY 劫持 127.0.0.1:8188 返回 502；②CLIPLoader 下拉无 z_image type | ①全部探测/出图脚本内置绕代理 opener；②依赖 sd.py 对 qwen_3_4b TE 的自动路由（type=qwen_image） |
| _drama_char_sheet.py（＋ _dl_weights.py 新增 counterfeit 档并串接 _verify_weights.verify_one） | 22:41~23:44 | 23:44 | 角色 JSON→锁 seed→SD1.5 五视图（正/侧/背/脸/身高）→build_sheet 合成 turnaround 资产表；下载器加字节+头部校验失败自动重下 | 动漫短剧 Step3 资产一致性 | ComfyUI 8188 + _pc_common(绕代理) + **anaconda3 python(含 PIL)** | 走 _pc_gen_sd15.CONFIG 档位，无该 model 回退 512x768/28步/cfg8.0 | Counterfeit 在盘后重跑补齐 front 缺格 | — | 每角色一次；seed 锁定保证一致性 | ①GPU 单卡队列被 Qwen2.1 长任务占满→front 排队超时无产物；②默认 managed python 无 PIL | ①队列空时重跑即补齐；②统一用 anaconda3 python。**实测 4/5 视图出图＋合成表 1063×1170 ✅** |

---

## 二、2026-10-09

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 使用场景 | 依赖前提 | 限制 | 扩展方向 | 优化方向 | 后续规则 | 存在过的问题 | 修复记录 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| comfy_sqlite_queue.py | 10-09 | 10-10 | ComfyUI SQLite 断点续跑队列：任务先落库→执行→产物归档→崩溃自动恢复 | 长批量渲染的灾备底座 | SQLite + ComfyUI API 8188（`COMFY_URL` 可环境变量覆盖） | DB 位于 user/ | 分布式/多机队列 | 状态机细化 | 长任务必须先落库 | 直接 POST /prompt 绕过队列不入库；ComfyUI 0.30 原生资产面板重启必为空（原生限制，易误判丢数据） | 新增 backfill 子命令扫描 output/ 回填 19952 个历史资产（abs_path 去重幂等）；历史产物走 Browser 插件画廊或 flat_gallery |
| test_sqlite_queue_suite.py | 10-09 | 10-09 | queue 自动化测试套件：落库校验/崩溃模拟恢复/失败隔离重试/资产索引/CLI 集成 | 改动 queue 后回归 | 同上 | — | — | — | — | — | — |
| example_batch_submit.py | 10-09 | 10-09 | 批量分镜任务提交标准用法示例（先落库后提交） | 模板/学习 | 同上 | — | — | — | — | — | — |
| yangjiajiang_ep03_pipeline.py | 10-09 | 10-09 | EP03 全链路出片管线（54镜、`--submit-only`、4-step Turbo → Lanczos 720P、`-an` 去噪） | EP03 本地渲染 | ComfyUI 8188 | 路径/日期硬编码 | 集数参数化 | — | 长任务只提交不轮询 | — | — |
| yangjiajiang_ep03_master_engine.py | 10-09 | 10-09 | EP03 母带三轨总成：720P 超分 + Edge-TTS 云健男声（防吞字）+ SRT | EP03 收口 | ffmpeg + edge-tts | — | — | — | — | — | — |
| comfy_shot_quality_auditor.py | 10-09 | 10-09 | 54镜逐镜机器审计（存在性/时长/分辨率/黑屏方差/黑框）→ Markdown 审计矩阵 | 渲染后质检 | cv2 | — | 接入自动重渲染 | — | 形态类指标做最终裁决（借鉴 restore_qa 经验） | — | — |
| auto_audit_and_master_assembler.py | 10-09 | 10-09 | 后台守护：轮询扫描新渲染产物 → 逐镜审计 → 54镜全 PASS 自动触发母带总装 | 无人值守收尾 | 依赖 auditor + master_engine | 轮询模式 | 改事件驱动 | — | — | — | — |
| batch_muse_pipeline.py | 10-09 | 10-09 | Muse.ai 54镜批量图生视频：逐镜上传首帧+水墨Prompt、blob 新旧比对捕获产物、断点续跑去重 | 云端出片主线 | CDP 9222 + Muse 已登录 | 依赖前端 DOM 结构 | — | — | 已有产物(>100KB)秒级跳过 | Muse 下载曾拿到错误 blob | 新旧 src 集合比对精准定位 |
| reprocess_clean_ep03_slices.py | 10-09 | 10-09 | 54镜纯净画芯提取定稿版：内缩剔黑框 + 去底部英文 + 柔焦景深铺满 544x960（防拉伸） | 修复早期切片缺陷 | PIL/numpy | — | — | — | — | 早期切片含黑框/英文/拉伸变形 | 4 方案实验后定稿（见下行 test_*） |
| test_clean_crop.py ／ test_fit_crop.py ／ test_cinema_crop.py ／ test_scroll_crop.py | 10-09 | 10-09 | 4 种切片规格化方案实验：画芯探测 / ImageOps.fit 裁剪 / 景深扩展 / 宣纸底色卷轴 | 方案对比选型 | PIL/numpy | 一次性实验 | — | — | — | — | — |
| Flow UI 探针系列：click_new_project.py ／ explore_flow_workspace.py ／ inspect_flow_canvas.py ／ inspect_flow_settings.py ／ check_settings_popup.py ／ check_media_menu.py ／ inspect_sidebar.py ／ find_flow_prompt_box.py ／ check_flow_result.py ／ wait_flow_finish.py ／ animate_flow_card.py ／ open_flow_scenes.py ／ test_upload_flow.py ／ test_add_ingredients.py ／ test_benchmark_platforms.py | 10-09 | 10-09 | Flow DOM 侦察与动作试验（新建项目/画布/设置/提示框定位/结果等待/上传素材），产出选择器知识 | flow_video_automation 开发前置侦察 | CDP 9222 | 一次性探针 | 已并入主引擎，可归档清理 | — | — | — | — |
| Muse 探针+下载系列：inspect_muse.py ／ inspect_muse_ui.py ／ inspect_muse_history.py ／ test_muse_upload.py ／ check_muse_status.py ／ download_muse_video.py | 10-09 | 10-09 | Muse UI/历史/上传/状态/下载 侦察与操作 | Muse 自动化开发前置 | CDP 9222 | 一次性探针 | 同上 | — | — | — | — |
| shot02 双平台对比系列：setup_comparison_env.py ／ run_flow_benchmark.py ／ run_muse_benchmark.py ／ run_flow_shot02.py ／ run_muse_shot02.py ／ download_flow_shot02.py ／ extract_latest_muse_video.py ／ extract_exact_video.py ／ extract_shot02_frames.py ／ extract_frames.py | 10-09 | 10-09 | Flow vs Muse 逐镜同题基准（环境准备/生成/下载/ffmpeg 抽帧对比） | 平台选型评测 | CDP 9222 + ffmpeg | shot01/shot02 单镜 | 扩展到多镜自动化 | — | — | — | — |
| 多chunk工作流生成系列：build_multichunk_full_ui_wf.py ／ build_full_ui_workflow.py ／ validate_full_wf.py ／ inspect_multichunk_ui.py | 10-09 | 10-09 | 基于 workflows/v3 基底生成 Wan Animate 多 chunk 全片动作迁移工作流 JSON（API版+UI版）并校验一致性 | 长视频分 chunk 迁移 | workflows/v3 基底文件 | — | chunk 数参数化 | — | — | — | — |
| DWPose/节点调试系列：query_nodes.py ／ test_dwpreprocessor_batch.py ／ test_face_only.py | 10-09 | 10-09 | /object_info 探针 + DWPose 批量性能/仅人脸模式直测 | 骨架提取调优 | ComfyUI 8188 / controlnet_aux | 一次性 | — | — | — | — | — |
| 其他单件：check_dual_pipeline_status.py（Comfy+Muse 双管线状态一览）｜audit_muse_and_comfy_frames.py（拼装成片 2s/7s/12s/25s 抽帧审计）｜deploy_ep03_input_assets.py（shot 图部署到 input/）｜inspect_todos_dir.py（打印 todos 目录树） | 10-09 | 10-09 | 见名 | 日常查单/抽检/部署 | urllib/glob/ffmpeg/shutil | 一次性 | — | — | — | — | — |

---

## 三、2026-10-08

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 使用场景 | 依赖前提 | 限制 | 扩展方向 | 优化方向 | 后续规则 | 存在过的问题 | 修复记录 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| launch_flow_cdp_chrome.bat | 10-08 | 10-08 | 启动带 `--remote-debugging-port=9222` + 独立 profile + 代理 7897 的 Chrome | 一切 Flow/Muse 自动化的统一入口 | Chrome + 本地代理 | 同 profile 不能双开；普通 Chrome 无法后补接管 CDP | 端口/URL 参数化 | — | 先跑它再跑自动化 | — | bat→ps1 彩色提示增强版 |
| launch_flow_cdp_chrome.ps1 | 10-08 | 10-08 | 同上（PowerShell 版） | 同上 | 同上 | 同上 | — | — | — | — | — |
| check_chrome_status.py | 10-08 | 10-09 | CDP 9222 全 context/标签页枚举 + 逐页截图留存 | 接管自检 | Playwright + CDP | — | — | — | — | — | — |
| yangjiajiang_ep02_metadata.py | 10-08 | 10-08 | EP02 54镜元数据表（6×九宫格、214.0s 精确对齐、解说/音效/BGM 多轨） | EP02 数据源（被 import） | — | 硬编码 | — | — | — | — | — |
| yangjiajiang_ep02_grid_cutter.py | 10-08 | 10-08 | OpenCV 智能探测九宫格画框切片 + 等距兜底 + Lanczos 重采样 544x960 | EP02 素材准备 | opencv/PIL | — | — | — | — | 黑边框/底部文字污染切片 | 智能边框检测 + 安全平退机制 |
| yangjiajiang_ep02_pipeline.py | 10-08 | 10-08 | EP02 全链路管线（54镜、`--submit-only`、4-step Turbo、两段式超分、`-an` 剥离白噪、三轨混音） | EP02 渲染 | ComfyUI 8188 | — | — | — | 长任务只提交不轮询 | 扩散模型原生嘶嘶白噪 | 规整时强制 `-an` |
| yangjiajiang_ep02_master_engine.py | 10-08 | 10-08 | EP02 母带三轨总成：Lanczos+Unsharp 720P 超分 + Edge-TTS 云健男声（防吞字） | EP02 收口 | ffmpeg/edge-tts | — | — | — | — | — | — |
| yangjiajiang_ep03_metadata.py | 10-08 | 10-08 | EP03 54镜元数据表（同 EP02 架构） | EP03 数据源 | — | — | — | — | — | — | — |
| crop_ep03_grid01.py | 10-08 | 10-08 | EP03 grid01 手工等分 3x3 切 9 镜首帧 | Flow 试点素材 | PIL | 源路径硬编码到 .gemini/brain | — | — | — | 等分切片含黑框 | 被 10-09 reprocess_clean 版取代 |
| flow_cdp_automation.py | 10-08 | 10-10 | Flow CDP 接管试点引擎：登录检测/工作台识别/Grid01 九镜素材与提示词装载/监控下载 | Flow 试点 | Playwright + CDP 9222 | Grid01 提示词内嵌硬编码 | — | — | — | — | 已被 flow_video_automation 主引擎取代 |
| 全片动作迁移系列：extract_full_poses.py ／ run_full_motion_transfer.py ／ auto_full_duration_pipeline.py | 10-08 | 10-08 | 全片时长动作迁移：调 ootd_study 提纯姿态 → Wan2.2 Animate 全片提交 → 自动管线 | 用户视频动作克隆 | ComfyUI 8188 + ootd_study | — | — | — | — | — | — |
| 动作迁移配套：process_user_videos.py ／ inspect_videos.py ／ assemble_10s_test_videos.py ／ create_full_comparisons.py ／ verify_final_results.py | 10-08 | 10-08 | 用户驱动视频预处理/元信息/10s 测试拼装/原片对比/产物帧数校验 | 动作迁移配套 | ffmpeg/cv2 | 路径硬编码 | — | — | — | — | — |
| 开发侦察：find_wan_node.py ／ check_node_info.py ／ check_ep02.py | 10-08 | 10-08 | 全库搜 Wan Animate 节点定义 / WanAnimateToVideo schema / EP02 渲染计数 | 节点调试 | — | 一次性 | — | — | — | — | — |

跨期修改（10-08 在改）：`subtitle_annotator.py`（10-04 创建，字幕标注/烧录）、`global_master_audio_engine.py`（10-04 创建，全局母带音频引擎 33KB）。

---

## 四、2026-10-01 ~ 10-07

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 使用场景 | 依赖前提 | 限制 | 扩展方向 | 优化方向 | 后续规则 | 存在过的问题 | 修复记录 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| restore_qa.py | 10-01 | 10-02 | 图片修复 8 项体检指标（锐度/细节/纹理形态等） | 修复质量验收 | PIL/numpy | — | — | — | ⑧纹理形态为最终裁决项 | ④⑤锐度/细节对塑料皮肤是盲区 | 规则改为以平坦区噪声底裁决 |
| h3_fast_submit.py | 10-01 | 10-02 | H3 4步 turbo 快速提交（24.3min→3.92min/段，含原生音频） | H3 快速出片 | ComfyUI 8188 | — | — | — | 只提交不轮询 | 内存/队列硬门槛误拦排队任务 | 改为告警不拦截 |
| h3_enhance_submit.py | 10-01 | 10-01 | H3 出片后增强提交（VFI/AI 超分/补帧 60fps） | H3 后期增强 | ComfyUI 8188 | — | — | — | 同上 | 同上门槛问题 | 同上修复 |
| h3_fast_segmented.py | 10-01 | 10-02 | H3 长片分段生成 + ffmpeg 拼接 | 长视频分段流水线 | ComfyUI 8188 + ffmpeg | — | — | — | 支持硬切默认；`--merge-only` 重拼 | merge 丢音；crossfade 约3帧叠影 | `-map [aout]`+acrossfade 0.3；默认硬切 |
| h3_fl2v_pipeline.py | 10-02 | 10-02 | FL2V 首尾帧驱动视频管线 | 首尾帧控制生成 | workflows/v5 模板 | 节点19 须 `[inject:last_frame]` 接 last_frame | — | — | — | — | — |
| qwen_keyframe_submit.py | 10-02 | 10-02 | Qwen 关键帧生成提交 | 关键帧出图 | ComfyUI 8188 | — | — | — | — | — | — |
| download_wan22_animate.py | 10-02 | 10-02 | Wan2.2 Animate 模型下载 | 环境准备 | requests | — | — | — | — | — | — |
| ui_workflow_postprocess.py | 10-02 | 10-02 | UI 工作流后处理 | 工作流整理 | — | — | — | — | — | — | — |
| api2canvas.py | 08-15 | 10-02 | API 工作流 ↔ Canvas 转换 | 工作流格式互转 | — | — | — | — | — | — | — |
| yangjiajiang_ep01_1min_pipeline.py | 10-03 | 10-04 | EP01 一分钟版全链路管线 | EP01 渲染 | ComfyUI 8188 | — | — | — | — | — | — |
| yangjiajiang_pilot_i2v.py | 10-04 | 10-04 | 杨家将试点 i2v | 试点验证 | ComfyUI 8188 | — | — | — | — | — | — |
| yangjiajiang_ep01_1min.py ／ copy_ep01_keyframes.py ／ prepare_ep01_part2_inputs.py ／ copy_act2_colored_inputs.py | 10-04 | 10-04 | EP01 一分钟版配置 / 关键帧复制 / Part2 输入准备 / Act2 上色素材复制 | EP01 素材配套 | shutil/PIL | 一次性 | — | — | — | — | — |
| yangjiajiang_ep01_part2_pipeline.py | 10-04 | 10-04 | EP01 下半集全链路管线 | EP01 渲染 | ComfyUI 8188 | — | — | — | — | — | — |
| storyboard_grid_pipeline.py | 10-04 | 10-04 | 分镜九宫格管线 | 分镜出图 | ComfyUI 8188 | — | — | — | — | — | — |
| motion_transfer_pipeline.py ／ run_motion_transfer_tests.py | 10-04 | 10-04 | 动作迁移管线与批量测试 | 动作迁移 | ComfyUI 8188 | — | — | — | — | — | — |
| three_track_sync_engine.py | 10-04 | 10-04 | 三轨（画面/旁白/BGM）同步引擎 | 母带声画对齐 | ffmpeg | — | — | — | — | — | — |
| global_master_audio_engine.py | 10-04 | 10-08 | 全局母带音频引擎（33KB，多集复用） | 各集音频总成 | ffmpeg/edge-tts | — | — | — | — | — | — |
| subtitle_annotator.py | 10-04 | 10-08 | 字幕标注/烧录 | 成片字幕 | — | — | — | — | — | — | — |
| finalize_and_deliver.py ／ crop_act4.py ／ crop_act5.py | 10-04 | 10-04 | 交付收尾 / 第4、5幕裁剪 | 分幕处理 | ffmpeg/PIL | 一次性 | — | — | — | — | — |

---

## 五、2026-09（紧凑表：仅名称/时间/作用/备注）

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 备注（问题/修复） |
|---|---|---|---|---|
| run_h3_guard_v5.py | 09-21 | 09-22 | H3 守护进程 v5（提交看护/断点恢复，49KB） | 待拆分重构 |
| h3_rope_common.py | 09-21 | 09-22 | H3 公共库（33KB，被 guard 等引用） | — |
| run_h3_shiling_c3.py | 09-21 | 09-21 | H3 视灵 c3 单片 | — |
| _checkv.py ／ _cmd.py | 09-22 | 09-22 | 临时校验/命令小工具 | 一次性 |
| _pc_common.py ／ _pc_prompts.py ／ _pc_gen_sd15.py ／ _pc_gen_flux.py ／ _pc_sheet.py ／ _pc_report.py | 09-21 | 09-21 | PC 端图片生成系列（公共/提示词/SD15/FLUX/报表/汇总表） | 一次性 |
| generate_mirror_selfies.py | 09-20 | 09-20 | 镜像自拍图生成 | — |
| benchmark_gfpgan.py | 09-20 | 09-20 | GFPGAN 人脸修复基准测试 | — |
| gen_wear_source.py | 09-14 | 09-14 | 穿戴类源图生成 | — |
| frame_extractor.py | 09-14 | 09-14 | 通用帧提取器 | — |
| h3_gen_yunxiao_gesture.py ／ h3_yunxiao_gesture.py ／ h3_yunxiao_dance.py | 09-12 | 09-12 | H3 云霄主题（手势/舞蹈）单片 | 单片脚本模式，已被 fast_submit 模板化取代 |
| h3_gen_street_dance.py ／ h3_street_dance.py | 09-12 | 09-12 | H3 街舞主题单片 | 同上 |
| h3_prompt_gen.py | 09-12 | 09-12 | H3 提示词批量生成器 | — |
| batch_faceswap_overlay.py | 09-11 | 09-11 | 批量换脸+水印/语录叠加 | 对应 batch-faceswap skill |
| gen_lora_verify.py ／ gen_lora_verify2.py ／ gen_lora_verify3.py | 09-10 | 09-10 | LoRA 训练验证（三代迭代） | — |
| alchemist_pipeline.py | 09-09 | 09-09 | 综合处理管线（推测） | 未记录 |
| ui_to_prompt.py | 08-05 | 09-09 | UI 工作流 → 提示词提取 | — |
| assemble_lora_dataset.py | 09-08 | 09-09 | LoRA 数据集组装 | — |
| download_flux_dev.py | 09-08 | 09-08 | FLUX dev 模型下载 | — |
| gen_lora_dataset.py ／ gen_lora_diff.py | 09-08 | 09-08 | LoRA 数据集生成/差分集 | — |
| run_flux_lora_test.py ／ test_flux_lora.py | 09-08 | 09-08 | FLUX LoRA 出图测试 | — |
| t2i_flux_v2.py ／ t2i_model_test.py | 09-08 | 09-08 | 文生图 v2 / 模型对比测试 | — |
| h3_tennis_skirt_dance.py | 09-08 | 09-08 | H3 网球裙舞蹈单片（对应 tennis_dance 项目） | — |
| h3_indoor_heels_dance.py ／ h3_erza_cosplay.py ／ h3_fashion_10pose.py ／ h3_fashion_10pose_anime.py | 09-07 | 09-07 | H3 室内高跟/艾尔莎cos/时尚10姿势（实拍/动漫）单片 | — |
| submit_h3_corridor.py ／ submit_h3_qipao.py ／ submit_h3_runway.py ／ submit_h3_eyebrow.py ／ wait_h3_runway.py | 09-07 | 09-07 | H3 走廊/旗袍/秀场/眉眼 提交 + runway 等待 | "提交+等待"分离的早期形态 |
| h3_eyebrow_seg.py | 09-07 | 09-07 | 眉眼分割处理 | — |
| h3_fashion_10pose 系列变体、h3_micro_expression.py、h3_browse_show.py、h3_xiaoshimei_dance.py、h3_sexy_dynamic_dance.py | 09-07 | 09-07 | H3 时尚/微表情/浏览展示/小妹舞蹈单片 | — |
| h3_ab_g2_golf.py ／ h3_ai_dynamic_dance.py ／ h3_lemi_handed_dance.py ／ h3_vlog_minidv.py | 09-06 | 09-06 | H3 高尔夫/AI热舞/手持/vlog minidv 单片 | — |
| run_rain_street_480p_5s.py ／ run_qipao_480p_5s.py ／ run_ol_girl_group_480p_5s.py ／ run_xinniang_480p_5s.py ／ run_jingling_480p_5s.py | 09-05~06 | 09-05~06 | 480p 5s 快速出片系列（雨街/旗袍/女团/新娘/精灵） | — |
| verify_vfi_workflow.py | 09-06 | 09-06 | VFI 补帧工作流验证 | — |
| submit_jingling_h3.py | 09-05 | 09-05 | 精灵主题 H3 提交 | — |
| enhance_h3_video.py ／ h3_simple_video.py ／ run_workflow_json.py | 09-05 | 09-05 | H3 增强/简单示例/通用工作流 JSON 执行器 | — |
| h3_xinniang_v1.py ／ h3_xinniang_cosplay.py | 09-05 | 09-05 | 新娘主题 v1/cosplay | — |
| submit_h3_mv7_ref2va.py ／ submit_h3_mv7_fl2va.py ／ stitch_h3_mv7.py | 09-01~02 | 09-01~02 | MV7 参考图→音视频 / 首尾帧→音视频 / 拼接 | 分段拼接架构雏形 |

---

## 六、2026-08 及更早（紧凑表）

| 脚本名称 | 创建 | 最后修改 | 主要作用 | 备注（问题/修复） |
|---|---|---|---|---|
| rate_fp8_hazy_lazy.py ／ rate_fp8_hazy_lazy_v2.py ／ gen_hazy_home_lazy_prompts.py ／ submit_hazy_home_lazy.py | 08-31 | 08-31 | fp8「hazy home lazy」主题评分/提示词/提交 | — |
| batch_fp8_300.py ／ batch_fp8_300_en.py ／ test_fp8_batch01.py | 08-30~31 | 08-31 | fp8 300 张批量出片（中/英）+ 首批测试 | 轮询消耗积分教训的发生地之一 |
| night_watcher.py | 08-30 | 08-30 | 夜间守护任务（有 night_watcher.log） | — |
| h3_gufeng_2segs.py ／ build_h3_24segs.py ／ test_h3_seg01.py | 08-30 | 08-30 | H3 古风2段 / 24段构建 / 段1测试 | — |
| translate_prompts_en.py ／ fix_negative_prompts.py | 08-30 | 08-30 | 提示词英译 / 负向词修复 | — |
| ltx_speed_test.py ／ ltx_quality_test.py ／ ltx_smoke_test.py | 08-28~30 | 08-30 | LTX 速度/质量/冒烟测试 | 对应 LTX-2.3_deletion_record.md |
| verify_xiezhen_fix.py ／ fix_xiezhen_prompts.py ／ submit_batches_50xiezhen.py ／ run_batches_50xiezhen_orchestrator.py ／ submit_50xiezhen.py | 08-29~30 | 08-30 | 「50写真」批量：修复校验/提示词修复/分批提交/编排器 | — |
| check_v03_frames.py ／ watch_v04_diag.py ／ submit_v04_only.py ／ analyze_refs.py | 08-28~29 | 08-29 | v03 帧检查 / v04 诊断与提交 / 参考图分析 | — |
| submit_chibi.py ／ assemble_chibi.py ／ merge_chibi.py ／ make_title_card.py | 08-27~28 | 08-28 | chibi 系列：提交/合成/拼接/标题卡 | — |
| mux_h3_audio.py ／ monitor_h3_segments.py ／ submit_h3_audio.py ／ merge_h3_segments.py ／ submit_h3_segments.py | 08-27 | 08-27 | H3 分段：提交/监控/音频混流/拼接 | 分段拼接早期版（后被 h3_fast_segmented 改进） |
| download_flux_models.py | 08-28 | 08-28 | FLUX 模型批量下载 | — |
| validate_avatar_workflows.py ／ smoke_test.py ／ download_avatar_models.py ／ download_avatar_models_v2.py ／ stop_comfyui.py ／ wait_comfyui.py ／ toggle_nodes.py | 08-14~15 | 08-15 | 头像工作流：校验/冒烟/模型下载/ComfyUI 停等/节点启停 | 有 avatar_final_report.md、avatar_smoke_test_record.md |
| compare_v2_v3.py | 08-11 | 08-11 | v2/v3 结果对比 | — |
| batch_faceswap.py ／ batch_faceswap_v2.py ／ batch_faceswap_v3.py ／ batch_faceswap_gpu.py ／ batch_faceswap_comfyui.py | 08-05~06 | 08-06 | 批量换脸（多代：本地/ComfyUI/GPU） | — |
| batch_faceswap_overlay ／ batch_demosaic_faceswap.py ／ demosaic_faceswap_pipeline.py ／ demosaic_faceswap_v2.py | 08-05 | 08-05 | 换脸叠加 / 批量去码换脸 | — |
| video_faceswap.py ／ video_faceswap_direct.py ／ video_faceswap_enhanced.py ／ video_outfit_faceswap.py | 08-05 | 08-05 | 视频换脸（直出/增强/换装） | — |
| tryon.py ／ video_tryon_pipeline.py(_v2) ／ batch_tryon_comfyui.py ／ batch_tryon_runner.py ／ faceswap_tryon_pipeline.py(_v2) ／ pipeline_faceswap_outfit.py ／ inpaint_clothing.py | 08-05 | 08-05 | 虚拟试衣全链路（单图/视频/批量/换脸+试衣组合） | 有 README_tryon.md |
| test_idm_vton.py 及 9 个变体（clean/fp32fix/gnfix/time_emb/resnet_trace/hook_diag 等）＋ idm_vton_inference.py ／ run_idm_vton_test.py ／ submit_idm_vton.py ＋ idm_vton_workflow*.json ×12 | 08-05 | 08-05 | IDM-VTON 试衣实验与工作流（fp16/fp32/groupnorm 修复排查） | fp16 数值问题排查记录 |
| generate_ra_masks.py(_v2/v3) ／ ra_seamless_clone.py ／ ra_overlay_test.py ／ submit_ra_batch.py ／ classify_ra_videos.py | 08-05 | 08-05 | RA 系列：掩码生成/无缝克隆/叠加/批量/分类 | — |
| gen_pose.py ／ gen_mask.py ／ gen_torso_mask.py ／ generate_pose_mask.py ／ fix_mask.py | 08-05 | 08-05 | 姿态/掩码生成与修复 | — |
| add_subtitles.py ／ fix_subtitles_concat.py ／ fix_sub_v2.py ／ fix_sub_v3.py ／ add_text_overlay.py ／ add_ai_watermark.py ／ watermark.py ／ quotes.json | 08-05 | 08-05 | 字幕/文字叠加/AI 水印/语录库 | — |
| restore_and_mix_audio.py | 08-05 | 08-05 | 音频恢复与混音 | — |
| monitor_faceswap.py ／ retry_optimized.py ／ retry_failed_videos.py ／ hf_speed_test.py | 08-05 | 08-05 | 换脸监控/重试器/HF 下载测速 | — |
| run_full.py ／ run_fix.py ／ run_autofps.py ／ run_e2e_autofps.py ／ run_workflow_verify.py ／ wait_verify.py（＋v2_*_api_prompt.json ×5） | 08-05 | 08-05 | 工作流运行/修复/自动补帧/验证运行器 | — |
| zombie_* 系列 ×14（zombie_v3_ep1 / zombie_v4 / zombie_pipeline / zombie_postprocess(_v2) / zombie_batch_* 等） | 08-05 | 08-05 | 僵尸题材批量视频流水线（多代并存） | — |
| download_unet.py ／ download_unet_fast.py ／ download_unet_resume.py ／ download_unet_model.py ／ download_qwenvl.py ／ download_idm_vton.py | 08-05 | 08-05 | 模型下载器（多版本断点续传） | — |
| faceswap_tryon_pipeline_v2.py ／ video_tryon_pipeline_v2.py | 07-31 | 07-31 | 换脸+试衣/视频试衣 v2 | — |
| run_all.ps1 ／ s.ps1 ／ start_comfyui.ps1 | 07-27 | 07-27 | 批量运行/快捷启动/ComfyUI 启动 | 单实例纪律适用（多实例显存争用教训） |

---

## 七、子目录与数据文件

| 名称 | 类型 | 创建 | 说明 |
|---|---|---|---|
| ootd_study/ | 目录 | 10-02 | OOTD 试衣研究与纯姿态提取（被 extract_full_poses 引用） |
| motion_clone/ | 目录 | 10-02 | 动作克隆子项目 |
| _viggle/ ／ _scratch_h3/ ／ tmp_faceswap_verify/ | 目录 | 10-01/09-28/08-15 | 临时草稿/验证目录 |
| workflows/ | 目录 | 07-27 | 工作流 JSON 库（v2/v3/v5 等，各管线的基底） |
| models/ | 目录 | 06-09 | 本地模型 |
| yt-dlp/ ／ v2/ ／ tiktok-downloader(-app)/ ／ faceswap_app/ ／ compare/ | 目录 | 07-08~08-15 | 独立子项目/下载器 |
| __pycache__/ | 目录 | 07-31 | Python 缓存 |
| 进度/账本类 JSON：hazy_lazy_progress.json、fp8_300(_en)_progress.json、batches_submitted.json、batch_run_status.json、speedtest_times.json、fix_verify_submitted.json、huimou_*.json、50xiezhen_pids.json、h3_24segs_pids.json、*_pids.json 等 | 数据 | 08-29~09-05 | 各批量任务的进度/进程号存档（历史运行痕迹） |
| 报告类 MD：avatar_final_report.md、avatar_smoke_test_record.md、LTX-2.3_deletion_record.md、README_tryon.md | 文档 | 08-05~08-15 | 各时期工作记录 |
| 日志：batch_run.log、night_watcher.log、wan22_download(.log)、faceswap(.log)、download_qwenvl(.log)、idm_download.log 等 | 日志 | 06-09~10-02 | 历史运行日志 |
| _final.py ／ _tidy.py ／ _final_out.txt ／ _tidy_out.txt | 临时 | 09-28 | 一次性整理脚本 |

---

## 八、跨脚本共性规则与已知坑（现行有效）

1. **CDP 入口纪律**：所有 Flow/Muse 自动化先跑 `launch_flow_cdp_chrome.bat`（9222 + 独立 profile `flow_chrome_profile` + 代理 7897）；agent 经 Playwright `connect_over_cdp` 接管；同一 profile 禁止双开。
2. **积分风控**：Flow 每日 100 credits 硬熔断（`flow_credit_ledger.json`），提交前必读 UI 实际成本。
3. **长任务纪律**：只提交不轮询（`--submit-only`）；任务先落 SQLite 再执行（comfy_sqlite_queue.py）；产物按 `output/YYYY-MM-DD/<项目>/` 归档。
4. **单实例纪律**：16GB 卡上 ComfyUI 禁止多实例并行（显存争用会卡在 Model Initializing）。
5. **音画治理**：扩散出片规整时强制 `-an` 剥离原生白噪；分段拼接用 `-map [aout]` + acrossfade 0.3；过渡默认硬切。
6. **修复定稿**：正稿 = `qwen_v4_submit.py restore --image <源图> --run --verify`（in-workflow 颗粒 0.008 + `--auto-grain` 阶梯重试；速度档 `--lightning 8` 手动），`finalize_grain.py --sigma 1.5` 仅作 fallback；体检以 restore_qa ⑧纹理形态为最终裁决（达标线 max(0.6, 源图-0.1)，判塑料前先测源图基线）。
7. **待清理**：Flow/Muse 一次性探针约 45 个已完成使命（选择器知识已并入 flow_video_automation），可归档；`_` 前缀临时脚本可清理。
8. **本机代理坑**：HTTP_PROXY 会劫持 127.0.0.1:8188 返回 502 → 访问本机 ComfyUI 一律绕代理（`_probe_*`、`_zimage_test`、`_pc_gen_*` 已内置绕代理 opener）。
9. **ReActor/insightface 坑**：`FaceAnalysis.get()` native 崩溃 → 直连 RetinaFace `det_10g.onnx`，且 QA 进程禁 import torch；受限 shell 中 nvidia-smi 不在 PATH，完整路径 `C:\WINDOWS\System32\nvidia-smi.exe`。
10. **阶段闸门与合规**：阶段切换前跑 `_drama_gate.py` 校验前置产物（防浪费积分）；Flow 提交前必跑 `prompt_safety_linter.py`（Veo 知名人物政策）；Wan Animate 服装控制走两段式（重绘参考图→ReActor 锁脸），提示词写服装无效。
