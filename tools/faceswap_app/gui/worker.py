"""后台工作线程：在 QThread 中运行换脸引擎，避免阻塞 UI"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core.engine import EngineConfig, FaceSwapEngine


class FaceSwapWorker(QThread):
    """换脸工作线程

    信号:
        progress(stage, current, total, message): 进度更新
        frame_preview(frame_path): 流式预览帧路径（已换脸后的输出帧）
        log(message): 日志行
        finished_all(results): 全部完成（results 为 EngineResult 列表）
        failed(error): 引擎异常
    """

    progress = Signal(str, int, int, str)
    frame_preview = Signal(str)
    log = Signal(str)
    finished_all = Signal(list)
    failed = Signal(str)

    def __init__(self, config: EngineConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._cancel_flag = False

    def cancel(self):
        """请求取消（线程会在下一个检查点退出）"""
        self._cancel_flag = True

    def _is_cancelled(self) -> bool:
        return self._cancel_flag

    def _on_progress(self, stage: str, current: int, total: int, msg: str):
        # "preview" 阶段不进入 progress 信号（避免污染进度条），单独发射预览信号
        if stage == "preview":
            self.frame_preview.emit(msg)
            return
        self.progress.emit(stage, current, total, msg)
        self.log.emit(f"[{stage}] {msg}")

    def run(self):
        try:
            engine = FaceSwapEngine(
                self.config,
                progress_cb=self._on_progress,
                cancel_check=self._is_cancelled,
            )

            # 判断是单文件还是目录批量
            video_path = Path(self.config.video_source)
            if video_path.is_file():
                results = [engine.process_single_video(str(video_path))]
            else:
                results = engine.process_batch()

            if self._cancel_flag:
                self.log.emit("已取消")
            self.finished_all.emit(results)
        except Exception as e:
            self.failed.emit(str(e))
