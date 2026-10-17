"""PySide6 桌面客户端：QThread + Signal 接 core 事件（照搬 tiktok_downloader_app 模式）。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from PySide6.QtCore import Qt, QThread, Signal  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QProgressBar, QPushButton, QTextEdit,
    QVBoxLayout, QWidget, QSpinBox,
)

from core.jobs import JobManager  # noqa: E402
from core.model import JobSpec  # noqa: E402
from core.sites import ADAPTER  # noqa: E402


class DownloadWorker(QThread):
    log = Signal(str)
    progress = Signal(dict)
    stateChanged = Signal(str)
    finishedSignal = Signal(bool, str)

    def __init__(self, spec: JobSpec, parent=None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.mgr = JobManager()
        self.job = None

    def run(self) -> None:
        self.job = self.mgr.submit(self.spec)
        q = self.mgr.events(self.job.id)
        while True:
            try:
                ev = q.get(timeout=1.0)
            except Exception:
                if self.job.state.value in ("done", "failed", "cancelled"):
                    break
                continue
            t = ev.get("type")
            if t == "log":
                self.log.emit(ev.get("text", ""))
            elif t == "progress":
                self.progress.emit(ev)
            elif t == "state":
                self.stateChanged.emit(ev.get("state", ""))
            if t in ("done", "failed", "cancelled"):
                break
        ok = self.job.state.value == "done"
        self.finishedSignal.emit(ok, self.job.error or "")

    def stop(self) -> None:
        if self.job:
            self.mgr.cancel(self.job.id)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("media_dl · 通用媒体下载器")
        self.resize(880, 720)
        self.worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        c = QWidget()
        self.setCentralWidget(c)
        v = QVBoxLayout(c)

        g1 = QGroupBox("下载设置")
        f1 = QVBoxLayout(g1)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://www.instagram.com/ayano.fj/")
        self.url.editingFinished.connect(self._probe)
        self.probe = QLabel("—")
        self.probe.setStyleSheet("color:#6b7280")
        row = QHBoxLayout()
        self.engine = QComboBox()
        self.engine.addItems(["auto", "gallery-dl", "yt-dlp"])
        self.media = QComboBox()
        self.media.addItems(["all", "video", "image"])
        self.count = QSpinBox()
        self.count.setRange(0, 9999)
        self.count.setSpecialValueText("全部")
        self.days = QSpinBox()
        self.days.setRange(0, 3650)
        self.days.setSpecialValueText("不限")
        for w, lbl in ((self.engine, "引擎"), (self.media, "媒体"), (self.count, "条数"), (self.days, "最近N天")):
            box = QVBoxLayout()
            box.addWidget(QLabel(lbl))
            box.addWidget(w)
            row.addLayout(box)
        f1.addWidget(QLabel("URL"))
        f1.addWidget(self.url)
        f1.addWidget(self.probe)
        f1.addLayout(row)
        v.addWidget(g1)

        g2 = QGroupBox("Cookies（可选 · 仅内存，用完即删）")
        f2 = QVBoxLayout(g2)
        r2 = QHBoxLayout()
        self.cookies_path = QLineEdit()
        self.cookies_path.setPlaceholderText("选择 Netscape cookies.txt（留空则尝试 Chrome 9222）")
        b2 = QPushButton("浏览...")
        b2.clicked.connect(self._pick_cookies)
        r2.addWidget(self.cookies_path)
        r2.addWidget(b2)
        self.use_cdp = QCheckBox("允许从 Chrome 9222 取登录态")
        self.use_cdp.setChecked(True)
        self.simulate = QCheckBox("只枚举不下载")
        r3 = QHBoxLayout()
        self.probe_cdp_btn = QPushButton("检测 9222")
        self.probe_cdp_btn.clicked.connect(self._probe_cdp)
        self.cdp_status = QLabel("9222：未检测")
        self.cdp_status.setStyleSheet("color:#6b7280")
        r3.addWidget(self.probe_cdp_btn)
        r3.addWidget(self.cdp_status, 1)
        f2.addLayout(r2)
        f2.addWidget(self.use_cdp)
        f2.addWidget(self.simulate)
        f2.addLayout(r3)
        v.addWidget(g2)

        g3 = QGroupBox("进度")
        f3 = QVBoxLayout(g3)
        self.state = QLabel("待命")
        self.bar = QProgressBar()
        self.pctxt = QLabel("")
        f3.addWidget(self.state)
        f3.addWidget(self.bar)
        f3.addWidget(self.pctxt)
        v.addWidget(g3)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background:#0f172a;color:#d5dae5;font-family:Consolas")
        v.addWidget(self.log, 1)

        r4 = QHBoxLayout()
        self.go = QPushButton("开始下载")
        self.go.clicked.connect(self._start)
        self.cancel = QPushButton("取消")
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self._cancel)
        self.open = QPushButton("打开产物目录")
        self.open.clicked.connect(self._open_dir)
        r4.addWidget(self.go)
        r4.addWidget(self.cancel)
        r4.addWidget(self.open)
        r4.addStretch(1)
        v.addLayout(r4)

    # ---------------- 槽 ----------------
    def _probe(self) -> None:
        u = self.url.text().strip()
        if not u:
            return
        try:
            d = ADAPTER.resolve(u)
            self.probe.setText(f"识别：{d.rule.name} ｜ 引擎 {list(d.engines)} ｜ 目录 {d.out_name}"
                               + (" ｜ 需要登录态" if d.need_cookie else ""))
        except Exception as exc:
            self.probe.setText(f"识别失败：{exc}")

    def _probe_cdp(self) -> None:
        """可选功能：只探测 9222，不改变 use_cdp 的取值。"""
        from core.cookies import probe_cdp
        self.cdp_status.setText("9222：检测中...")
        QApplication.processEvents()
        r = probe_cdp(9222, self.url.text().strip())
        icon = "✅" if r["ok"] else ("⚠️" if r["reachable"] else "⛔")
        txt = f"{icon} 9222：{r['detail']}"
        if r["ok"]:
            txt += f" ｜ 账号 {r['ig_username']}"
        self.cdp_status.setText(txt)
        self.log.append(f"[9222 探测] 可达={r['reachable']} 浏览器={r['browser'] or '-'} "
                        f"cookie={r['cookie_count']} 已登录={r['logged_in']} 账号={r['ig_username'] or '-'}")

    def _pick_cookies(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "选择 cookies.txt", "", "Text (*.txt);;All (*)")
        if p:
            self.cookies_path.setText(p)

    def _start(self) -> None:
        u = self.url.text().strip()
        if not u:
            self.log.append("请填 URL")
            return
        spec = JobSpec(
            url=u, engine=self.engine.currentText(), media_filter=self.media.currentText(),
            item_range=(f"1-{self.count.value()}" if self.count.value() else None),
            days=(self.days.value() or None), simulate=self.simulate.isChecked(),
            cookies_file=self.cookies_path.text().strip() or None,
            use_cdp=self.use_cdp.isChecked(),
        )
        self.worker = DownloadWorker(spec)
        self.worker.log.connect(self.log.append)
        self.worker.progress.connect(self._on_progress)
        self.worker.stateChanged.connect(lambda s: self.state.setText(s))
        self.worker.finishedSignal.connect(self._on_done)
        self.worker.start()
        self.go.setEnabled(False)
        self.cancel.setEnabled(True)

    def _cancel(self) -> None:
        if self.worker:
            self.worker.stop()
            self.log.append("[取消] 已请求停止")

    def _on_progress(self, ev: dict) -> None:
        d, t = ev.get("done", 0), ev.get("total", 0)
        self.pctxt.setText(f"已下载 {d}" + (f" / {t}" if t else ""))
        if t:
            self.bar.setValue(int(d / t * 100))

    def _on_done(self, ok: bool, err: str) -> None:
        self.go.setEnabled(True)
        self.cancel.setEnabled(False)
        self.state.setText("完成" if ok else "失败")
        self.bar.setValue(100 if ok else 0)
        if err:
            self.log.append(f"[错误] {err}")

    def _open_dir(self) -> None:
        import os
        import subprocess
        d = getattr(self.worker, "job", None)
        if d and d.out_dir:
            try:
                os.startfile(d.out_dir)  # noqa: S606
                return
            except Exception:
                subprocess.Popen(["explorer", d.out_dir])
        self.log.append("还没有产物目录")


def main(argv=None) -> int:
    app = QApplication(argv or sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
