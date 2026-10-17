# HANDOVER · 2026-10-11 · Instagram 下载器与通用媒体下载器 media_dl

> **会话主题**：Instagram 博主下载打通 + 通用媒体下载器 `media_dl`（CLI / 网页 / 桌面三端）
> **时间跨度**：2026-10-11 15:20 ~ 23:10
> **接手人请先读**：第 3 节（核心结论）、第 7 节（待办）、第 9 节（复现命令）

---

## 1. 一句话摘要

本次会话把 Instagram 下载从**「被账号级 429 完全阻断」打到「可用」**——突破口不是等解禁，而是**换端点族**（用 gallery-dl 走 `graphql/query`）；顺带做出了一个**通用媒体下载器 `media_dl`**（CLI + 网页 + 桌面三端共用一套 core），并新增了**可选的 9222 探测功能**。

---

## 2. 本次会话做了什么（时间序）

| 时间 | 事件 | 结果 |
|---|---|---|
| 15:20 | 检查 `tools/` 有无 IG 下载工具 | 无专用工具；发现 `tools/yt-dlp/yt-dlp.exe` 存在但其 `instagram:user` 标 BROKEN |
| 15:30~16:10 | instaloader 方案 | 链路前三段通（CDP 取 cookie → `load_session` → `test_login` 返回 `ken.zhao.986`），第四段被 `web_profile_info` **429** 阻断 |
| 16:10~18:00 | 排查 429 根因 | 与匿名/登录、两个代理出口（11205/7897）、Python vs 浏览器内 fetch **全都无关**；浏览器自身也不渲染帖子网格 → **判定账号级限制** |
| **18:20** | **换 gallery-dl 当主引擎** | ✅ **打通**：走 `POST /graphql/query`（带 `lsd`+`fb_dtsg` token）返回 200，下到真实 mp4 |
| 18:50~22:50 | 建通用下载器 `media_dl` | ✅ 三端共用 core；站点自动识别；Popen 流式执行；统一续传 |
| 22:06 | ⚠️ **升级 ComfyUI v0.39.1 时整个 `tools/` 被重置** | `tools/*.py` 全消失（含刚写的两个工具）→ 从备份提交 `4d7c00747` **完整恢复 12 个文件** |
| 22:57~23:10 | 新增 9222 探测（四端）+ ayano.fj 测试下载 | ✅ archive 3→4、文件 3→4、**旧文件 mtime 未变**（证明续传跳过） |

---

## 3. 已完成进度（含验收证据）

### 3.1 `tools/ig_download.py`（45,728 字节）

Instagram 主页下载器，**三引擎择优**：`gallery-dl`（主）→ `yt-dlp`（次）→ `instaloader`（兜底）。

- 三种模式：`--count N`（前 N 条，含置顶帖规避）/ `--days N`（滚动时间窗）/ 默认全量
- 登录态：`--cookies-file`（给了它**完全不碰 CDP**）/ CDP 9222 自动取 / `--anonymous`
- 新增 `--probe-cdp`：只探测端口与登录态，不下载
- 含 `--dry-run`、图片/视频过滤、断点续传、产物校验（文件头 + cv2 验帧可选）

**验收证据**：
- `--count 2` 下到真实 mp4，**720×1280，305 / 438 帧**，cv2 验帧通过
- `--days 3` 正确命中 1 条（排除 4 天前那条）
- 全量 dry-run 枚举 **69 条文件**（账号约 68 帖）
- `--count 4`：archive 3→**4**，文件 3→**4**，**原 3 个文件 mtime 完全未变**，无 `.part` 残留

### 3.2 `tools/media_dl/`（14 个文件）

通用媒体下载器，**三端共用 `core/`**：

```
tools/media_dl/
├── __init__.py  __main__.py          # CLI 入口
├── core/                              # __init__ archive cookies engines jobs model runner sites
├── web/  server.py  static/index.html # 标准库 http.server + SSE，零新增依赖、零 CDN
└── qt/   __init__.py app.py           # PySide6 桌面端
```

- **站点自动识别**（三层）：`HOST_RULES` → `gallery_dl.extractor.find()` **离线探测**（零网络请求）→ 兜底启发式
  实测：instagram→gallery-dl、youtube→yt-dlp、pixiv→gallery-dl、bilibili→yt-dlp 全部正确
- **重启续传**：`import_legacy()` 能自动迁移 `ig_download.py` 时代的旧归档

**验收证据**：CLI simulate 通过；网页 `/api/engines`、`/api/probe`、`/api/cdp`、任务提交、SSE 全部实测通；Qt 端验证到「可导入」；续传实测见 3.1

### 3.3 9222 探测功能（可选 · 仅展示）

`core/cookies.probe_cdp(port, username)`，**四端入口齐备**：

| 端 | 入口 |
|---|---|
| CLI | `python tools/media_dl --probe-cdp [--probe-port] [--json]` |
| 网页 | `GET /api/cdp?port=9222` + 页面「检测 9222」按钮与状态徽标 |
| 桌面 | Qt 窗口「检测 9222」按钮 |
| 脚本 | `python tools/ig_download.py --probe-cdp` |

**实测输出**：`Chrome/154.0.8037.98` + 检测到 IG 页面 + 10 条 cookie + 已登录 `ken.zhao.986`

> ⚠️ **设计要求（请勿改动）**：探测**只展示状态，绝不自动改变行为**。`JobSpec.use_cdp` 的开关语义保持不变。

### 3.4 产物现状

`D:/ai_projects/ComfyUI/output/2026-10-11/instagram_ayano_fj/`（合计 ≈10.7 MB）

| 文件 | 字节 | 说明 |
|---|---|---|
| `2026-10-05_05-59-28_DeGg3wkgn4p_1.mp4` | 1,506,499 | 本次新增 |
| `2026-10-06_11-59-04_DeJu0mmA4jW_1.mp4` | 2,889,384 | |
| `2026-10-07_12-56-14_DeMaIN9gB3Q_1.mp4` | 3,370,166 | |
| `2026-10-09_12-54-23_DeRjgPHgZAK_1.mp4` | 3,439,517 | |
| `_gallery_archive.txt` | 8,192 | **实为 SQLite**，表 `archive(entry TEXT PRIMARY KEY)`，4 条 |
| `_media_dl_archive.sqlite` | 8,192 | media_dl 的统一续传主库，4 条（已对齐） |

---

## 4. 核心结论（技术要点，交接最关键）

1. **★ 最大突破：gallery-dl 绕开 429 的方式是「换端点族」**
   instaloader 的 `Profile.from_username` **只走** `api/v1/users/web_profile_info/` 且**源码里没有回退路径**；
   gallery-dl 走 `POST https://www.instagram.com/graphql/query`（带 `lsd` + `fb_dtsg` token）→ **不受该端点限流影响**。

2. **引擎分工**
   gallery-dl = 图库/社交（pixiv / reddit / 微博 / 小红书 / Instagram / X）；yt-dlp = 视频平台（YouTube / B站 / Vimeo / TikTok）。
   instaloader 已降为兜底。**两者都吃 Netscape cookies.txt，一套 cookie 通吃。**

3. **★ 进度唯一可信源 = `Archive.count()`**
   已从 gallery-dl 源码确认：非 TTY 时走 `PipeOutput`，**skip 与 success 输出完全同形**，
   所以**绝不能数 stdout 行数**来算进度，必须 `SELECT COUNT(*) FROM archive`。

4. **★ 流式执行** `core/runner.run_stream()`
   `Popen(stdout=PIPE, stderr=STDOUT) + pump 线程 + cancel.wait(0.2)`，
   取消/超时走 `taskkill /PID x /T /F`（Windows）/ `os.killpg`（POSIX）杀整个进程树。
   这是替代 `subprocess.run(capture_output=True)`（阻塞、UI 全黑）的关键。

5. **统一续传**
   主库 `_media_dl_archive.sqlite`（gallery-dl 原生就是 SQLite，直接指过去，可并发读）；
   yt-dlp 只吃文本 → 跑前 `export_to_text()` 预热、跑后 `sync_from_text()` 回灌；
   `import_legacy()` 迁移旧 `_gallery_archive.txt`（SQLite）与 `_ig_state.json`（shortcode 列表）。

6. **登录态三通道**：CDP 9222 自动取 / `--cookies-file` / 网页粘贴。
   一律转 Netscape 临时文件（`mkstemp` + 收紧权限），**用完即焚**（finally + atexit + 启动清理超 1h 残留）；
   用户自带的文件**永不删除**（`drop_cookie_file(path, ours=False)` 直接 return）。

7. **判登录必须用 `test_login()`**，不能用 `InstaloaderContext.is_logged_in`——源码里它只是 `return bool(self.username)`，**恒真不可信**。

---

## 5. 重点问题与踩坑记录

| # | 现象 | 根因 | 处置 |
|---|---|---|---|
| 1 | 首次请求即 `429 Too Many Requests` | Instagram **账号/路由级限流**，与匿名/登录、代理出口、Python vs 浏览器 **全都无关** | 换 gallery-dl（不同端点族），不再重试轰炸 |
| 2 | 主页 HTML 200 但 645KB | 是**空壳**（无 `additionalDataLoaded` / `__NEXT_DATA__`）；浏览器自身也不渲染 `article` 网格 | 放弃 HTML/DOM 采集路线 |
| 3 | 判登录一直为真 | `is_logged_in` 恒真 | 改用 `test_login()` 返回值 |
| 4 | 枚举结果数为 0 | gallery-dl `--simulate` 输出每行带 **`# ` 前缀**，被误当注释过滤 | 计数所有非空行（**踩了两次**） |
| 5 | 输出目录下不到预期位置 | gallery-dl **`-D` 是 exact location**，`-d` 才是 destination | 用 `-D` |
| 6 | 新工具续传失效 | 目录名一度生成 `instagram_ayano.fj`（点），与旧的 `instagram_ayano_fj`（下划线）**不一致** | 统一 `re.sub(r"[^A-Za-z0-9_-]", "_", ...)` |
| 7 | `available` 报 yt-dlp 不可用 | yt-dlp 是**独立 exe，不在 PATH** | 走 `default_ytdlp_exe()` 显式取路径 |
| 8 | `core/__init__.py` 导入报错 | 误 import 不存在的 `.events`（`EventBus` 实际在 `model.py`） | 修正导入 |
| 9 | **⚠️ 22:37 `tools/*.py` 全部消失** | **升级 ComfyUI v0.39.1 会重置 `tools/`** | 从备份提交 `4d7c00747` 恢复 |

---

## 6. 遗留问题（明确未解决）

1. **instaloader 老路仍被账号级封锁** —— 不打算再修，已用 gallery-dl 绕开；若要用 instaloader 需先确认端点解禁。
2. **`media_dl` 的总数（`total`）不可靠** —— 只能靠 `--total-hint` 手填、运行时 `Downloading item N of M` 补正，或额外一次 `--simulate` 探测（有轻微 429 风险，未默认开启）。
3. **网页端 SSE 不做事件重放** —— 断连后用 `/api/jobs/<id>` 快照兜底，`Last-Event-ID` 重放未实现。
4. **Qt 端只验证到「可导入 + 构造 Worker」** —— 未做真机点按全流程测试。
5. **`media_dl` 未做过真实站点的全量压力验证** —— 只在 Instagram 上验证过小批量。
6. **代理端口注记需注意** —— 本机环境变量代理为 `127.0.0.1:11205`；Hitomi 那条线用的是 `7897`（非 7890）。两套不要混。

---

## 7. 待办 TODO

- 🔴 **【最高优先级】把新工具提交进 git**
  `tools/` 已经被 ComfyUI 升级重置过一次。`ig_download.py` 与 `media_dl/` 目前**仍未提交**（只是从旧备份 commit 恢复的副本），下次升级还会丢。
- 🟡 `media_dl` 找一个真实站点（如 YouTube / pixiv）跑一次全量，验证多引擎与限速表现。
- 🟡 补网页端 SSE 的 `Last-Event-ID` 重放，替代当前的快照兜底。
- 🟡 Qt 端做一次真机点按验证（开始/取消/打开目录）。
- 🟢 支持 Story / Highlight（gallery-dl 侧 URL 已清楚：`/stories/<user>/`、`/<user>/highlights/`）。
- 🟢 多站点并发队列（当前是全局 `Semaphore(1)` 串行，为保护账号刻意如此）。

---

## 8. 后续优化建议

1. **cookie 过期友好提示** —— 现在是 `test_login()` 返回空才报错，可提前解析 `sessionid` 的 `expires` 并预警。
2. **`total` 自动探测并缓存** —— `--simulate` 结果写入 `<dir>/_media_dl_meta.json`（带时间戳，24h 内复用）。
3. **Qt 打包成 exe** —— PyInstaller 打包，免去同事安装 Python 环境。
4. **多账号队列** —— 当前仅按 URL 维度串行；若要多账号并行需扩展 `locks.py` 的跨平台锁。
5. **`ig_download.py` 瘦身** —— 它的引擎调度与 `media_dl/core` 有重复，可改为 core 的薄封装（当前刻意保留独立，避免破坏已验证路径）。

---

## 9. 复现与关键路径速查

### 9.1 解释器（**必须用这个 venv，anaconda3 里没有这些包**）

```
C:/Users/kenzhao/.workbuddy/binaries/python/envs/default/Scripts/python.exe
```

### 9.2 Instagram 下载

```bash
PY=C:/Users/kenzhao/.workbuddy/binaries/python/envs/default/Scripts/python.exe

# 只探测 9222（不下载）
$PY tools/ig_download.py --probe-cdp

# 用 cookies 文件下最新 4 条（已下过的自动跳过）
$PY tools/ig_download.py ayano.fj --count 4 --sleep 3 \
    --engine gallery-dl --cookies-file "d:/instagram_cookies.txt"

# 最近 7 天 / 全量 / 只枚举
$PY tools/ig_download.py ayano.fj --days 7
$PY tools/ig_download.py ayano.fj
$PY tools/ig_download.py ayano.fj --dry-run
```

### 9.3 通用下载器 media_dl

```bash
# CLI
$PY tools/media_dl "https://www.instagram.com/ayano.fj/" --count 4
$PY tools/media_dl --probe-cdp

# 网页（浏览器打开 http://127.0.0.1:8765）
$PY tools/media_dl web --port 8765

# 桌面
$PY tools/media_dl qt
```

### 9.4 恢复被 ComfyUI 升级重置的 `tools/`

```bash
cd /d/ai_projects/ComfyUI
git checkout 4d7c00747 -- tools/ig_download.py tools/media_dl/
# 通用写法：git checkout <备份commit> -- tools/<目标路径>
```

---

## 10. 环境与依赖现状

| 项 | 值 |
|---|---|
| 隔离 venv | `C:/Users/kenzhao/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（Python 3.13.14） |
| gallery-dl | **1.32.16** |
| instaloader | **4.15.3** |
| websocket-client | 1.9.2 |
| PySide6-Essentials | **6.12.0**（仅桌面端需要） |
| requests | 2.34.2 |
| yt-dlp | `tools/yt-dlp/yt-dlp.exe` = **2026.08.19**；旧版备份 `tools/yt-dlp/yt-dlp-2026.07.04.exe.bak`（18.2 MB） |
| Chrome 9222 | ✅ 可用，`Chrome/154.0.8037.98` |
| cookies 文件 | `d:/instagram_cookies.txt`，**804 字节**（内容不外泄，仅记路径与大小） |

> 🔒 **安全纪律**：cookie 值**不得**写入任何文档、日志、JSON 或命令行回显。本工具链已内置 `redact()` / `note_secret()` 机制。

---

## 11. 今日全局索引（其他工作线）

本次会话只覆盖下载器这一条线。今日其他工作在各自文档里：

| 工作线 | 文档入口 | 状态 |
|---|---|---|
| 杨家将 EP01-07 前期制作 | `HANDOVER_2026-10-11_YANGJIAJIANG_EP01-07_PREPRODUCTION.md` | 已完成阶段性 |
| 杨家将前四集镜头切片对比 / EP04 剧情一致性修复 | `HANDOVER_2026-10-11_杨家将前四集镜头切片对比与EP04剧情一致性修复.md` | 已完成 |
| 换装视频工作流 | `仅换装视频工作流_交接文档_2026-10-11.md` | 进行中 |
| 动漫短剧资产管线 | `AI_DRAMA_RUNBOOK.md` + `tools/_drama_char_sheet.py` | 5/5 视图已验证 |
| WanAnimate B 方案全量重跑 | （今日 memory 日志） | **进行中**（索引 5–22 / 152 chunks） |
| ComfyUI 升级 v0.39.1 + 分支迁移 | 提交 `03baf2f4e`；前端已升 **1.55.16** | 已完成 |
| ⚠️ `tools/` 重置事件 | 本文件第 5 节 #9、第 9.4 节 | 已恢复 |

---

## 12. 给接手人的三条提醒

1. **任何新写的脚本，写完就提交**。本项目 `tools/` 会被 ComfyUI 升级重置——今天已经丢过一次。
2. **别再用 instaloader 拼 Instagram**，它那条 `web_profile_info` 路已废；直接用 gallery-dl。
3. **progress 只能信 `Archive.count()`**，别改回数 stdout（skip 和 success 输出长得一样）。
