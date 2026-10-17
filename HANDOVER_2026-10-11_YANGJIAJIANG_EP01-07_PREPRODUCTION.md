# 《北宋杨家将》竖屏短剧 · 前期资产交接文档

> **交接日期**：2026-10-11
> **交接范围**：第 1 / 5 / 6 / 7 集前期资产（剧情脚本 + Flow 九宫格 + 切片首帧）+ 第 4 集剧情修复 + Flow 自动化工具链改造 + 资产对账 + 第 8 集续产计划
> **当前整体进度**：**7 / 24 集**（EP01-EP07 前期资产齐备；EP08 续产计划已定，源料已取）
> **工作区**：`D:\ai_projects\ComfyUI`　｜　**操作系统**：Windows 11　｜　**显卡**：RTX 4060 Ti 16GB

---

## 一、今日完成清单（按时间序）

### 1. 范围确认与 EP04 剧情修复
- 通读近 2 天全部文档，确认缺口：EP01 为旧 41 镜 / 16:9 样片范式（与现行 54 镜 / 9:16 不符）；EP05《误卯牌》完全空白。
- 修复 EP04 元数据 **4 处剧情断点**（`tools/yangjiajiang_ep04_metadata.py`）：
  1. 开篇年份/文案矛盾（原"太平兴国四年·亲征北汉"→改为"太平兴国五年·游幸邠阳"，与 EP03 衔接）
  2. 韩延寿左臂旧伤未延续（第 28 镜补"左臂裹素布"）
  3. 二郎阵亡缺镜（第 33 镜改为"力竭殒身"）
  4. 第 36 镜"三旗"归属不明（明确为延平/延定/延广三杆将旗）

### 2. 新建 4 集完整前期资产（EP01 / EP05 / EP06 / EP07）

| 集数 | 标题 | 分幕（6 幕） | 源料 |
|---|---|---|---|
| EP01 | 北汉风雪 | 代州受印／晋阳初战·一箭衔马／夜劫空营·留白爆闪／塞北连雨·借雨设伏／止戈讲和·太祖托孤／晨光北征·救晋诏书 | 册1 页1-41（41镜扩写） |
| EP05 | 误卯牌 | 辽犯中原·点将／边关扎营·保官应战／误卯牌·松绑／调离保官·执手泪别／下战书·陈家谷伏兵／抗辩·四十大板·潘仁美冷笑 | 册3 页1-35（31镜扩写） |
| EP06 | 李陵碑·殉国 | 边关请令·谷口之约／两道谷口·连破辽阵／陈家谷·万箭断后／谷道黄昏·百人同跪／土岗·李陵碑殉国／潘营夜·七郎蒙难 | 册3 页36-70（31镜扩写） |
| EP07 | 七郎之死 | 芦林认尸·黄河断肠／土岗认父·葬父断戈／孤枪突围·雪落双坟／五台山·禅杖松手／汴京渡口·贼船脱险／街市流言·八王收状 | 册3 页64-88（29镜扩写） |

每集规格统一：**54 镜 / 6 组九宫格 / 214.0s / 竖屏 9:16**，镜长仅用 2/3/4/5s。

### 3. 工具链改造（关键工程产出）

| 文件 | 说明 |
|---|---|
| `tools/yangjiajiang_flow_grids.py` | **通用「九宫格生成 + 3×3 切片」器**（由 EP04 试点脚本参数化，支持任意集数；`--ep N --all` / `--slice-all`） |
| `tools/_flow_cdp.py` | **原生 CDP WebSocket 驱动**（绕过失效的 Playwright，含真实鼠标点击/insertText/截图/取图） |
| `tools/yangjiajiang_flow_grid_prompts.py` | EP01/05/06/07 共 **24 组**九宫格英文提示词（人物全脱敏，含朱砂纪律断言） |
| `tools/yangjiajiang_ep01/05/06/07_metadata.py` | 各集 54 镜元数据（sub 解说 / tag 名片 / visual 画面 / camera / sfx / bgm） |

---

## 二、资产清单与位置

### 2.1 本次产出（`D:\ai_projects\ComfyUI\output\2026-10-11\`）

| 集 | 目录 | grids(768×1376) | frames(544×960) | 速览图 | 分镜表 | 体积 |
|---|---|---|---|---|---|---|
| EP01 | `yangjiajiang_ep01\` | 6 | 54 | 6 | 1 | 14.6 MB |
| EP05 | `yangjiajiang_ep05\` | 6 | 54 | 6 | 1 | 14.3 MB |
| EP06 | `yangjiajiang_ep06\` | 6 | 54 | 6 | 1 | 14.0 MB |
| EP07 | `yangjiajiang_ep07\` | 6 | 54 | 6 | 1 | 14.5 MB |

每集子目录结构一致：
```
yangjiajiang_epXX/
├── grids/        九宫格分镜总览板（6 张 PNG，每张=9 镜）
├── frames/       单镜首帧（54 张 JPG，H3/i2v 管线直接可用）
├── flow_debug/   速览图 contact sheet（6 张）+ 调试截图
└── script_ref/   54 镜分镜表（txt，含 书页/景别运镜/画面/解说/名片/音效/BGM）
```

**总账**：24 张九宫格 / 216 张首帧 / 24 张速览图 / 4 份分镜表。**全部已落盘本地，无云端依赖**（Flow 出图当场抓取写入磁盘，切片/速览由本地 PIL 完成）。

资产清单文件：[`output/2026-10-11/yangjiajiang_asset_manifest.md`](file:///d:/ai_projects/ComfyUI/output/2026-10-11/yangjiajiang_asset_manifest.md)

### 2.1b 资产对账结果（2026-10-11 已执行，逐项核验）

以脚本扫描磁盘与清单声明交叉比对，结论 **ALL OK**：

| 核验项 | 结果 |
|---|---|
| 九宫格数量/尺寸 | 4 集各 6 张，尺寸全部 768×1376 ✅ |
| 首帧数量/尺寸 | 4 集各 54 张，尺寸全部 544×960 ✅ |
| 速览图 / 分镜表 | 各集 6 张 / 1 份，无缺项 ✅ |
| 元数据镜数 ↔ 磁盘首帧 | 4 集均 54 镜 / 214.0s / 6 组，完全吻合 ✅ |
| 清单体积声明 ↔ 实测 | 14.6 / 14.3 / 14.0 / 14.5 MB，四项全对 ✅ |
| tools 模块 | 7/7 齐备 ✅ |
| Flow 积分账本 | 不存在（**非缺漏**，本日 0 积分，见 §3.4）✅ |

**遗留待清理**：EP01、EP06 各 1 个 `grids/*.prev_*.png` 旧图备份（确认新版可用后可删）。

### 2.2 历史集（口径不同，注意区分）

| 集 | 位置 | 状态 |
|---|---|---|
| EP02（归宋·天波府） | `output/2026-10-08/yangjiajiang_ep02/`（视频产物）+ `input/yang_ep02_shot01-54.jpg`（首帧） | ✅ 已出片 |
| EP03（邠阳城围） | `output/2026-10-09/yangjiajiang_ep03/` + `input/yang_ep03_shot01-54.jpg` | ✅ 已出片（720P 母带 214s） |
| EP04（邠阳城·血） | `output/2026-10-11/yangjiajiang_ep04/`（含 frames/54 张） | ✅ 资产就绪（今日修复剧情） |
| EP01 | `input/yang_ep01_shot*.jpg`（38 张 + `_v_` 变体） | ⚠️ 旧 41镜/16:9 范式，已被本次 `output/2026-10-11/yangjiajiang_ep01/` 的 54镜/9:16 取代 |

> **口径提醒**：只有本次 4 集（EP01/05/06/07）是统一的"54镜/6组/214s/9:16"范式；EP02/03/04 首帧在 `input/`，output 目录是出片产物。

---

## 三、重点问题与踩坑记录（务必阅读）

### 3.1 Flow CDP 自动化的 4 个硬坑（均已修复并固化进脚本）

| # | 现象 | 根因 | 处置（已写入脚本/项目记忆） |
|---|---|---|---|
| 1 | `connect_over_cdp` 卡死 180s 超时 | **Playwright 1.61 与 Chrome 154 不兼容**（`<ws connected>` 后死等） | 弃用 Playwright，改自写原生 WebSocket 驱动 `tools/_flow_cdp.py` |
| 2 | 点了生成按钮但静默不出图 | **JS `el.click()` 不触发 Angular Material 事件流** | 改坐标级真实鼠标事件 `Input.dispatchMouseEvent` |
| 3 | 出图是 1376×768 横屏废片 | 触发器文本含 `crop_9_16`，**子串匹配误判为"已是 9:16"** | 改为**按换行末行精确匹配**（文本形如 `Nano Banana 2.1\ncrop_9_16\n9:16`） |
| 4 | 抓不到新图 | 画廊视图缩略图域名是 `flow.google.com/asb/`，**非** `flow-content.google` | 选择器扩到 `/asb/` + `googleusercontent` 并过滤头像 |

### 3.2 环境运维坑

- **CDP WebSocket 长闲置后卡死**（HTTP `/json/version` 仍正常但连接超时）→ **杀命令行含 `flow_chrome_profile` 的 chrome 进程后重启** `tools\launch_flow_cdp_chrome.bat`。
- Chrome 重启后可能**只绑 IPv6 `::1`**（`127.0.0.1` 拒连、`localhost` 可用）→ `_flow_cdp.resolve_base()` 已按 `127.0.0.1 → localhost → [::1]` 顺序自动探测。
- Chrome 硬杀后**可能掉 Google 登录**（需人工重登）；本次重启侥幸保住登录态。
- 重启后项目会回到「All media 画廊」视图，脚本会自动 `Page.navigate` 回 project 路径。
- 跑 CDP 脚本必须用 **`C:\Users\kenzhao\anaconda3\python.exe`**（ComfyUI 的 venv 里没有 playwright/websocket）。

### 3.3 内容一致性问题（本日发现并修复）

- **EP06 与 EP07 开场撞车**：EP06 收尾曾用 OCR 3-64~3-70（认尸/葬父），而这正是切分表划给 EP07 的开场 8 镜。
  → 已把 EP06 镜 52-54 改为**空鞍战马 / 帅帐孤灯 / 晨光箭林**三个氛围镜（呼应 EP04 空鞍母题），并同步更新元数据 + 提示词 + 分镜表 + 重生成 grid6。**跨集切分时务必核对页码范围，避免重复叙事**。

### 3.4 流程性缺口

- **Flow 积分账本不存在**（`output/2026-10-11/flow_credit_ledger.json` 缺失）——**不是缺漏**，本次九宫格走 Nano Banana **0 积分**，脚本不写账本；走 Veo 视频路线时才产生账本（10-10 耗 20 积分）。

---

## 四、待办事项（To-Do）

### 4.1 立即待办
1. **人工验收 EP01/05/06/07 速览图**（重点看：EP06 grid5 李陵碑殉国、EP07 grid1 黄河认尸、EP01 grid1 雪城受印）——不满意的单组可单独重抽：
   ```
   python tools/yangjiajiang_flow_grids.py --ep 6 --grid 5 --wait 240
   python tools/yangjiajiang_flow_grids.py --ep 6 --slice 5
   ```
2. **清理旧图备份**：EP01、EP06 各遗留 1 个 `grids/*.prev_*.png`（重抽前自动备份，确认新版可用后可删）。
3. **更正资产清单口径**：EP02/03/04 的"历史产出"表述需细化（首帧在 `input/`、output 为视频产物）。

### 4.2 续产待办（EP08~EP24，共 17 集）

**EP08《汴京审潘》——第一季 · 归宋 终（续产计划已定，可直接开跑）**

| 项 | 值 |
|---|---|
| 源料 | 切分表 **35 镜 / 6 场**（`全片切分表812段` 第8集行）+ OCR 册3 页 89-106 |
| 目标 | 54 镜 / 6 组九宫格 / 214.0s / 竖屏 9:16 |
| 开场钩子 | "一面登闻鼓，静着"（承接 EP07 收尾的夜鼓架意象） |
| 分幕（6 幕 × 9 镜） | ①登闻鼓响·金殿质证（8-1）②边关夺印·帅权易主（8-2）③大理寺·礼单败露（8-3）④西台审潘·冢开酒囊（8-4）⑤天理昭彰·奸佞伏诛（8-5）⑥天波府·季终李陵碑（8-6） |

季终集**特殊注意事项**：
1. **季终镜头**（镜 33 附近）：李陵碑空镜、固定机位、**空十秒**，镜长需给足并留字幕位。
2. **首季字幕**："第一季 · 归宋 终"需在元数据标注，供后期母带烧录。
3. **"接枪"母题第一次**（六郎取下父亲银枪）—— 与第 23 集桂英挂帅呼应。
4. **酒囊回环**：第 6 集遗物在此集被重新捡起（跨集道具线）。
5. **不给血**：百姓打死潘刘 → 镜头留街上只看门一开一合；验尸只给酒囊与箭孔。
6. **构图纪律**：潘仁美全程矮半头，帅印易手后"矮"的性质由地位变为"被无视"。
7. **朱砂**：EP08 不启用（全片仅第2/6/23集）。

**逐集流水线（每次约 30 分钟，0 积分）**：
1. 取源料：切分表 xlsx `全片切分表812段` 第 N 集行 + OCR `season*.txt` 对应块
2. 写元数据 `tools/yangjiajiang_epNN_metadata.py`（54 镜 / 214.0s / 6 组）
3. 追加提示词 `tools/yangjiajiang_flow_grid_prompts.py` 的 `EP_GRID_PROMPTS[NN]`
4. 生成 + 切片：`python tools/yangjiajiang_flow_grids.py --ep NN --all --wait 200` → `--slice-all`

> **注意**：`tools/SCRIPTS_INVENTORY.md` 已按集登记 EP06/EP07 独立行（不再合并），新集数请同样单独登记。

### 4.3 出片阶段（资产齐备后）
1. 把 `frames/yang_epXX_shotNN.jpg` 拷入 `input/`（按 `yang_epXX_shotNN.jpg` 命名）
2. 复用 `tools/yangjiajiang_ep03_pipeline.py` 改集数参数（**54 镜 `--submit-only`，只提交不轮询**）
3. 母带总成复用 `tools/yangjiajiang_ep03_master_engine.py`（Edge-TTS 云健男声 + 720P + SRT）
4. 逐镜质检 `tools/comfy_shot_quality_auditor.py`

---

## 五、后续优化建议

1. **流水线一键化**：把"取源料→元数据→提示词→生成→切片"封装成 `tools/yangjiajiang_ep_builder.py --ep NN`，将单集耗时从多步手工降为一条命令。
2. **CDP 自愈**：在 `_flow_cdp.py` 加入"连接失败自动重启 Chrome"逻辑（当前仍需人工杀进程），并持久化登录 probe。
3. **生成后自动质检**：九宫格出图后自动检测是否含 1-9 编号/文字污染/横屏，不合格自动重抽（目前靠人工看速览图）。
4. **分镜脚本与元数据单源化**：目前 `分镜表 txt` 由元数据手工同步，易漏改（EP06 修订时就需三处同步）→ 建议改为从元数据自动导出 txt。
5. **跨集连续性校验器**：自动比对相邻两集的页码区间与剧情摘要，提前发现"重复叙事/断点"（本次 EP06/EP07 撞车即为例）。
6. **资产台账自动化**：`asset_manifest.md` 改为脚本生成（扫描磁盘 → 输出清单），避免手工维护失真。

---

## 六、关键路径速查

| 用途 | 路径 |
|---|---|
| 本次资产根目录 | `D:\ai_projects\ComfyUI\output\2026-10-11\yangjiajiang_ep0X\` |
| 资产清单 | `output\2026-10-11\yangjiajiang_asset_manifest.md` |
| 通用九宫格器 | `tools\yangjiajiang_flow_grids.py` |
| 原生 CDP 驱动 | `tools\_flow_cdp.py` |
| 提示词模块 | `tools\yangjiajiang_flow_grid_prompts.py` |
| 各集元数据 | `tools\yangjiajiang_ep01/05/06/07_metadata.py` |
| 脚本全量清单 | `tools\SCRIPTS_INVENTORY.md` |
| 新 Agent 接入指南 | `tools\AGENT_ONBOARDING.md` |
| 切分表源 | `todos\北宋杨家将\动画改编方案\杨家将_Flow片段切分表.xlsx` |
| 原书 OCR | `todos\北宋杨家将\.workbuddy\_tmp\ocr\season1.txt`（册1-3） |

---

## 七、执行纪律（承接既有约定）

1. **长任务只提交不轮询**：后台完成会自动通知，禁止 sleep+check 循环。
2. **单实例纪律**：16GB 卡上禁止双 ComfyUI 实例。
3. **输出按日期归档**：`output/<YYYY-MM-DD>/<项目名>/`。
4. **本机 API 绕代理**：访问 8188 用 `ProxyHandler({})`，否则 502。
5. **改脚本前先查清单**：`tools/SCRIPTS_INVENTORY.md`，别在废弃脚本上叠加。
6. **敏感信息不出域**：本机路径/token/账号不上传远程仓库。

---

*本文档由 2026-10-11 生产会话产出。配套资产已全部落盘并通过对账，EP08《汴京审潘》（第一季季终）续产计划已定，可直接开跑。*