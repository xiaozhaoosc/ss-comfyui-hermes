"""换脸客户端主窗口

三栏专业工作站布局 + 深色主题 QSS。
布局结构：顶部工具栏 / 左栏参数(320) / 中栏预览(stretch) / 右栏进度日志(300) / 状态栏。
"""
from __future__ import annotations

import os
import sys
import time
from html import escape
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
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.engine import EngineConfig
from core.license import LicenseManager
from core.media_utils import imread_unicode, list_audios, list_images, list_videos
from gui.worker import FaceSwapWorker


# ============================================================================
# QSS 深色主题（与 HTML 原型 :root 设计令牌一致）
# Why: 全局 setStyleSheet 一次应用，避免逐控件设样式，保证视觉一致性
# ============================================================================
QSS = """
QMainWindow, QWidget {
    background: #0b0c10;
    color: #e6e8ec;
    font-family: "Segoe UI", "Microsoft YaHei UI", system-ui, sans-serif;
    font-size: 13px;
}
QGroupBox {
    background: #14161c;
    border: 1px solid #2a2e3a;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #9aa0ab;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLineEdit {
    background: #0b0c10;
    border: 1px solid #2a2e3a;
    border-radius: 6px;
    padding: 7px 10px;
    color: #e6e8ec;
    font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
    font-size: 12px;
    selection-background-color: #00d4ff;
}
QLineEdit:focus { border-color: #00d4ff; }
QPushButton {
    background: #1a1d25;
    border: 1px solid #2a2e3a;
    border-radius: 6px;
    padding: 7px 12px;
    color: #9aa0ab;
    font-size: 12px;
}
QPushButton:hover { background: #22262f; color: #e6e8ec; border-color: #3a3f4d; }
QPushButton:disabled { color: #5d6370; background: #14161c; }
QPushButton#btnPrimary {
    background: #00d4ff;
    color: #000;
    font-weight: 600;
    font-size: 13px;
    padding: 10px;
    border: none;
}
QPushButton#btnPrimary:hover { background: #2ee0ff; }
QPushButton#btnPrimary:disabled { background: #1a1d25; color: #5d6370; }
QPushButton#btnDanger {
    background: transparent;
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.3);
}
QPushButton#btnDanger:hover { background: rgba(239,68,68,0.1); }
QPushButton#btnDanger:disabled { color: #5d6370; border-color: #2a2e3a; }
QPushButton#btnActivate {
    background: transparent;
    color: #00d4ff;
    border: 1px solid #00d4ff;
}
QPushButton#btnActivate:hover { background: rgba(0,212,255,0.15); }
QProgressBar {
    background: #0b0c10;
    border: 1px solid #2a2e3a;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00a8cc, stop:1 #00d4ff);
    border-radius: 3px;
}
QSlider::groove:horizontal {
    background: #0b0c10;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00d4ff;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    border: 2px solid #14161c;
}
QSlider::sub-page:horizontal { background: #00d4ff; border-radius: 2px; }
QPlainTextEdit {
    background: #14161c;
    border: 1px solid #2a2e3a;
    border-radius: 6px;
    color: #9aa0ab;
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 11px;
    padding: 8px;
}
QLabel { color: #e6e8ec; }
QLabel#secondary { color: #9aa0ab; font-size: 11px; }
QLabel#tertiary {
    color: #5d6370;
    font-size: 11px;
    font-family: "JetBrains Mono", Consolas, monospace;
}
QLabel#monoAccent {
    color: #00d4ff;
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 11px;
}
QCheckBox { color: #9aa0ab; spacing: 8px; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #3a3f4d; background: #0b0c10; }
QCheckBox::indicator:checked { background: #00d4ff; border-color: #00d4ff; }
QComboBox, QSpinBox {
    background: #0b0c10;
    border: 1px solid #2a2e3a;
    border-radius: 6px;
    padding: 6px 8px;
    color: #e6e8ec;
}
QRadioButton { color: #9aa0ab; spacing: 8px; }
QRadioButton::indicator { width: 14px; height: 14px; border-radius: 7px; border: 1px solid #3a3f4d; background: #0b0c10; }
QRadioButton::indicator:checked { background: #00d4ff; border-color: #00d4ff; }
QStatusBar { background: #14161c; border-top: 1px solid #2a2e3a; color: #5d6370; font-size: 11px; }
QStatusBar::item { border: none; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #2a2e3a; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3a3f4d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; }
QScrollBar::handle:horizontal { background: #2a2e3a; border-radius: 4px; min-width: 30px; }
/* 顶部工具栏 */
QWidget#toolbar {
    background: #14161c;
    border-bottom: 1px solid #2a2e3a;
}
/* 引擎分段开关：模仿 HTML .engine-switch */
QWidget#engineSwitch {
    background: #0b0c10;
    border: 1px solid #2a2e3a;
    border-radius: 6px;
}
QWidget#engineSwitch QPushButton {
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 5px 14px;
    color: #9aa0ab;
    font-size: 12px;
    font-weight: 500;
}
QWidget#engineSwitch QPushButton:hover { background: #1a1d25; }
QWidget#engineSwitch QPushButton:checked {
    background: #1a1d25;
    color: #e6e8ec;
}
QWidget#engineSwitch QPushButton#btnGpu:checked { color: #00d4ff; }
QWidget#engineSwitch QPushButton:disabled { color: #5d6370; }
/* license 徽章 */
QLabel#licenseBadge {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
}
/* 面板分隔 */
QWidget#panelLeft { background: #14161c; border-right: 1px solid #2a2e3a; }
QWidget#panelRight { background: #14161c; border-left: 1px solid #2a2e3a; }
QWidget#previewHeader, QWidget#logHeader, QWidget#progressBlock, QWidget#actionBar {
    background: #14161c;
}
QWidget#previewHeader { border-bottom: 1px solid #2a2e3a; }
QWidget#logHeader { border-bottom: 1px solid #2a2e3a; }
QWidget#progressBlock { border-bottom: 1px solid #2a2e3a; }
QWidget#actionBar { border-top: 1px solid #2a2e3a; }
"""


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
    """换脸客户端主窗口（三栏工作站布局）"""

    def __init__(self):
        super().__init__()
        self.resize(1280, 800)

        # license 管理器先初始化，标题栏更新与试用拦截都依赖它
        # Why: 所有 license 操作 try-except，异常退化为未激活而非崩溃
        try:
            self.license_mgr = LicenseManager()
        except Exception:
            self.license_mgr = None

        self.worker: FaceSwapWorker | None = None
        # 预览状态：idle / running / done
        self._preview_state = "idle"
        # 任务计时起点，用于状态栏已用时间
        self._start_ts: float | None = None

        self._init_ui()
        self.setStyleSheet(QSS)
        self._apply_variant()  # CPU 版禁用 GPU（须在 _detect_gpu 前生效）
        self._detect_gpu()
        self._update_title()
        self._check_license()  # 篡改/试用耗尽检测弹窗

        # 默认输出目录
        default_out = str(Path.cwd() / "output" / "faceswap_app")
        self.output_picker.edit.setText(default_out)
        self._update_status_output(default_out)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部工具栏
        self._build_toolbar(root)

        # 主体三栏
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_left_panel(), 0)
        body.addWidget(self._build_center_panel(), 1)
        body.addWidget(self._build_right_panel(), 0)
        root.addLayout(body, 1)

        # 状态栏
        self._build_statusbar()

    # ---------- 顶部工具栏 ----------

    def _build_toolbar(self, parent_layout: QVBoxLayout):
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(44)
        lay = QHBoxLayout(toolbar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(16)

        # GPU/CPU 分段开关：两个互斥 checkable 按钮
        engine_switch = QWidget()
        engine_switch.setObjectName("engineSwitch")
        es_lay = QHBoxLayout(engine_switch)
        es_lay.setContentsMargins(2, 2, 2, 2)
        es_lay.setSpacing(0)
        self.btn_gpu = QPushButton("GPU")
        self.btn_gpu.setObjectName("btnGpu")
        self.btn_gpu.setCheckable(True)
        self.btn_gpu.setChecked(True)
        self.btn_cpu = QPushButton("CPU")
        self.btn_cpu.setObjectName("btnCpu")
        self.btn_cpu.setCheckable(True)
        self.engine_group = QButtonGroup(self)
        self.engine_group.setExclusive(True)
        self.engine_group.addButton(self.btn_gpu)
        self.engine_group.addButton(self.btn_cpu)
        es_lay.addWidget(self.btn_gpu)
        es_lay.addWidget(self.btn_cpu)
        lay.addWidget(engine_switch)

        # onnxruntime 状态：版本 + CUDA 可用性
        self.ort_status = QLabel("检测中…")
        self.ort_status.setObjectName("tertiary")
        self.ort_status.setTextFormat(Qt.RichText)
        lay.addWidget(self.ort_status)

        lay.addStretch(1)

        # license 徽章：显示试用次数/已激活
        self.license_badge = QLabel("体验版")
        self.license_badge.setObjectName("licenseBadge")
        lay.addWidget(self.license_badge)

        # 激活按钮：青色描边样式
        self.btn_activate = QPushButton("🔑 激活授权")
        self.btn_activate.setObjectName("btnActivate")
        self.btn_activate.clicked.connect(self._on_activate)
        lay.addWidget(self.btn_activate)

        parent_layout.addWidget(toolbar)

    # ---------- 左栏：参数面板 ----------

    def _build_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(320)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        content = QWidget()
        content.setObjectName("panelLeft")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ① 人脸源
        face_box = QGroupBox("① 人脸源")
        face_layout = QVBoxLayout(face_box)
        self.face_picker = FilePicker(
            mode="file",
            filter="图片 (*.png *.jpg *.jpeg *.bmp *.webp)",
            placeholder="选择人脸源图片")
        face_layout.addWidget(self.face_picker)
        self.face_preview = QLabel("（选择图片后显示预览）")
        self.face_preview.setObjectName("secondary")
        self.face_preview.setFixedSize(140, 140)
        self.face_preview.setAlignment(Qt.AlignCenter)
        self.face_preview.setStyleSheet(
            "border:1px dashed #3a3f4d; color:#5d6370; border-radius:6px;")
        face_layout.addWidget(self.face_preview, 0, Qt.AlignHCenter)
        self.face_picker.edit.textChanged.connect(self._update_face_preview)
        layout.addWidget(face_box)

        # ② 视频源
        video_box = QGroupBox("② 视频源")
        video_layout = QVBoxLayout(video_box)
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
        self.video_picker = FilePicker(
            mode="file",
            filter="视频 (*.mp4 *.avi *.mov *.mkv *.flv *.webm)",
            placeholder="选择视频文件")
        video_layout.addWidget(self.video_picker)
        self.video_info = QLabel("")
        self.video_info.setObjectName("tertiary")
        video_layout.addWidget(self.video_info)
        self.video_picker.edit.textChanged.connect(self._update_video_info)
        layout.addWidget(video_box)

        # ③ BGM
        bgm_box = QGroupBox("③ BGM")
        bgm_layout = QVBoxLayout(bgm_box)
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
        self.bgm_picker = FilePicker(
            mode="file",
            filter="音频 (*.mp3 *.wav *.aac *.m4a *.flac *.ogg)",
            placeholder="选择 BGM 文件")
        bgm_layout.addWidget(self.bgm_picker)

        # 原音音量
        orig_row = QHBoxLayout()
        orig_label = QLabel("原音音量")
        orig_label.setObjectName("secondary")
        self.orig_vol = QSlider(Qt.Horizontal)
        self.orig_vol.setRange(0, 100)
        self.orig_vol.setValue(100)
        self.orig_vol_label = QLabel("100%")
        self.orig_vol_label.setObjectName("monoAccent")
        self.orig_vol.valueChanged.connect(
            lambda v: self.orig_vol_label.setText(f"{v}%"))
        orig_row.addWidget(orig_label)
        orig_row.addWidget(self.orig_vol, 1)
        orig_row.addWidget(self.orig_vol_label)
        bgm_layout.addLayout(orig_row)

        # BGM 音量
        bgm_vol_row = QHBoxLayout()
        bgm_vol_label = QLabel("BGM 音量")
        bgm_vol_label.setObjectName("secondary")
        self.bgm_vol = QSlider(Qt.Horizontal)
        self.bgm_vol.setRange(0, 100)
        self.bgm_vol.setValue(50)
        self.bgm_vol_label = QLabel("50%")
        self.bgm_vol_label.setObjectName("monoAccent")
        self.bgm_vol.valueChanged.connect(
            lambda v: self.bgm_vol_label.setText(f"{v}%"))
        bgm_vol_row.addWidget(bgm_vol_label)
        bgm_vol_row.addWidget(self.bgm_vol, 1)
        bgm_vol_row.addWidget(self.bgm_vol_label)
        bgm_layout.addLayout(bgm_vol_row)

        self.keep_original = QCheckBox("保留原音（与 BGM 混合，取消则仅保留 BGM）")
        self.keep_original.setChecked(True)
        bgm_layout.addWidget(self.keep_original)
        layout.addWidget(bgm_box)

        # ④ 引擎参数（GPU/CPU 已移至顶部工具栏，此处仅保留高级参数）
        engine_box = QGroupBox("④ 引擎参数")
        engine_layout = QVBoxLayout(engine_box)
        # 高级参数：最大片段 + 帧率
        adv_row = QHBoxLayout()
        seg_label = QLabel("最大片段(秒)")
        seg_label.setObjectName("secondary")
        self.seg_spin = QSpinBox()
        self.seg_spin.setRange(5, 120)
        self.seg_spin.setValue(15)
        fps_label = QLabel("帧率")
        fps_label.setObjectName("secondary")
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(25)
        adv_row.addWidget(seg_label)
        adv_row.addWidget(self.seg_spin, 1)
        adv_row.addSpacing(8)
        adv_row.addWidget(fps_label)
        adv_row.addWidget(self.fps_spin, 1)
        engine_layout.addLayout(adv_row)
        self.gfpgan_chk = QCheckBox("启用 GFPGAN 画质修复")
        self.gfpgan_chk.setChecked(True)
        engine_layout.addWidget(self.gfpgan_chk)
        layout.addWidget(engine_box)

        # ⑤ 输出目录
        out_box = QGroupBox("⑤ 输出目录")
        out_layout = QVBoxLayout(out_box)
        self.output_picker = FilePicker(mode="dir", placeholder="选择输出目录")
        out_layout.addWidget(self.output_picker)
        self.output_picker.edit.textChanged.connect(self._update_status_output)
        layout.addWidget(out_box)

        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    # ---------- 中栏：预览区（主角） ----------

    def _build_center_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 预览头部：标题 + meta（分辨率/帧率/片段）
        header = QWidget()
        header.setObjectName("previewHeader")
        header.setFixedHeight(36)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)
        h_lay.setSpacing(12)
        title = QLabel("实时预览")
        title.setObjectName("secondary")
        self.preview_meta = QLabel("")
        self.preview_meta.setObjectName("tertiary")
        h_lay.addWidget(title)
        h_lay.addStretch(1)
        h_lay.addWidget(self.preview_meta)
        layout.addWidget(header)

        # 预览舞台：黑底，显示流式帧
        stage = QWidget()
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(24, 24, 24, 24)
        self.preview_label = QLabel("选择参数后点击开始换脸")
        self.preview_label.setMinimumHeight(300)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self._apply_preview_idle_style()
        stage_layout.addWidget(self.preview_label)
        layout.addWidget(stage, 1)

        # 预览底部控制条：帧计数 + 帧进度条 + FPS/ETA
        controls = QWidget()
        controls.setObjectName("previewHeader")
        controls.setFixedHeight(48)
        c_lay = QHBoxLayout(controls)
        c_lay.setContentsMargins(16, 0, 16, 0)
        c_lay.setSpacing(12)
        self.frame_counter = QLabel("帧 0 / 0")
        self.frame_counter.setObjectName("tertiary")
        self.frame_counter.setTextFormat(Qt.RichText)
        self.frame_progress = QProgressBar()
        self.frame_progress.setRange(0, 100)
        self.frame_progress.setFixedHeight(3)
        self.frame_progress.setTextVisible(False)
        self.frame_fps = QLabel("")
        self.frame_fps.setObjectName("tertiary")
        self.frame_fps.setTextFormat(Qt.RichText)
        c_lay.addWidget(self.frame_counter)
        c_lay.addWidget(self.frame_progress, 1)
        c_lay.addWidget(self.frame_fps)
        layout.addWidget(controls)

        return panel

    # ---------- 右栏：进度 + 日志 + 操作按钮 ----------

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("panelRight")
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 进度块
        prog_widget = QWidget()
        prog_widget.setObjectName("progressBlock")
        prog_lay = QVBoxLayout(prog_widget)
        prog_lay.setContentsMargins(14, 14, 14, 14)
        prog_lay.setSpacing(8)
        # 阶段行：图标 + 阶段名 + 百分比
        stage_row = QHBoxLayout()
        stage_row.setSpacing(8)
        self.stage_icon = QLabel("●")
        self.stage_icon.setObjectName("secondary")
        self.stage_icon.setFixedSize(20, 20)
        self.stage_icon.setAlignment(Qt.AlignCenter)
        self.stage_label = QLabel("就绪")
        self.stage_label.setObjectName("secondary")
        self.stage_label.setStyleSheet("font-weight:600; color:#e6e8ec; font-size:12px;")
        self.stage_pct = QLabel("0%")
        self.stage_pct.setObjectName("monoAccent")
        self.stage_pct.setStyleSheet("font-size:13px; font-weight:600; color:#00d4ff;")
        stage_row.addWidget(self.stage_icon)
        stage_row.addWidget(self.stage_label)
        stage_row.addStretch(1)
        stage_row.addWidget(self.stage_pct)
        prog_lay.addLayout(stage_row)
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        prog_lay.addWidget(self.progress_bar)
        # 统计行：片段/已用/剩余
        self.progress_stats = QLabel("")
        self.progress_stats.setObjectName("tertiary")
        prog_lay.addWidget(self.progress_stats)
        layout.addWidget(prog_widget)

        # 日志块：先创建 log_view，再创建头部（清空按钮需要引用）
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        log_header = QWidget()
        log_header.setObjectName("logHeader")
        log_header.setFixedHeight(32)
        lh_lay = QHBoxLayout(log_header)
        lh_lay.setContentsMargins(14, 0, 14, 0)
        log_title = QLabel("日志")
        log_title.setObjectName("secondary")
        log_title.setStyleSheet("font-weight:600;")
        btn_clear = QPushButton("清空")
        btn_clear.setStyleSheet(
            "background:transparent; border:none; color:#5d6370; font-size:10px;")
        btn_clear.clicked.connect(self.log_view.clear)
        lh_lay.addWidget(log_title)
        lh_lay.addStretch(1)
        lh_lay.addWidget(btn_clear)
        layout.addWidget(log_header)
        layout.addWidget(self.log_view, 1)

        # 操作按钮
        action_widget = QWidget()
        action_widget.setObjectName("actionBar")
        action_lay = QVBoxLayout(action_widget)
        action_lay.setContentsMargins(14, 12, 14, 12)
        action_lay.setSpacing(8)
        self.btn_start = QPushButton("▶ 开始换脸")
        self.btn_start.setObjectName("btnPrimary")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_open_out = QPushButton("📂 打开输出目录")
        self.btn_open_out.clicked.connect(self._open_output)
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setObjectName("btnDanger")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        action_lay.addWidget(self.btn_start)
        action_lay.addWidget(self.btn_open_out)
        action_lay.addWidget(self.btn_stop)
        layout.addWidget(action_widget)

        return panel

    # ---------- 状态栏 ----------

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        # 左：就绪状态（绿点 + 文字）
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color:#10b981; font-size:8px;")
        self.status_text = QLabel("就绪")
        self.status_text.setStyleSheet("color:#5d6370;")
        sb.addWidget(self.status_dot)
        sb.addWidget(self.status_text)
        # 中：输出路径
        self.status_output = QLabel("")
        self.status_output.setStyleSheet("color:#5d6370;")
        sb.addWidget(self.status_output, 1)
        # 右：版本信息
        self.status_version = QLabel("v1.0.0")
        self.status_version.setStyleSheet("color:#5d6370;")
        sb.addPermanentWidget(self.status_version)

    # ------------------------------------------------------------------
    # 预览区状态样式
    # ------------------------------------------------------------------

    def _apply_preview_idle_style(self):
        self.preview_label.setStyleSheet(
            "background:#000; color:#5d6370; border:1px solid #2a2e3a; border-radius:8px;")

    def _apply_preview_running_style(self):
        self.preview_label.setStyleSheet(
            "background:#000; color:#9aa0ab; border:1px solid #2a2e3a; border-radius:8px;")

    def _apply_preview_done_style(self):
        self.preview_label.setStyleSheet(
            "background:#000; color:#10b981; border:1px solid #10b981; border-radius:8px; font-size:14px;")

    # ------------------------------------------------------------------
    # 状态栏 / 徽章 更新
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str = "#10b981"):
        """更新状态栏左侧就绪状态"""
        self.status_text.setText(text)
        self.status_dot.setStyleSheet(f"color:{color}; font-size:8px;")

    def _update_status_output(self, path: str):
        """更新状态栏中部输出路径"""
        p = path.strip() if path else ""
        if p:
            self.status_output.setText(f"输出: {p}")
        else:
            self.status_output.setText("")

    def _update_status_version(self):
        """更新状态栏右侧版本信息（GPU/CPU 版）"""
        variant = os.environ.get("FACESWAP_VARIANT", "gpu").lower()
        self.status_version.setText(f"v1.0.0 · {variant.upper()} 版")

    # ------------------------------------------------------------------
    # GPU 检测 / variant
    # ------------------------------------------------------------------

    def _detect_gpu(self):
        """启动时检测 onnxruntime GPU 支持情况"""
        try:
            import onnxruntime
            providers = onnxruntime.get_available_providers()
            has_cuda = 'CUDAExecutionProvider' in providers
            ort_ver = onnxruntime.__version__
            cuda_str = "✅" if has_cuda else "⚠️"
            self.ort_status.setText(
                f"<b style='color:#9aa0ab'>onnxruntime {ort_ver}</b> · "
                f"CUDA {cuda_str} · providers: {', '.join(providers)}"
            )
            if not has_cuda:
                self.btn_cpu.setChecked(True)
                self.btn_gpu.setEnabled(False)
        except ImportError:
            self.ort_status.setText("未安装 onnxruntime")
            self.btn_cpu.setChecked(True)
            self.btn_gpu.setEnabled(False)

    def _apply_variant(self):
        """CPU 版禁用 GPU 选项（通过 FACESWAP_VARIANT 环境变量推断）"""
        variant = os.environ.get("FACESWAP_VARIANT", "gpu").lower()
        if variant == "cpu":
            self.btn_gpu.setEnabled(False)
            self.btn_cpu.setChecked(True)
            self.ort_status.setText("CPU 版本不支持 GPU 加速")
        self._update_status_version()

    # ------------------------------------------------------------------
    # license 相关
    # ------------------------------------------------------------------

    def _update_title(self):
        """根据 license 状态更新标题栏 + 工具栏 license 徽章"""
        if self.license_mgr is None:
            self.setWindowTitle("视频换脸工作站")
            self.license_badge.setText("未授权")
            self.license_badge.setStyleSheet(
                "color:#5d6370; background:rgba(93,99,112,0.1); "
                "border:1px solid rgba(93,99,112,0.3);")
            return
        if self.license_mgr.is_activated():
            self.setWindowTitle("视频换脸工作站 - 已授权")
            self.license_badge.setText("● 已授权")
            self.license_badge.setStyleSheet(
                "color:#10b981; background:rgba(16,185,129,0.1); "
                "border:1px solid rgba(16,185,129,0.3);")
        else:
            remaining = self.license_mgr.get_remaining_trials()
            self.setWindowTitle(f"视频换脸工作站 - 体验版（剩余 {remaining}/3 次）")
            self.license_badge.setText(f"● 体验版 · 剩余 {remaining}/3 次")
            self.license_badge.setStyleSheet(
                "color:#f59e0b; background:rgba(245,158,11,0.1); "
                "border:1px solid rgba(245,158,11,0.3);")

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
            self._append_log("✓ 授权激活成功", "ok")
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

    # ------------------------------------------------------------------
    # 人脸预览 / 视频信息
    # ------------------------------------------------------------------

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
                140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _update_video_info(self, path: str):
        if not path:
            self.video_info.setText("")
            self.preview_meta.setText("")
            return
        if os.path.isdir(path):
            videos = list_videos(path)
            self.video_info.setText(f"目录模式: {len(videos)} 个视频")
            return
        if not os.path.isfile(path):
            self.video_info.setText("")
            self.preview_meta.setText("")
            return
        from core.media_utils import get_video_duration, get_video_fps, get_video_resolution
        try:
            dur = get_video_duration(path)
            fps = get_video_fps(path)
            w, h = get_video_resolution(path)
            self.video_info.setText(f"{dur:.1f}s | {fps:.1f}fps | {w}x{h}")
            # 同步预览头部 meta 信息
            self.preview_meta.setText(
                f"分辨率 <b style='color:#9aa0ab'>{w}×{h}</b>  "
                f"帧率 <b style='color:#9aa0ab'>{fps:.0f} fps</b>")
        except Exception as e:
            self.video_info.setText(f"读取失败: {e}")

    # ------------------------------------------------------------------
    # FilePicker 模式切换（双按钮直接弹对话框）
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # 打开输出目录
    # ------------------------------------------------------------------

    def _open_output(self):
        out = self.output_picker.text() or "."
        os.makedirs(out, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(out)
        elif sys.platform == "darwin":
            os.system(f'open "{out}"')
        else:
            os.system(f'xdg-open "{out}"')

    # ------------------------------------------------------------------
    # 日志（语义着色）
    # ------------------------------------------------------------------

    def _append_log(self, msg: str, level: str = "info"):
        """语义着色日志输出

        level 对应颜色：
            info   #9aa0ab（默认灰）
            ok     #10b981（绿色）
            warn   #f59e0b（黄色）
            err    #ef4444（红色）
            accent #00d4ff（青色）
        """
        colors = {
            "info": "#9aa0ab",
            "ok": "#10b981",
            "warn": "#f59e0b",
            "err": "#ef4444",
            "accent": "#00d4ff",
        }
        color = colors.get(level, colors["info"])
        timestamp = time.strftime("%H:%M:%S")
        safe_msg = escape(msg)
        html = (
            f'<span style="color:#5d6370">{timestamp}</span> '
            f'<span style="color:{color}">{safe_msg}</span>'
        )
        self.log_view.appendHtml(html)

    def _on_log(self, msg: str):
        """worker.log 信号处理：根据前缀自动推断级别"""
        if msg.startswith("✓") or msg.startswith("✅"):
            level = "ok"
        elif msg.startswith("▶"):
            level = "accent"
        elif msg.startswith("⚠") or msg.startswith("⚠️"):
            level = "warn"
        elif msg.startswith("❌"):
            level = "err"
        else:
            level = "info"
        self._append_log(msg, level)

    def _log(self, msg: str):
        """内部日志快捷方法（转发到 _on_log 自动着色）"""
        self._on_log(msg)

    # ------------------------------------------------------------------
    # 启动 / 停止
    # ------------------------------------------------------------------

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
            use_gpu=self.btn_gpu.isChecked(),
            max_segment_sec=float(self.seg_spin.value()),
            fps=self.fps_spin.value(),
            enable_gfpgan=self.gfpgan_chk.isChecked(),
        )

        self.log_view.clear()
        self._append_log("=== 开始任务 ===", "accent")
        self._append_log(f"人脸源: {config.face_source}")
        self._append_log(f"视频源: {config.video_source}")
        self._append_log(f"BGM: {config.bgm_source or '无'}")
        self._append_log(f"引擎: {'GPU' if config.use_gpu else 'CPU'}")

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.stage_pct.setText("0%")
        self.frame_progress.setValue(0)
        # 重置预览区为运行态
        self._preview_state = "running"
        self.preview_label.clear()
        self.preview_label.setText("等待帧生成…")
        self._apply_preview_running_style()
        # 状态栏切换为处理中
        self._set_status("处理中", "#00d4ff")
        self._start_ts = time.time()

        self.worker = FaceSwapWorker(config)
        self.worker.progress.connect(self._on_progress)
        self.worker.frame_preview.connect(self._on_frame_preview)
        self.worker.log.connect(self._on_log)
        self.worker.finished_all.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_stop(self):
        if self.worker and self.worker.isRunning():
            self._append_log("⚠️ 正在停止（等待当前片段完成）…", "warn")
            self.worker.cancel()
            self.btn_stop.setEnabled(False)

    def _on_progress(self, stage: str, current: int, total: int, msg: str):
        # preview 阶段已由 worker 路由到 frame_preview，此处仅防御性跳过
        if stage == "preview":
            return
        self.stage_label.setText(msg or stage)
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setValue(pct)
            self.stage_pct.setText(f"{pct}%")
            # 预览底部帧进度
            self.frame_counter.setText(
                f"帧 <b style='color:#00d4ff'>{current}</b> / {total}")
            self.frame_progress.setValue(pct)
            # 统计行：已用时间 + 进度
            elapsed = ""
            if self._start_ts:
                secs = int(time.time() - self._start_ts)
                m, s = divmod(secs, 60)
                elapsed = f"  ·  已用 {m:02d}:{s:02d}"
            self.progress_stats.setText(
                f"{current}/{total}  ·  {pct}%{elapsed}")

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

        self._append_log("=== 全部完成 ===", "accent")
        self._append_log(f"成功 {ok} 个，失败 {fail} 个", "ok" if fail == 0 else "warn")
        for r in results:
            if r.success:
                self._append_log(
                    f"✓ {r.output_path} ({r.frames_processed} 帧, {r.elapsed_sec:.0f}s)",
                    "ok")
            else:
                self._append_log(f"✗ {r.error}", "err")

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
            self.stage_pct.setText("100%")
            self.frame_progress.setValue(100)
            self.stage_label.setText("完成")
            self.stage_icon.setText("✓")
            # 预览区显示完成提示
            self._preview_state = "done"
            self.preview_label.clear()
            self.preview_label.setText(f"✓ 处理完成（成功 {ok} 个）\n点击下方「打开输出目录」查看")
            self._apply_preview_done_style()
        # 状态栏恢复就绪
        self._set_status("就绪", "#10b981")
        self._start_ts = None
        QMessageBox.information(self, "完成", f"成功 {ok} 个，失败 {fail} 个")

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
        self._append_log(f"✗ 异常: {err}", "err")
        # 预览区恢复空闲态
        self._preview_state = "idle"
        self.preview_label.clear()
        self.preview_label.setText("处理失败")
        self._apply_preview_idle_style()
        # 状态栏恢复就绪
        self._set_status("就绪", "#10b981")
        self._start_ts = None
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
        self.btn_activate.setObjectName("btnPrimary")
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
