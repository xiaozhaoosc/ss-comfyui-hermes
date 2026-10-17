# AIGC 本地资产库（asset_manager）交接文档

> 更新日期：2026-10-16 ｜ 服务地址：http://127.0.0.1:8090 ｜ 代码位置：`tools/asset_manager/`

---

## 1. 系统概览

本地资产管理 + 多平台发布一体化工具，为 ComfyUI 工作流提供零显存（纯 CPU）的资产管理面。现已全面支持视频号与微信公众号（贴图消息/图文文章）全自动草稿箱归档、多图组合单篇发布、以及基于 ComfyUI PNG Prompt 元数据的标题、正文描述与话题标签智能生成。

| 项 | 值 |
|---|---|
| 后端 | FastAPI + Uvicorn + SQLAlchemy(SQLite)，运行在 ComfyUI venv |
| 前端 | 单文件 Vue3（CDN 全局构建）+ Tailwind，`dist/index.html` 直接编辑，无构建步骤 |
| 端口 | 8090（`ASSET_MANAGER_PORT`，可环境变量覆盖）；ComfyUI 委托地址 8188 |
| 数据库 | `tools/asset_manager/assets.db`（角色/服装/搭配三张表；**ComfyUI 已导入/已生成不走数据库**，按需扫描） |
| 关键依赖 | fastapi 0.136.3 / starlette 1.3.1（StaticFiles 已支持 Range 206，视频可拖进度条）/ selenium 4.51（发布用，已装入 ComfyUI venv） |

### 功能模块（前端 6 个 Tab）
1. 角色（characters）— 角色人脸库，insightface 向量相似检索
2. 服装（garments）— 服装库，透明底/白底预览切换
3. 搭配（lookbook/combos）— 角色×服装矩阵
4. **📥 已导入** — 实时扫描 ComfyUI `input/`（约 4500+ 文件）
5. **📤 已生成** — 实时扫描 ComfyUI `output/`（约 2.8 万文件，按日期/项目筛选）+ 发布入口
6. 设置 — 同步、ComfyUI API 直投开关

---

## 2. 目录结构

```
tools/asset_manager/
├── run.py                    # 启动器（uvicorn，--no-browser 跳过自动开浏览器）
├── requirements.txt          # selenium>=4.20
├── assets.db                 # SQLite
├── dist/index.html           # 前端（唯一前端文件，直接改）
├── backend/
│   ├── app.py                # FastAPI 主入口：静态挂载 + 路由注册
│   ├── config.py             # 路径与端口常量（含 COMFY_INPUT_DIR/COMFY_OUTPUT_DIR）
│   ├── database.py           # SQLAlchemy 引擎
│   ├── models.py             # ORM + Pydantic（characters/garments/combos）
│   ├── sync_engine.py        # 角色库/服装库磁盘同步
│   ├── comfy_client.py       # ComfyUI 8188 委托客户端
│   ├── routers/
│   │   ├── characters.py / garments.py / combos.py / system.py
│   │   ├── comfy.py          # ComfyUI 状态/工作流代理
│   │   ├── comfy_assets.py   # ★ 已导入/已生成扫描列表（TTL 缓存）
│   │   └── publish.py        # ★ 发布任务 API + suggest + config
│   └── publishers/
│       ├── __init__.py       # PUBLISHERS 注册表 + UPLOAD_POST_PLATFORMS
│       ├── selenium_base.py  # ★ 共享骨架：Chrome profile / 填表 / _auto_confirm 自动发布
│       ├── douyin.py / kuaishou.py / shipinhao.py   # 国内视频平台
│       ├── wechat_mp.py      # ★ 公众号三模式（视频素材/贴图/文章）
│       └── upload_post.py    # 海外平台（YouTube/Instagram/X 经 Upload-Post API）
├── publish_config.json       # Upload-Post Key + default_tags（已 gitignore，勿提交）
├── publish_jobs/             # 任务状态 JSON 落盘（已 gitignore）
└── browser_profiles/         # 各平台 Chrome 持久化登录态（已 gitignore）
```

---

## 3. 启动 / 重启

```powershell
# 正常启动（仓库根目录）
d:\ai_projects\ComfyUI\venv\Scripts\python.exe tools\asset_manager\run.py --no-browser

# 重启已运行实例（改代码后必须重启，无 --reload）
$conn = Get-NetTCPConnection -LocalPort 8090 -State Listen | Select-Object -First 1
Stop-Process -Id $conn.OwningProcess -Force
Start-Process -FilePath "d:\ai_projects\ComfyUI\venv\Scripts\python.exe" `
  -ArgumentList "tools\asset_manager\run.py --no-browser" `
  -WorkingDirectory "d:\ai_projects\ComfyUI" -WindowStyle Hidden
```

注意：`publish_jobs/` 中状态为 pending/running 的任务在重启时会被标记 failed，**不会自动重跑**。

---

## 4. API 清单

### 4.1 已导入/已生成扫描（`/api/comfy-assets`）
| 端点 | 说明 |
|---|---|
| `GET /{source}/files` | source=`input`/`output`；参数 `media`(all/image/video)、`date`/`project`(仅 output)、`page`、`page_size`(≤200)、`refresh`(跳过缓存强制重扫)。返回 `{total,page,page_size,items[]}`，item 含 `rel_path/media/size/mtime/name/preview_url`，mtime 倒序 |
| `GET /output/tree` | output 两级目录树 `[{date, projects[]}]` 日期倒序 |

**性能要点**：扫描结果按 `(source, base目录)` 缓存 10 秒（TTL）。实测 output 冷扫 1.5~2.1s，缓存翻页 ~50ms。缓存无法感知深层文件变化（目录 mtime 不可靠），所以前端提供刷新按钮 + 新文件落盘后 10 秒内自然过期。

**安全**：`date`/`project` 是不可信输入，`_resolve_segment` 拒绝 `..`/分隔符/盘符/绝对路径，且 resolve 后必须仍在根目录内。

### 4.2 发布（`/api/publish`）
| 端点 | 说明 |
|---|---|
| `POST /jobs` | body: `{file_rel_path, platforms[], title, tags?, upload_post_key?, publish_mode, media_type}`；每平台一个 job 后台线程执行 |
| `GET /jobs` / `GET /jobs/{id}` | 任务列表（无日志）/ 详情（含日志） |
| `GET /suggest?file_rel_path=` | **标题/标签自动生成**：文件名去尾部时间戳(_HHMMSS[_N])做标题（≤30 字），目录层级 + `default_tags` 做标签（≤8 个） |
| `GET/POST /config` | Upload-Post key/user + `default_tags` 读写，落盘 `publish_config.json` |

**关键字段**：
- `publish_mode`：`publish`（默认，自动点发布按钮）｜`draft`（自动存草稿）｜`manual`（仅填表，停确认页等人工）
- `media_type`：`video`｜`images`（公众号贴图）｜`article`（公众号图文文章，图片模式）。后两者仅允许 `platforms=["wechat_mp"]` 且文件必须是 jpg/jpeg/png/webp
- job 状态机：`pending → running → success | failed | need_login`

### 4.3 其他
- `GET /api/system/stats`、`POST /api/system/sync`（角色/服装库全量重扫）
- `GET /api/comfy/status`、`POST /api/comfy/dispatch`（工作流代理提交到 8188）

---

## 5. 发布流程详解

### 5.1 国内视频平台（抖音/快手/视频号）— Selenium
统一骨架 `selenium_base.run_publish_flow`：
1. 有头 Chrome，profile 目录 `browser_profiles/<platform>/`（**登录态持久化，首次发布需人工扫码一次**）
2. 调度机制：已引入平台级排队互斥锁（`_PLATFORM_LOCKS`），避免并发任务争抢同平台 Chrome profile。
3. 打开创作者上传页 → 等 `input[type=file]`（20s 超时 → `need_login`，窗口保留）→ `send_keys` 注入视频绝对路径
4. `fill_form`：各平台等待"标题/描述框出现"作为上传完成信号（最长 180s），填标题（抖音 30 字/快手 450 字/视频号 20 字截断）+ 逐个 `#话题`（快手最多 3 个）+ 自动确认首选视频封面（视频号）。
5. **确认发布/存草稿**（`_auto_confirm`，AUTO_CONFIRM_TIMEOUT=240s）：
   - `publish_mode="draft"`：按 `DRAFT_XPATHS` 自动定位「存草稿」按钮，严格排除「发表/发布/群发/定时」等操作，点击后监听「保存成功/草稿保存成功」Toast 提示与页面跳转，全自动完成闭环；
   - `publish_mode="publish"`：按 `CONFIRM_XPATHS` 轮询可见发布按钮，排除草稿/定时；
   - 原生 click 失败则 JS click，每 6 秒一轮；
   - 离开上传页或检测到成功 Toast = success（浏览器自动优雅关闭）；
   - 超时未生效 → 自动降级 `_wait_manual_confirm`（保留窗口，等人工最长 600s）。

各平台上传页与选择器：
- 抖音 `creator.douyin.com/creator-micro/content/upload`：标题 `input.semi-input`；简介 `div[data-placeholder="添加作品简介"]`
- 快手 `cp.kuaishou.com/article/publish/video`：描述 `div[placeholder*="添加合适的话题和描述"]`
- 视频号 `channels.weixin.qq.com/platform/post/create`：标题按 placeholder 匹配；简介 `div.input-editor`；存草稿 XPath 已完备（含自动封面适配）

### 5.2 公众号（`wechat_mp.py`）三模式草稿箱全自动
- **video（视频消息草稿）**：优先寻找「视频消息/新建视频」草稿入口（或从草稿箱 `type=10` 列表新建）→ 注入视频 → 填标题 → 自动确认默认封面帧 → `publish_mode="draft"` 时点击「保存为草稿」并轮询 Toast 提示自动判定 success；
- **images（贴图消息草稿）**：图片消息入口注入图片 → 填标题 → 点击「保存为草稿」→ 监听成功 Toast 全自动完成；
- **article（图文文章草稿）**：图文编辑器注入正文图片 → 从正文提取封面 → 点击「保存为草稿」→ 监听成功 Toast 全自动完成。

**公众号特殊限制**：
- mp 后台是重 iframe 富页面，自动化脆弱——**每一步失败都写日志并降级人工窗口**，不抛异常中断
- 「发表/群发」可能弹管理员扫码确认，微信强制，只能人工
- 每步都在主文档和一层 iframe 里找元素，嵌套 iframe 内的控件找不到（已知局限）

### 5.3 海外平台（YouTube/Instagram/X）— Upload-Post API
- 单次 multipart POST `https://api.upload-post.com/api/upload`，header `Authorization: Apikey <key>`，字段 `user`/`title`/`platform[]`（与 MoneyPrinterTurbo 源码一致）
- key 存 `publish_config.json`；无 key/user 时该平台 job 直接 failed 带提示
- 仅在用户点发布时发起外网请求

### 5.4 前端发布交互（`dist/index.html`）
- 视频卡片/图片卡片「🚀 发布」→ 对话框：**打开即调 suggest 自动填标题标签（可改）**
- 视频：发布方式三选一（自动发布/存草稿/仅填表）+ 国内四平台 + 海外三平台 + Upload-Post Key 输入
- 图片：只显示公众号贴图/文章两个选项（id 为 `wechat_mp_images`/`wechat_mp_article`，提交时映射为 `platform=wechat_mp` + `media_type`）
- 「📋 发布任务」按钮 → 任务面板 3 秒轮询，行展开看日志，need_login 黄/failed 红/success 绿

---

## 6. 前端结构与要点

- 单文件 Vue3，`createApp({...}).directive('lazy-video', lazyVideo).mount('#app')`，Tab 用 `currentTab` + `<section v-if>` 切换
- **`v-lazy-video` 指令**（性能关键）：视频卡片 src 存 `data-src`，IntersectionObserver（rootMargin 300px）进视口才赋 `src`，否则一页 60 个 `<video preload="metadata">` 会同时拉流拖慢打开
- 分页 = `fetchXxxFiles(page, append, refresh)`，「加载更多」追加；筛选切换重置到第 1 页
- 改完前端无构建，刷新浏览器即生效；改后端必须重启服务
- 修复过的存量 bug：`fetchCharacters`/`fetchGarments` 曾漏在 setup return 外

---

## 7. 验证状态（2026-10-15）

| 项 | 状态 | 证据 |
|---|---|---|
| 扫描 API（过滤/排序/分页/筛选/穿越拒绝/空目录） | ✅ | TestClient 离线断言 + 真实服务冒烟（input 4551 / output 28402 项） |
| 缓存性能 | ✅ | 冷扫 1.5~2.1s → 缓存翻页 48ms |
| Range 视频拖进度条 | ✅ | face_ref.mp4 range 0-1023 → 206 |
| 发布任务生命周期/落盘重载/穿越/未知平台/无 key failed | ✅ | `test_publish.py` 8/8 全通过 |
| 存草稿模式调用链 | ⚠ 未完成真实端到端验收 | 8 项单测只覆盖 API 参数与后台任务状态，不会启动浏览器或验证平台草稿箱 |
| 多图组合发布（公众号贴图/文章） | ✅ | 前端浮动批量栏 + 对话框候选网格 + `file_rel_paths` 批量上传注入 |
| 智能元数据建议（标题/正文/标签） | ✅ | 后端解析 ComfyUI PNG Prompt 元数据与目录结构，自动映射风格为自然中文 |
| 同平台并发互斥锁 | ✅ | 已实现 `_PLATFORM_LOCKS` 平台线程排队锁；Chrome profile 清理尚未有真实残留进程验证 |
| 自动点发布（真实平台端到端） | ⚠ 待人工验收 | 需用户在场扫码登录后跑一次；选择器基于当前平台界面实现 |
| 海外平台真实上传 | ⚠ 待人工验收 | 需先在发布对话框填 Upload-Post API Key |

运行 `tools/asset_manager/test_publish.py` 即可复跑发布后端测试（8/8 通过，不弹浏览器、不发真实请求）。

---

## 8. 已知限制与使用说明

1. **同平台排队锁已就绪**：同一平台的多任务会自动排队（`_PLATFORM_LOCKS`），避免 Chrome Profile 被锁崩溃；启动前会自动清理残留僵尸 Chrome 与 lockfile。
2. **自动存草稿/确认超时降级**：平台转码慢或出现强制人工验证时会保留窗口等待人工接管（最长 600s）；未检测到明确成功提示时任务标为 failed，避免将未验证结果误报为成功。
3. **output 目录深层文件变化**：TTL 缓存 10 秒内不感知，新渲染完的文件要等过期或点刷新。
4. **ComfyUI 依赖环境**：必须使用 `d:\ai_projects\ComfyUI\venv\Scripts\python.exe` 运行。

---

## 9. 后续可做（按优先级）

1. **真实平台端到端验收**：公众号视频/贴图/文章与视频号分别跑一次 draft，人工核对草稿箱确有对应内容；根据真实页面日志校正入口、编辑器和草稿按钮定位。
3. 公众号文章封面自动化补全（「从正文选择」弹窗内多步确认）
3. 批量发布（多视频 × 多平台排队）与发布历史持久化视图
4. 图片资产生成视频封面缩略图（后端 ffmpeg 抽帧），替代 `preload="metadata"` 方案进一步省流量

---

## 10. 快速排障

| 症状 | 处置 |
|---|---|
| 页面 502/打不开 | 服务没起，按 §3 重启 |
| 已生成翻页突然变慢 | TTL 缓存过期，属正常（一次全扫）；持续慢则检查 output 文件数是否暴涨 |
| 发布任务卡 running 很久 | 看 job 日志：大概率在等上传完成（最长 180s）或降级人工窗口等确认（600s） |
| need_login | 在弹出的浏览器里扫码登录，**登录态已存 profile，之后不用再扫**；然后重新发起发布 |
| 视频发布失败但找不到原因 | `publish_jobs/<job_id>.json` 有全程日志；先确认平台创作者页面手动能否上传（平台改版 → 更新 CONFIRM_XPATHS） |
| 改了后端不生效 | 忘了重启服务（无 --reload） |
