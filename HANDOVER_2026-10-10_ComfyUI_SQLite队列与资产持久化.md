# ComfyUI 队列与资产持久化方案交付文档

> **主题**: ComfyUI 重启/崩溃数据防丢改造（方案 1 UI 资产浏览插件 + 方案 2 外部 SQLite 任务队列与断点续跑）  
> **日期时间**: 2026-10-10 09:59:00 (Asia/Shanghai)  
> **执行环境**: Windows 11 / NVIDIA RTX 4060 Ti 16GB / ComfyUI 0.30.0 / Python 3.11  
> **文档位置**: `HANDOVER_2026-10-10_ComfyUI_SQLite队列与资产持久化.md`

---

## 一、 背景与痛点根因

在原生 ComfyUI 中：
1. **任务与历史纯内存存放**: `execution.PromptQueue` 将任务堆（`self.queue`）与执行结果（`self.history`）放在 Python 进程内存中。一旦系统重启、关机或遭遇显存溢出（OOM）崩溃，所有排队任务与历史记录立即归零。
2. **前端资产展示失联**: 磁盘 `output/` 上的实体文件虽然存在，但前端侧边栏（Queue / History 面板）强依赖 `/history` API，重启后面板变空，无法追溯工作流参数与文件生成关系。
3. **批量脚本缺乏容灾机制**: 过去的批处理脚本直接循环调用 `/prompt` 并挂起，若进程中断，无法知道哪些分镜已成功出片、哪些尚未执行，缺乏断点续跑能力。

---

## 二、 方案设计与选型结论

经架构评估，采取 **“UI 插件索引 + 外部 SQLite 状态调度”** 双层防护架构：

```mermaid
flowchart TD
    subgraph UI层_方案1
        Frontend[ComfyUI Web 前端] --> Browser[comfyui-browser 插件]
        Browser --> DiskScan[扫描 output/ 磁盘文件 & 提取元数据]
    end

    subgraph 引擎层_方案2
        BatchScript[批量生产脚本] --> PreEnqueue[Write-Ahead 任务先落库]
        PreEnqueue --> SQLite[(user/task_queue.db<br>WAL模式)]
        SQLite --> Dispatcher[调度器 resume_queue]
        Dispatcher -- 提交任务 / 监听进度 --> ComfyWorker[ComfyUI 8188 实例]
        ComfyWorker --> OutputDir[output/YYYY-MM-DD/]
        OutputDir --> AssetRecord[登记至 assets 资产表]
    end
```

### 数据库选型对比
* **SQLite（已落地选型）**: 采用 WAL 模式（Write-Ahead Logging），单机零运维、无常驻服务进程损耗、抗异常断电崩溃能力极强，完全契合单机工作站。
* **PostgreSQL**: 适合未来多台 GPU Worker 分布式集群或 Web 多租户平台，当前单机阶段无需引入额外运维复杂度。

---

## 三、 本次会话完成事项与交付物清单

### 1. 方案 1：开箱即用媒体资产画廊已就绪
* **安装路径**: [`custom_nodes/comfyui-browser/`](file:///d:/ai_projects/ComfyUI/custom_nodes/comfyui-browser)
* **功能特性**:
  * 彻底解决重启后前端无法查看历史产物的问题。
  * 自动检索并索引 `output/` 及子目录下的所有图片、视频与工作流。
  * 启动 ComfyUI 后在前端顶部点击 **Browser** 即可直接按日期、类型浏览检索。

### 2. 方案 2：外部 SQLite 任务状态管理与断点续跑系统
* **核心模块**: [`tools/comfy_sqlite_queue.py`](file:///d:/ai_projects/ComfyUI/tools/comfy_sqlite_queue.py)
* **数据库文件**: [`user/task_queue.db`](file:///d:/ai_projects/ComfyUI/user/task_queue.db)
* **数据表结构**:
  * `tasks`: 包含 `task_id`, `batch_name`, `prompt_id`, `status (pending/running/completed/failed)`, `prompt_payload`, `extra_meta`, `retry_count`, `error_msg` 等。
  * `assets`: 包含 `task_id`, `prompt_id`, `batch_name`, `asset_type (image/video/audio)`, `subfolder`, `filename`, `abs_path`, `meta_json` 等。

### 3. 全套自动化测试套件（通过率 100%）
* **测试文件**: [`tools/test_sqlite_queue_suite.py`](file:///d:/ai_projects/ComfyUI/tools/test_sqlite_queue_suite.py)
* **验证用例**:
  1. `test_01_enqueue_and_schema`: 验证任务先行落库、状态为 `pending`、元数据完整保存。`[PASS]`
  2. `test_02_crash_simulation_and_breakpoint_resume`: 模拟执行中途突然断电/崩溃遗留 `running` 状态，验证 `resume` 自动检测并成功断点续跑完成。`[PASS]`
  3. `test_03_failure_isolation_and_retry`: 模拟节点执行报错，验证异常任务被严格隔离并记录原因，不阻塞后续任务；测试 `retry_failed` 重置。`[PASS]`
  4. `test_04_asset_tracking_and_classification`: 验证图片与视频资产自动归类识别与 `output/YYYY-MM-DD/` 路径解析。`[PASS]`

### 4. 生产接入示例脚本
* **演示文件**: [`tools/example_batch_submit.py`](file:///d:/ai_projects/ComfyUI/tools/example_batch_submit.py)
* 演示多分镜批量落库、状态查询与恢复。

---

## 四、 运维命令与接入指南

### 1. 命令行运维速查

```bash
# 查看队列状态统计（待处理/运行中/已完成/失败）
cmd /c python tools/comfy_sqlite_queue.py status

# 断点续跑：机器重启开机后执行，自动恢复所有未完成的任务
cmd /c python tools/comfy_sqlite_queue.py resume

# 查看已入库的产物资产
cmd /c python tools/comfy_sqlite_queue.py list-assets --limit 20

# 一键重置因显存溢出或报错失败的任务以便重跑
cmd /c python tools/comfy_sqlite_queue.py retry-failed

# 清理指定批次或指定状态的任务记录
cmd /c python tools/comfy_sqlite_queue.py purge --batch demo_batch
```

### 2. 业务脚本极简接入（3 行代码实现防丢保障）

在任何批量出片或分镜生成脚本中引入：

```python
from tools.comfy_sqlite_queue import enqueue_task, resume_queue

# 1. 组装好的 API Prompt 先行落库
task_id = enqueue_task(
    prompt_dict=api_prompt,
    batch_name="ep01_shots",
    extra_meta={"shot_id": "shot_01", "seed": 42}
)

# 2. 批量入库完成后启动调度执行（支持随时中断并断点恢复）
resume_queue(batch_name="ep01_shots")
```

---

## 五、 下个会话启动建议与待办事项

1. **会话切换原则**: 本阶段设计、开发、落地与全场景测试已全部闭环，**建议开启新会话**以保持上下文清爽并节省 Token。
2. **待办 1 - Web 界面验证**:
   * 启动 ComfyUI (`cmd /c start_comfyui.bat`)，访问 Web 页面检查右上角 `Browser` 按钮，确认历史画廊加载正常。
3. **待办 2 - 存量脚本接入**:
   * 评估将重点生产流水线脚本（如 `yangjiajiang_*.py` 或批量换脸 `batch_faceswap.py`）接入 `enqueue_task`，彻底告别批量跑片中途崩溃丢进度问题。
