# AIGC Local Asset Hub · 本地资产管理系统

专为 ComfyUI 与本地 AIGC 生产管线打造的高性能、轻量级、**零显存占用（Zero-VRAM）** 资产管理中枢。

---

## 🌟 核心特性

1. **零显存占用 (Zero-VRAM Architecture)**：
   - 系统服务端完全运行在 CPU 上，不常驻 PyTorch / CUDA，绝不与 ComfyUI 抢占显存（RTX 4060 Ti 16GB 友好）。
   - 复杂 AI 运算（SAM2 服装抠图、换装换脸生成）通过内置代理委托给运行中的 ComfyUI 8188 实例。
2. **纯 CPU 高性能向量检索**：
   - 基于 NumPy 矩阵运算在内存中瞬时计算 512 维 InsightFace 人脸特征的余弦相似度（两两比对与全库聚类 $<1\text{ms}$）。
3. **无损双向同步引擎 (Lossless Two-Way Sync)**：
   - 原位挂载并接管 `character_library/` 与 `garment_library/`，保留全部既有目录结构；
   - 读写数据通过 SQLite 高速缓存，同时实时自动回写 `index.json` 与 `INDEX.md`，保持既有 CLI 脚本 100% 兼容。
4. **现代化自适应暗黑 Web 界面 (Vue 3 SPA)**：
   - 随包预编译分发至 `dist/`，开箱即用，免装 Node.js；
   - 角色多视角画廊（`front`, `left45`, `right45`, `smile`）、身份余弦矩阵探查、色卡容差取色筛选、透明底/白底自由切换、一键复制标准路径。
5. **ComfyUI 联动与直投开关**：
   - 默认模式：一键复制标准绝对/相对路径，粘贴即用；
   - 扩展模式：可选开启“常用工作流一键直投”与“无头出片控制台”。

---

## 🚀 启动与使用

### 方式一：双击一键批处理（推荐）
在工程根目录双击运行：
```cmd
start_asset_manager.bat
```
脚本将自动启动后台服务并自动在默认浏览器中打开 `http://127.0.0.1:8090`。

### 方式二：命令行启动
使用虚拟环境 Python 运行：
```cmd
cmd /c D:\ai_projects\ComfyUI\venv\Scripts\python.exe tools\asset_manager\run.py --port 8090
```

* **Web UI 访问**：[http://127.0.0.1:8090](http://127.0.0.1:8090)
* **交互式 API 文档 (Swagger)**：[http://127.0.0.1:8090/docs](http://127.0.0.1:8090/docs)

---

## 📁 目录结构

```
tools/asset_manager/
├── backend/                  # FastAPI 后端源码
│   ├── app.py                # 主服务入口与静态目录挂载
│   ├── config.py             # 端口、ComfyUI 地址与目录路径配置
│   ├── database.py           # SQLite 连接引擎与 Session
│   ├── models.py             # SQLAlchemy ORM 与 Pydantic Schema
│   ├── vector_math.py        # 纯 CPU 向量相似度与色卡算法
│   ├── sync_engine.py        # 双向扫描与 JSON/Markdown 回写引擎
│   ├── comfy_client.py       # ComfyUI 8188 异步委托客户端
│   └── routers/              # RESTful API 路由模块
│       ├── characters.py     # 角色列表、检索与相似度搜索
│       ├── garments.py       # 服装列表、色卡拾取与分类过滤
│       ├── comfy.py          # ComfyUI 状态与工作流直投
│       └── system.py         # 系统聚合统计与重扫
│
├── dist/                     # 现代自适应暗黑前端单页应用
│   └── index.html            # Vue 3 + Tailwind 响应式页面
│
├── run.py                    # 独立启动脚本
├── test_stage1.py            # 全功能集成测试套件
└── README.md                 # 说明文档
```

---

## 🔌 API 核心端点总览

* `GET /api/system/stats`：全库资产聚合统计（角色数、服装数、分类统计、标签云）；
* `POST /api/system/sync`：触发本地目录全量重扫与数据库同步；
* `GET /api/characters`：角色列表与多维筛选（支持 `q` 关键字、`min_det_score` 置信度）；
* `POST /api/characters/similarity_search`：输入角色 ID 或 512 维特征向量，返回余弦相似度降序结果；
* `GET /api/garments`：服装列表与多维筛选（支持 `category`、`color_hex` 色彩过滤、`color_tolerance` 色彩容差）；
* `GET /api/garments/colors/palette`：提取全库所有服装的主色色卡聚合清单；
* `GET /api/comfy/status`：检测 ComfyUI 8188 连通性与队列状态。
