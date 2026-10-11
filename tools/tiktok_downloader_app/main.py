"""TikTok 博主视频一键下载器 GUI 主程序"""
import os
import sys
import re
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QFileDialog,
    QTextEdit, QProgressBar, QGroupBox, QMessageBox
)


def resource_path(rel: str) -> str:
    """PyInstaller 打包后资源路径"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class DownloadWorker(QThread):
    """后台执行 yt-dlp 子进程"""
    log = Signal(str)
    progress = Signal(int, int, str)  # current, total, title
    finished_signal = Signal(bool, str)

    # yt-dlp 进度行正则：[download] Downloading item N of M
    item_re = re.compile(r"Downloading item (\d+) of (\d+)")
    # 标题行：[TikTok] xxx: Downloading webpage
    title_re = re.compile(r"\[TikTok\] (\d+):")

    def __init__(self, ytdlp_path, url, out_dir, no_overwrite, archive):
        super().__init__()
        self.ytdlp_path = ytdlp_path
        self.url = url
        self.out_dir = out_dir
        self.no_overwrite = no_overwrite
        self.archive = archive
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        import subprocess
        args = [self.ytdlp_path,
                "-o", os.path.join(self.out_dir, "%(id)s.%(ext)s"),
                "--retries", "3",
                "--no-warnings",
                "--newline"]
        if self.no_overwrite:
            args.append("--no-overwrites")
        if self.archive:
            arc_file = os.path.join(self.out_dir, "archive.txt")
            args += ["--download-archive", arc_file]
        args.append(self.url)

        self.log.emit(f"[启动] {self.ytdlp_path}")
        self.log.emit(f"[命令] {' '.join(args)}")
        self.log.emit("")

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            for line in proc.stdout:
                if self._stop:
                    proc.terminate()
                    self.log.emit("\n[已停止] 用户中断下载")
                    self.finished_signal.emit(False, "用户中断")
                    return
                line = line.rstrip()
                if not line:
                    continue
                self.log.emit(line)

                m = self.item_re.search(line)
                if m:
                    cur, total = int(m.group(1)), int(m.group(2))
                    self.progress.emit(cur, total, "")
                else:
                    tm = self.title_re.search(line)
                    if tm:
                        self.progress.emit(-1, -1, tm.group(1))

            proc.wait()
            ok = proc.returncode == 0
            msg = "下载完成" if ok else f"yt-dlp 退出码 {proc.returncode}"
            self.finished_signal.emit(ok, msg)
        except FileNotFoundError:
            self.finished_signal.emit(False, f"找不到 yt-dlp.exe: {self.ytdlp_path}")
        except Exception as e:
            self.finished_signal.emit(False, f"异常: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok 博主视频下载器")
        self.resize(720, 560)
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        # === 输入区 ===
        grp = QGroupBox("下载设置")
        glay = QVBoxLayout(grp)

        # 用户名
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("博主用户名:"))
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("例如 within_elin（无需 @）")
        self.username_edit.returnPressed.connect(self._on_download)
        row1.addWidget(self.username_edit, 1)
        glay.addLayout(row1)

        # URL 预览
        self.url_preview = QLabel()
        self.url_preview.setStyleSheet("color:#666; font-size:11px;")
        self.username_edit.textChanged.connect(self._update_url_preview)
        glay.addWidget(self.url_preview)

        # 下载目录
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("下载目录:"))
        self.dir_edit = QLineEdit()
        default_dir = os.path.join(os.getcwd(), "downloads")
        self.dir_edit.setText(default_dir)
        row2.addWidget(self.dir_edit, 1)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse_dir)
        row2.addWidget(btn_browse)
        glay.addLayout(row2)

        # 选项
        row3 = QHBoxLayout()
        self.chk_no_overwrite = QCheckBox("不覆盖已下载")
        self.chk_no_overwrite.setChecked(True)
        self.chk_archive = QCheckBox("断点续传(archive)")
        self.chk_archive.setChecked(True)
        row3.addWidget(self.chk_no_overwrite)
        row3.addWidget(self.chk_archive)
        row3.addStretch()
        glay.addLayout(row3)

        lay.addWidget(grp)

        # === 操作按钮 ===
        row_btn = QHBoxLayout()
        self.btn_download = QPushButton("开始下载")
        self.btn_download.setStyleSheet("font-weight:bold; padding:6px 24px;")
        self.btn_download.clicked.connect(self._on_download)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        row_btn.addStretch()
        row_btn.addWidget(self.btn_download)
        row_btn.addWidget(self.btn_stop)
        row_btn.addStretch()
        lay.addLayout(row_btn)

        # === 进度条 ===
        self.progress = QProgressBar()
        self.progress.setFormat("等待开始")
        lay.addWidget(self.progress)

        # === 日志区 ===
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("font-family: Consolas, monospace; font-size:12px;")
        lay.addWidget(self.log_view, 1)

        self.status = self.statusBar()
        self.status.showMessage("就绪")

    def _update_url_preview(self):
        u = self.username_edit.text().strip().lstrip("@")
        self.url_preview.setText(f"将下载: https://www.tiktok.com/@{u}" if u else "")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择下载目录", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def _on_download(self):
        username = self.username_edit.text().strip().lstrip("@")
        if not username:
            QMessageBox.warning(self, "提示", "请输入博主用户名")
            return
        out_dir = self.dir_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(self, "提示", "请选择下载目录")
            return
        os.makedirs(out_dir, exist_ok=True)

        ytdlp = resource_path("yt-dlp.exe")
        if not os.path.exists(ytdlp):
            # 退回到工具目录查找
            alt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "yt-dlp", "yt-dlp.exe")
            if os.path.exists(alt):
                ytdlp = alt
            else:
                QMessageBox.critical(self, "错误", f"找不到 yt-dlp.exe:\n{ytdlp}")
                return

        url = f"https://www.tiktok.com/@{username}"
        self.worker = DownloadWorker(
            ytdlp, url, out_dir,
            self.chk_no_overwrite.isChecked(),
            self.chk_archive.isChecked()
        )
        self.worker.log.connect(self._append_log)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

        self.btn_download.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.username_edit.setEnabled(False)
        self.dir_edit.setEnabled(False)
        self.status.showMessage(f"正在下载 @{username} ...")

    def _on_stop(self):
        if self.worker:
            self.worker.stop()

    def _append_log(self, text):
        self.log_view.append(text)
        # 自动滚动到底部
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _update_progress(self, cur, total, title):
        if cur > 0 and total > 0:
            self.progress.setMaximum(total)
            self.progress.setValue(cur)
            self.progress.setFormat(f"已下载 {cur}/{total} 个 ({cur*100//total}%)")
        if title:
            self.status.showMessage(f"正在下载: {title}")

    def _on_finished(self, ok, msg):
        self.btn_download.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.username_edit.setEnabled(True)
        self.dir_edit.setEnabled(True)
        self.status.showMessage(msg)
        self._append_log(f"\n[{'完成' if ok else '结束'}] {msg}")
        if ok:
            self.progress.setFormat("全部完成")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
