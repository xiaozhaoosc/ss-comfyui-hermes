"""换脸客户端主窗口"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.engine import EngineConfig
from core.license import LicenseManager
from core.media_utils import imread_unicode, list_audios, list_images, list_videos
from gui.worker import FaceSwapWorker


class FilePicker(QWidget):
    """文件/目录选择器：输入框 + 浏览按钮（可选文件或目录模式）"""

    def __init__(self, mode: str = "file", filter: str = "", placeholder: str = "", parent=None):
        super().__init__(parent)
        self.mode = mode  # "file" | "dir"
        self.filter = filter
        # 记录上一次浏览目录，作为下次对话框初始路径
        # Why: 避免每次浏览都从默认位置开始，提升使用体验
        self._last_dir = str(Path.home())
        self.edit = QLineEdit()
        if placeholder:
            self.edit.setPlaceholderText(placeholder)
        self.btn = QPushButton("浏览…")
        self.btn.clicked.connect(self._browse)
        self.paste_btn = QPushButton("📋 粘贴")
        self.paste_btn.clicked.connect(self._paste_from_clipboard)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.btn)
        lay.addWidget(self.paste_btn)

    def _initial_dir(self) -> str:
        # 优先用当前输入框中的路径所在目录，否则用上次记录目录
        # Why: 若用户已粘贴或选过路径，再次浏览时应从该位置附近开始
        cur = self.edit.text().strip()
        if cur:
            p = Path(cur)
            if p.is_dir():
                return str(p)
            if p.parent.exists():
                return str(p.parent)
        return self._last_dir

    def _browse(self):
        # parent 改用 window()：FilePicker 自身是子 widget，作为 QFileDialog parent
        # 可能导致某些 Qt 平台插件下原生对话框无法正常弹出。
        parent = self.window()
        options = QFileDialog.Options(QFileDialog.DontUseNativeDialog)
        start_dir = self._initial_dir()

        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(
                parent, "选择目录", start_dir, options)
        else:
            path, _ = QFileDialog.getOpenFileName(
                parent, "选择文件", start_dir, self.filter, options)
        if path:
            self.edit.setText(path)
            # 记录所选路径所在目录，作为下次浏览的初始位置
            p = Path(path)
            self._last_dir = str(p.parent if p.is_file() else p)

    def _paste_from_clipboard(self):
        # 从剪贴板粘贴路径，便于直接复用资源管理器中复制的路径
        text = QApplication.clipboard().text().strip()
        if text:
            self.edit.setText(text)

    def text(self) -> str:
        return self.edit.text().strip()


class MainWindow(QMainWindow):
    """换脸客户端主窗口"""

    def __init__(self):
        super().__init__()
        self.resize(1100, 760)

        # license 管理器先初始化，标题栏更新与试用拦截都依赖它
        # Why: 所有 license 操作 try-except，异常退化为未激活而非崩溃
        try:
            self.license_mgr = LicenseManager()
        except Exception:
            self.license_mgr = None

        self.worker: FaceSwapWorker | None = None
        self._init_ui()
        self._apply_variant()  # CPU 版禁用 GPU（须在 _detect_gpu 前生效）
        self._detect_gpu()
        self._update_title()
        self._check_license()  # 篡改/试用耗尽检测弹窗

        # 默认输出目录
        default_out = str(Path.cwd() / "output" / "faceswap_app")
        self.output_picker.edit.setText(default_out)

    # ---------- UI 构建 ----------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # 左侧：参数区（可滚动）
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(560)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)

        # 人脸源
        face_box = QGroupBox("① 人脸源")
        face_layout = QVBoxLayout(face_box)
        self.face_picker = FilePicker(mode="file",
                                      filter="图片 (*.png *.jpg *.jpeg *.bmp *.webp)",
                                      placeholder="选择人脸源图片")
        face_layout.addWidget(self.face_picker)
        self.face_preview = QLabel("（选择图片后显示预览）")
        self.face_preview.setFixedSize(160, 160)
        self.face_preview.setAlignment(Qt.AlignCenter)
        self.face_preview.setStyleSheet("border:1px dashed #aaa; color:#888;")
        face_layout.addWidget(self.face_preview)
        self.face_picker.edit.textChanged.connect(self._update_face_preview)
        left_layout.addWidget(face_box)

        # 视频源
        video_box = QGroupBox("② 视频源（文件或目录，目录则批量）")
        video_layout = QVBoxLayout(video_box)
        self.video_picker = FilePicker(mode="file",
                                       filter="视频 (*.mp4 *.avi *.mov *.mkv *.flv *.webm)",
                                       placeholder="选择视频文件")
        video_layout.addWidget(self.video_picker)
        # 双按钮互斥：点击直接弹出对应对话框，而非切换模式
        video_mode_row = QHBoxLayout()
        self.video_file_btn = QPushButton("选文件")
        self.video_file_btn.setCheckable(True)
        self.video_file_btn.setChecked(True)
        self.video_file_btn.clicked.connect(self._pick_video_file)
        self.video_dir_btn = QPushButton("选目录")
        self.video_dir_btn.setCheckable(True)
        self.video_dir_btn.clicked.connect(self._pick_video_dir)
        self.video_mode_group = QButtonGroup(self)
        self.video_mode_group.setExclusive(True)
        self.video_mode_group.addButton(self.video_file_btn)
        self.video_mode_group.addButton(self.video_dir_btn)
        video_mode_row.addWidget(self.video_file_btn)
        video_mode_row.addWidget(self.video_dir_btn)
        video_mode_row.addStretch(1)
        video_layout.addLayout(video_mode_row)
        self.video_info = QLabel("（选择后显示视频信息）")
        self.video_info.setStyleSheet("color:#666;")
        video_layout.addWidget(self.video_info)
        self.video_picker.edit.textChanged.connect(self._update_video_info)
        left_layout.addWidget(video_box)

        # BGM
        bgm_box = QGroupBox("③ BGM（可选）")
        bgm_layout = QVBoxLayout(bgm_box)
        self.bgm_picker = FilePicker(mode="file",
                                     filter="音频 (*.mp3 *.wav *.aac *.m4a *.flac *.ogg)",
                                     placeholder="选择 BGM 文件")
        bgm_layout.addWidget(self.bgm_picker)
        # 双按钮互斥：点击直接弹出对应对话框，与视频源交互保持一致
        bgm_row = QHBoxLayout()
        self.bgm_file_btn = QPushButton("选文件")
        self.bgm_file_btn.setCheckable(True)
        self.bgm_file_btn.setChecked(True)
        self.bgm_file_btn.clicked.connect(self._pick_bgm_file)
        self.bgm_dir_btn = QPushButton("选目录")
        self.bgm_dir_btn.setCheckable(True)
        self.bgm_dir_btn.clicked.connect(self._pick_bgm_dir)
        self.bgm_mode_group = QButtonGroup(self)
        self.bgm_mode_group.setExclusive(True)
        self.bgm_mode_group.addButton(self.bgm_file_btn)
        self.bgm_mode_group.addButton(self.bgm_dir_btn)
        bgm_row.addWidget(self.bgm_file_btn)
        bgm_row.addWidget(self.bgm_dir_btn)
        bgm_row.addStretch(1)
        self.bgm_random = QCheckBox("目录模式下随机选择")
        bgm_row.addWidget(self.bgm_random)
        bgm_layout.addLayout(bgm_row)

        # 音量控制
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("原音音量:"))
        self.orig_vol = QSlider(Qt.Horizontal)
        self.orig_vol.setRange(0, 100)
        self.orig_vol.setValue(100)
        self.orig_vol_label = QLabel("100%")
        self.orig_vol.valueChanged.connect(
            lambda v: self.orig_vol_label.setText(f"{v}%"))
        vol_row.addWidget(self.orig_vol, 1)
        vol_row.addWidget(self.orig_vol_label)
        bgm_layout.addLayout(vol_row)

        vol_row2 = QHBoxLayout()
        vol_row2.addWidget(QLabel("BGM音量:"))
        self.bgm_vol = QSlider(Qt.Horizontal)
        self.bgm_vol.setRange(0, 100)
        self.bgm_vol.setValue(50)
        self.bgm_vol_label = QLabel("50%")
        self.bgm_vol.valueChanged.connect(
            lambda v: self.bgm_vol_label.setText(f"{v}%"))
        vol_row2.addWidget(self.bgm_vol, 1)
        vol_row2.addWidget(self.bgm_vol_label)
        bgm_layout.addLayout(vol_row2)

        self.keep_original = QCheckBox("保留原音（与 BGM 混合，取消则仅保留 BGM）")
        self.keep_original.setChecked(True)
        bgm_layout.addWidget(self.keep_original)
        left_layout.addWidget(bgm_box)

        # 引擎选择
        engine_box = QGroupBox("④ 引擎")
        engine_layout = QVBoxLayout(engine_box)
        self.engine_group = QButtonGroup(self)
        self.rb_gpu = QRadioButton("GPU (CUDA，需 onnxruntime-gpu)")
        self.rb_cpu = QRadioButton("CPU (兼容性好，速度慢)")
        self.rb_gpu.setChecked(True)
        self.engine_group.addButton(self.rb_gpu)
        self.engine_group.addButton(self.rb_cpu)
        engine_layout.addWidget(self.rb_gpu)
        engine_layout.addWidget(self.rb_cpu)
        self.gpu_status = QLabel("检测中…")
        self.gpu_status.setStyleSheet("color:#666;")
        engine_layout.addWidget(self.gpu_status)

        # 高级参数
        adv_row = QHBoxLayout()
        adv_row.addWidget(QLabel("最大片段(秒):"))
        self.seg_spin = QSpinBox()
        self.seg_spin.setRange(5, 120)
        self.seg_spin.setValue(15)
        adv_row.addWidget(self.seg_spin)
        adv_row.addWidget(QLabel("帧率:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(25)
        adv_row.addWidget(self.fps_spin)
        self.gfpgan_chk = QCheckBox("启用 GFPGAN 修复")
        self.gfpgan_chk.setChecked(True)
        adv_row.addWidget(self.gfpgan_chk)
        engine_layout.addLayout(adv_row)
        left_layout.addWidget(engine_box)

        # 输出目录
        out_box = QGroupBox("⑤ 输出目录")
        out_layout = QVBoxLayout(out_box)
        self.output_picker = FilePicker(mode="dir", placeholder="选择输出目录")
        out_layout.addWidget(self.output_picker)
        left_layout.addWidget(out_box)

        left_layout.addStretch(1)
        left_scroll.setWidget(left_widget)
        root.addWidget(left_scroll, 0)

        # 右侧：进度 + 视频预览 + 日志 + 按钮
        right = QVBoxLayout()
        right.setSpacing(8)

        # 进度
        prog_box = QGroupBox("进度")
        prog_layout = QVBoxLayout(prog_box)
        self.stage_label = QLabel("就绪")
        self.stage_label.setStyleSheet("font-weight:bold; font-size:14px;")
        prog_layout.addWidget(self.stage_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        prog_layout.addWidget(self.progress_bar)
        self.task_label = QLabel("")
        self.task_label.setStyleSheet("color:#666;")
        prog_layout.addWidget(self.task_label)
        right.addWidget(prog_box)

        # 视频预览（流式显示已换脸帧）
        # Why: 用户要求在进度和日志之间插入预览区，处理时边生成边看
        preview_box = QGroupBox("视频预览")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_label = QLabel("（开始任务后在此显示预览帧）")
        self.preview_label.setMinimumHeight(280)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet(
            "border:1px dashed #aaa; color:#888; background:#000;")
        preview_layout.addWidget(self.preview_label)
        right.addWidget(preview_box, 1)

        # 日志（缩小为固定高度，把空间让给预览区）
        log_box = QGroupBox("日志")
        log_layout = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        self.log_view.setFont(font)
        log_layout.addWidget(self.log_view)
        right.addWidget(log_box, 0)

        # 操作按钮
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ 开始")
        self.btn_start.setStyleSheet("font-size:16px; padding:8px 24px; background:#4CAF50; color:white;")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setStyleSheet("font-size:16px; padding:8px 24px; background:#f44336; color:white;")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        self.btn_activate = QPushButton("🔑 激活")
        self.btn_activate.setStyleSheet("font-size:14px; padding:8px 16px;")
        self.btn_activate.clicked.connect(self._on_activate)
        self.btn_open_out = QPushButton("📂 打开输出目录")
        self.btn_open_out.clicked.connect(self._open_output)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_activate)
        btn_row.addWidget(self.btn_open_out)
        right.addLayout(btn_row)

        root.addLayout(right, 1)

    # ---------- 辅助逻辑 ----------

    def _detect_gpu(self):
        """启动时检测 onnxruntime GPU 支持情况"""
        try:
            import onnxruntime
            providers = onnxruntime.get_available_providers()
            has_cuda = 'CUDAExecutionProvider' in providers
            self.gpu_status.setText(
                f"onnxruntime {onnxruntime.__version__} | "
                f"{'✅ CUDA 可用' if has_cuda else '⚠️ CUDA 不可用'} | providers: {', '.join(providers)}"
            )
            if not has_cuda:
                self.rb_cpu.setChecked(True)
                self.rb_gpu.setEnabled(False)
                self.gpu_status.setStyleSheet("color:#c00;")
        except ImportError:
            self.gpu_status.setText("未安装 onnxruntime")
            self.rb_cpu.setChecked(True)
            self.rb_gpu.setEnabled(False)
            self.gpu_status.setStyleSheet("color:#c00;")

    # ---------- license 相关 ----------

    def _apply_variant(self):
        """CPU 版禁用 GPU 选项（通过 FACESWAP_VARIANT 环境变量或 exe 文件名推断）"""
        variant = os.environ.get("FACESWAP_VARIANT", "gpu").lower()
        if variant == "cpu":
            self.rb_gpu.setEnabled(False)
            self.rb_cpu.setChecked(True)
            self.gpu_status.setText("CPU 版本不支持 GPU 加速")
            self.gpu_status.setStyleSheet("color:#c00;")

    def _update_title(self):
        """根据 license 状态更新标题栏"""
        if self.license_mgr is None:
            self.setWindowTitle("视频换脸客户端")
            return
        if self.license_mgr.is_activated():
            self.setWindowTitle("视频换脸客户端 - 已授权")
        else:
            remaining = self.license_mgr.get_remaining_trials()
            self.setWindowTitle(f"视频换脸客户端 - 体验版（剩余 {remaining}/3 次）")

    def _check_license(self):
        """启动时检测篡改与试用耗尽，弹窗提示"""
        if self.license_mgr is None:
            return
        try:
            # 篡改锁定：弹窗但允许打开（让用户看到购买信息）
            if self.license_mgr.is_tampered():
                QMessageBox.warning(
                    self, "授权异常",
                    "检测到授权文件被篡改，程序已锁定，请购买正版后激活。"
                )
                return

            # 未激活且试用耗尽：弹窗显示机器码 + 引导激活
            if (not self.license_mgr.is_activated()
                    and self.license_mgr.get_remaining_trials() <= 0):
                self._prompt_activate(
                    "试用次数已用完",
                    "您的 3 次免费体验已用完，请输入授权码激活后继续使用：",
                )
        except Exception:
            # license 检查异常不阻止启动
            pass

    def _prompt_activate(self, title: str, message: str) -> bool:
        """弹出激活对话框，返回是否激活成功"""
        dlg = ActivationDialog(self.license_mgr, title, message, self)
        activated = dlg.exec() == QDialog.Accepted
        if activated:
            self._update_title()
            self._log("✅ 授权激活成功")
        return activated

    def _on_activate(self):
        """点击「激活」按钮"""
        if self.license_mgr is None:
            QMessageBox.critical(self, "错误", "授权模块不可用")
            return
        if self.license_mgr.is_activated():
            QMessageBox.information(self, "已授权", "当前已激活正版授权，无需重复激活。")
            return
        self._prompt_activate("激活授权", "请输入您获得的授权码以激活正版：")

    def _update_face_preview(self, path: str):
        if not path or not os.path.exists(path):
            self.face_preview.clear()
            self.face_preview.setText("（选择图片后显示预览）")
            return
        img = imread_unicode(path)
        if img is None:
            return
        from core.media_utils import imwrite_unicode
        # 转为 QPixmap 显示（中文路径需先写入临时文件）
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "_face_preview.png")
        imwrite_unicode(tmp, img)
        pix = QPixmap(tmp)
        if not pix.isNull():
            self.face_preview.setPixmap(pix.scaled(
                160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _update_video_info(self, path: str):
        if not path:
            self.video_info.setText("")
            return
        if os.path.isdir(path):
            videos = list_videos(path)
            self.video_info.setText(f"目录模式: {len(videos)} 个视频")
            return
        if not os.path.isfile(path):
            self.video_info.setText("")
            return
        from core.media_utils import get_video_duration, get_video_fps, get_video_resolution
        try:
            dur = get_video_duration(path)
            fps = get_video_fps(path)
            w, h = get_video_resolution(path)
            self.video_info.setText(f"{dur:.1f}s | {fps:.1f}fps | {w}x{h}")
        except Exception as e:
            self.video_info.setText(f"读取失败: {e}")

    def _pick_video_file(self):
        # 点击"选文件"：同步 FilePicker 模式并直接弹出文件对话框
        self.video_picker.mode = "file"
        self.video_picker._browse()
        self._update_video_info(self.video_picker.text())

    def _pick_video_dir(self):
        # 点击"选目录"：同步 FilePicker 模式并直接弹出目录对话框
        self.video_picker.mode = "dir"
        self.video_picker._browse()
        self._update_video_info(self.video_picker.text())

    def _pick_bgm_file(self):
        # 点击"选文件"：同步 FilePicker 模式并直接弹出音频文件对话框
        self.bgm_picker.mode = "file"
        self.bgm_picker._browse()
        self.bgm_random.setText("目录模式下随机选择")

    def _pick_bgm_dir(self):
        # 点击"选目录"：同步 FilePicker 模式并直接弹出目录对话框
        self.bgm_picker.mode = "dir"
        self.bgm_picker._browse()
        path = self.bgm_picker.text()
        if path and os.path.isdir(path):
            audios = list_audios(path)
            self.bgm_random.setText(f"目录模式下随机选择（共 {len(audios)} 个）")

    def _open_output(self):
        out = self.output_picker.text() or "."
        os.makedirs(out, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(out)
        elif sys.platform == "darwin":
            os.system(f'open "{out}"')
        else:
            os.system(f'xdg-open "{out}"')

    def _log(self, msg: str):
        self.log_view.appendPlainText(msg)

    # ---------- 启动 / 停止 ----------

    def _validate(self) -> str | None:
        """校验输入，返回错误信息或 None"""
        face = self.face_picker.text()
        if not face or not os.path.exists(face):
            return "请选择有效的人脸源图片"
        video = self.video_picker.text()
        if not video or not os.path.exists(video):
            return "请选择有效的视频源（文件或目录）"
        out = self.output_picker.text()
        if not out:
            return "请选择输出目录"
        bgm = self.bgm_picker.text()
        if bgm and not os.path.exists(bgm):
            return "BGM 路径不存在"
        return None

    def _on_start(self):
        # 试用拦截：未激活且次数耗尽则阻止启动并引导激活
        if self.license_mgr is not None:
            try:
                if (not self.license_mgr.is_activated()
                        and not self.license_mgr.is_tampered()
                        and self.license_mgr.get_remaining_trials() <= 0):
                    self._prompt_activate(
                        "试用次数已用完",
                        "您的 3 次免费体验已用完，请输入授权码激活后继续使用：",
                    )
                    return
            except Exception:
                pass

        err = self._validate()
        if err:
            QMessageBox.warning(self, "输入错误", err)
            return

        config = EngineConfig(
            face_source=self.face_picker.text(),
            video_source=self.video_picker.text(),
            output_dir=self.output_picker.text(),
            bgm_source=self.bgm_picker.text() or None,
            bgm_random=self.bgm_random.isChecked(),
            keep_original_audio=self.keep_original.isChecked(),
            bgm_volume=self.bgm_vol.value() / 100.0,
            original_volume=self.orig_vol.value() / 100.0,
            use_gpu=self.rb_gpu.isChecked(),
            max_segment_sec=float(self.seg_spin.value()),
            fps=self.fps_spin.value(),
            enable_gfpgan=self.gfpgan_chk.isChecked(),
        )

        self.log_view.clear()
        self._log(f"=== 开始任务 ===")
        self._log(f"人脸源: {config.face_source}")
        self._log(f"视频源: {config.video_source}")
        self._log(f"BGM: {config.bgm_source or '无'}")
        self._log(f"引擎: {'GPU' if config.use_gpu else 'CPU'}")
        self._log("")

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        # 重置预览区
        self.preview_label.clear()
        self.preview_label.setText("等待帧生成…")
        self.preview_label.setStyleSheet(
            "border:1px dashed #aaa; color:#888; background:#000;")

        self.worker = FaceSwapWorker(config)
        self.worker.progress.connect(self._on_progress)
        self.worker.frame_preview.connect(self._on_frame_preview)
        self.worker.log.connect(self._log)
        self.worker.finished_all.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_stop(self):
        if self.worker and self.worker.isRunning():
            self._log("⚠️ 正在停止（等待当前片段完成）…")
            self.worker.cancel()
            self.btn_stop.setEnabled(False)

    def _on_progress(self, stage: str, current: int, total: int, msg: str):
        # preview 阶段已由 worker 路由到 frame_preview，此处仅防御性跳过
        if stage == "preview":
            return
        self.stage_label.setText(f"[{stage}] {msg}")
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setValue(pct)
            self.task_label.setText(f"{current} / {total}  ({pct}%)")

    def _on_frame_preview(self, frame_path: str):
        # 流式预览：读取已换脸的输出帧并显示
        # Why: 中文路径下 QPixmap.load 直接传字符串会失败，需先 imread 再写临时文件
        if not frame_path or not os.path.exists(frame_path):
            return
        img = imread_unicode(frame_path)
        if img is None:
            return
        import tempfile
        from core.media_utils import imwrite_unicode
        tmp = os.path.join(tempfile.gettempdir(), "_faceswap_preview.png")
        imwrite_unicode(tmp, img)
        pix = QPixmap(tmp)
        if pix.isNull():
            return
        # 等比缩放到预览区可用尺寸
        size = self.preview_label.size()
        if size.width() < 2 or size.height() < 2:
            size = self.preview_label.minimumSize()
        scaled = pix.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)
        self.preview_label.setText("")

    def _on_finished(self, results: list):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        ok = sum(1 for r in results if r.success)
        fail = len(results) - ok
        self._log(f"\n=== 全部完成: 成功 {ok}, 失败 {fail} ===")
        for r in results:
            if r.success:
                self._log(f"  ✅ {r.output_path} ({r.frames_processed} 帧, {r.elapsed_sec:.0f}s)")
            else:
                self._log(f"  ❌ {r.error}")

        # 完成换脸任务后计数：对每个成功的 EngineResult 累加用量
        if self.license_mgr is not None and ok > 0:
            try:
                for _ in range(ok):
                    self.license_mgr.increment_usage()
                self._update_title()
            except Exception:
                pass

        if fail == 0:
            self.progress_bar.setValue(100)
            self.stage_label.setText("完成")
            # 预览区显示完成提示
            self.preview_label.clear()
            self.preview_label.setText(f"✅ 处理完成（成功 {ok} 个）\n点击下方「打开输出目录」查看")
            self.preview_label.setStyleSheet(
                "border:1px dashed #aaa; color:#4CAF50; background:#000; "
                "font-size:14px;")
        QMessageBox.information(self, "完成",
                                f"成功 {ok} 个，失败 {fail} 个")

        # 计数达到 3 次且未激活 → 弹窗提示购买
        if self.license_mgr is not None:
            try:
                if (not self.license_mgr.is_activated()
                        and self.license_mgr.get_remaining_trials() <= 0):
                    QMessageBox.information(
                        self, "体验次数已用完",
                        "您的 3 次免费体验已全部用完，请点击「🔑 激活」按钮输入授权码后继续使用。"
                    )
            except Exception:
                pass

    def _on_failed(self, err: str):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._log(f"\n❌ 异常: {err}")
        QMessageBox.critical(self, "错误", err)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "确认退出",
                "任务正在运行，确定退出？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait(3000)
        event.accept()


class ActivationDialog(QDialog):
    """激活对话框：显示机器码 + license key 输入框 + 激活按钮"""

    def __init__(self, license_mgr, title: str, message: str, parent=None):
        super().__init__(parent)
        self.license_mgr = license_mgr
        self.setWindowTitle(title)
        self.resize(560, 380)

        layout = QVBoxLayout(self)

        # 提示信息
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # 机器码显示 + 复制按钮
        mid_box = QGroupBox("本机机器码（请将此码发给开发者获取授权码）")
        mid_layout = QHBoxLayout(mid_box)
        self.mid_edit = QLineEdit(license_mgr.machine_id if license_mgr else "")
        self.mid_edit.setReadOnly(True)
        mid_copy_btn = QPushButton("📋 复制")
        mid_copy_btn.clicked.connect(self._copy_machine_id)
        mid_layout.addWidget(self.mid_edit, 1)
        mid_layout.addWidget(mid_copy_btn)
        layout.addWidget(mid_box)

        # license key 输入框（支持多行粘贴）
        key_box = QGroupBox("授权码")
        key_layout = QVBoxLayout(key_box)
        self.key_edit = QTextEdit()
        self.key_edit.setPlaceholderText("在此粘贴授权码…")
        key_layout.addWidget(self.key_edit)
        layout.addWidget(key_box, 1)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_activate = QPushButton("✅ 激活")
        self.btn_activate.setStyleSheet("padding:6px 20px; background:#4CAF50; color:white;")
        self.btn_activate.clicked.connect(self._on_activate)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_activate)
        layout.addLayout(btn_row)

    def _copy_machine_id(self):
        QApplication.clipboard().setText(self.mid_edit.text())
        self.btn_cancel.setText("取消")
        # 简短反馈
        self.btn_activate.setText("✅ 激活（已复制机器码）")
        QTimer.singleShot(2000, lambda: self.btn_activate.setText("✅ 激活"))

    def _on_activate(self):
        key = self.key_edit.toPlainText().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请输入授权码")
            return
        if self.license_mgr is None:
            QMessageBox.critical(self, "错误", "授权模块不可用")
            return
        ok, msg = self.license_mgr.activate(key)
        if ok:
            QMessageBox.information(self, "激活成功", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "激活失败", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
