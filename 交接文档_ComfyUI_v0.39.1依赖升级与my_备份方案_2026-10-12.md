# 交接文档 — ComfyUI v0.39.1 维护：依赖升级评估与自定义目录 my_ 备份方案（2026-10-12）

> 受众：接手维护的同事
> 范围：本会话在已升级到 ComfyUI v0.39.1 的基础上，完成的两类维护事项——
> ① 启动告警的 companion package 是否需要升级；② 为防上游更新丢失自定义目录，建立 my_ 前缀备份方案并落地。
> 项目大图（动漫短剧 / WanAnimate / media_dl 等）见文末 §6 链接的前序交接文档。

---

## 0. 一句话背景

仓库已在 `v0.39.1` 分支（base = upstream tag `de0125d9a`），本地自定义功能已迁入。本会话做了两件维护性工作：
1. 评估 3 个启动告警的依赖包要不要升 —— **结论：建议升（低风险）**，命令已给出，尚未执行。
2. 建立 `my_` 前缀自定义目录备份方案 —— **已完成并跑通首次备份**。

---

## 1. 当前进度

### 1.1 v0.39.1 状态（前序会话收尾，已稳定）
- 分支 `v0.39.1` 已推送到 origin（HEAD `b775e0dce`）；本地功能已迁入（`tools/ workflows/ docs/ scripts/ custom_nodes_patches/ todos/ demo_chars/`）。
- 飞书密钥泄漏已封堵：`feishu_bridge.py` 的 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 改为 `os.environ.get(...)`，缺失时 `logger.warning`。
- ⚠️ 分支/标签同名碰撞：`v0.39.1` 既是 tag（`de0125d9a`）又是 branch（`b775e0dce`）。所有 git 操作须写 `refs/heads/v0.39.1` / `refs/tags/v0.39.1` 显式区分，裸 `git rev-parse v0.39.1` 会解析到 tag。

### 1.2 companion package 升级评估（已完成，待执行）
- **结论：需要升级**。风险极低，建议升级以消除启动告警并保证后端兼容。
- 证据：`requirements.txt` 已锁新版，而 anaconda3 venv（ComfyUI 实际运行的 python）装的是旧版。

  | 包 | 已装（anaconda3） | requirements 锁定 | 是否需升 |
  |---|---|---|---|
  | `comfyui-workflow-templates` | 0.11.27 | 0.11.77 | ✅ 是 |
  | `comfyui-embedded-docs` | 0.5.9 | 0.5.13 | ✅ 是 |
  | `comfy-kitchen` | 0.2.26（告警显示 0.2.33） | 0.2.37 | ✅ 是 |
  | `comfyui-frontend-package` | 1.47.11 | 1.53.10 | ⚠️ 也落后，但本次未告警 |

- 这 3 个（含前端）都是**非核心辅助包**（模板库 / 节点内嵌文档 / 计算内核库 / Web 前端），小版本跨步，破坏风险极低。不升也能跑（告警非致命），但会缺新文档/模板、漏掉内核 bug 修复。

### 1.3 自定义目录 my_ 前缀备份方案（已完成并落地）
- **位置**：仓库外同级目录 `D:\ai_projects\ComfyUI_custom_backup\`（git 看不见，对仓库内任何 git 操作免疫）。
- **工具**：`my_sync.py`（backup/restore 子命令，纯标准库）、`dirs.txt`（待保护目录清单）、`excludes.txt`（跳过构建产物/大权重）、`README.md`、`my_backup.bat` / `my_restore.bat`。
- **已执行首次备份**：1711 文件 / 513MB / 74s。

  | 备份目录 | 文件数 | 大小 |
  |---|---|---|
  | my_tools | 1169 | 379M |
  | my_workflows | 266 | 5.4M |
  | my_docs | 27 | 364K |
  | my_scripts | 7 | 100K |
  | my_custom_nodes_patches | 9 | 80K |
  | my_todos | 230 | 134M |
  | my_demo_chars | 3 | 7.0K |

  `tools/models`（19G junction）已正确排除。
- **restore 已验证安全**：dry-run 显示仅补「缺失/较旧/不同」的文件、绝不删目标（1711 个全部跳过 = 仓库与备份一致）。

---

## 2. 已知问题 / 坑

1. **飞书 App Secret 曾硬编码明文入库**（虽未真正上推，远程从未含密钥）。**务必去飞书后台轮换 App Secret**，旧密钥视为已泄露。
2. **comfy-kitchen 版本号对不上**：告警写已装 `0.2.33`，pip 实测 `0.2.26`。可能是更早一次启动快照；无论哪个都低于锁定的 `0.2.37`，升级结论不变。
3. **摘要笔误已纠正**：早期把 `comfyui-frontend-package` 锁版误记为 `1.55.16`；实际 `requirements.txt` 是 `1.53.10`（已装 `1.47.11`，也落后）。
4. **ComfyUI 升级会重置 `tools/`**：前序 22:06 那次 `tools/*.py` 全部消失，靠备份 commit `4d7c00747` 的 `git checkout 4d7c00747 -- tools/...` 恢复。写新工具后要及时提交或记住备份点。
5. **仓库内 my_ 前缀未跟踪目录仍会被 `git clean -fd` 删** → 所以备份刻意放在仓库外。
6. **excludes 必须匹配路径任意一级目录名**：否则 `tools/faceswap_app/dist/`（PyInstaller torch 包 ~18GB）会被整盘拷贝。已修复——备份体积从 15.2GB 降到 0.54GB。
7. 分支/标签同名碰撞（见 §1.1）。

---

## 3. 待办（Todos）

- [ ] **升级 3 个 companion package**（命令见 §5），升级后重启 ComfyUI 确认无告警。
- [ ] **去飞书后台轮换 App Secret**（视为已泄露）。
- [ ] 可选：把约 108 个未跟踪临时文件（诊断 dump、build 目录、`ideogram4_*`、`tools/tiktok-downloader/` 等）加进 `.gitignore`。
- [ ] 把 `D:\ai_projects\ComfyUI_custom_backup\` 再拷一份到云盘/移动硬盘做双保险。

---

## 4. 后续优化

- 把 my_ 备份纳入固定流程：**下次上游更新【前】跑 `backup`，更新【后】跑 `restore`**。
- 若想完全对齐 `requirements.txt`，可一次性 `pip install -r requirements.txt`（会把 frontend 也升到 1.53.10）。
- 考虑把 `my_sync` 工具本身也版本化或云同步，避免工具丢失。
- 升级后若出现前端异常，回滚前端包：`pip install comfyui-frontend-package==1.47.11`。

---

## 5. 命令速查

```powershell
# —— 升级 3 个告警包（anaconda3 = ComfyUI 实际运行用的 python）——
C:/Users/kenzhao/anaconda3/python.exe -m pip install comfyui-workflow-templates==0.11.77 comfyui-embedded-docs==0.5.13 comfy-kitchen==0.2.37

# —— 或一次性对齐 requirements.txt（含 frontend 升到 1.53.10）——
C:/Users/kenzhao/anaconda3/python.exe -m pip install -r D:/ai_projects/ComfyUI/requirements.txt

# —— 自定义目录备份 / 还原（建议先 dry-run 预览）——
python D:\ai_projects\ComfyUI_custom_backup\my_sync.py backup --dry-run
python D:\ai_projects\ComfyUI_custom_backup\my_sync.py backup
python D:\ai_projects\ComfyUI_custom_backup\my_sync.py restore --dry-run
python D:\ai_projects\ComfyUI_custom_backup\my_sync.py restore
```

> 还原语义是「合并」：只补回缺失/较旧/不同的文件，**绝不删除**目标里备份没有的文件，因此上游更新新加的文件会被保留。增删要保护的目录改 `dirs.txt` 即可。

---

## 6. 关键文件 / 位置

| 内容 | 路径 |
|---|---|
| 备份工具 + 备份数据 | `D:\ai_projects\ComfyUI_custom_backup\` |
| 依赖锁定 | `D:\ai_projects\ComfyUI\requirements.txt` |
| 飞书桥（已改读环境变量） | `D:\ai_projects\ComfyUI\feishu_bridge.py` |
| 备份方案说明 | `D:\ai_projects\ComfyUI_custom_backup\README.md` |
| 前序交接（项目大图） | 仓库根 `交接文档_动漫短剧本地落地_2026-10-11.md`、`交接_WanAnimate_831959换装视频_B方案全量批处理_2026-10-11.md`、`2026-10-10_多模型出图质量评测与Z-Image皮肤LoRA补偿_交接文档.md` |

---

## 7. 参考资料

- ComfyUI 更新公告（含 companion package 说明）：https://docs.comfy.org/installation/update_comfyui#common-update-issues
- 备份方案 README：`D:\ai_projects\ComfyUI_custom_backup\README.md`
