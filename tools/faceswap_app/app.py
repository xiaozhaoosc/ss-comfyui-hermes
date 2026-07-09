#!/usr/bin/env python3
"""换脸客户端启动入口"""
import os
import sys

# 推断 CPU/GPU 版本（打包后从 exe 文件名推断，开发模式默认 GPU）
# Why: spec 输出 FaceswapApp_cpu.exe / FaceswapApp_gpu.exe，从文件名推断最可靠
if getattr(sys, 'frozen', False):
    exe_name = os.path.basename(sys.executable).lower()
    if 'cpu' in exe_name:
        os.environ['FACESWAP_VARIANT'] = 'cpu'
    else:
        os.environ['FACESWAP_VARIANT'] = 'gpu'
else:
    os.environ.setdefault("FACESWAP_VARIANT", "gpu")

# 确保模块导入路径（开发模式 & 打包模式都适用）
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
# 上级目录（ComfyUI 根）用于定位 models/
_parent = os.path.dirname(os.path.dirname(_here))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
os.chdir(_parent)  # 工作目录切到 ComfyUI 根，方便定位 models/


def main():
    from PySide6.QtWidgets import QApplication
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("视频换脸客户端")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
