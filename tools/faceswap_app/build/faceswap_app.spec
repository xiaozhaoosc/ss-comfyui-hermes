# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec - 换脸客户端

用法:
  # CPU 版
  set FACESWAP_VARIANT=cpu && pyinstaller build/faceswap_app.spec --noconfirm
  # GPU 版
  set FACESWAP_VARIANT=gpu && pyinstaller build/faceswap_app.spec --noconfirm

环境变量 FACESWAP_VARIANT 决定:
- 输出目录名 (dist/FaceswapApp_cpu 或 dist/FaceswapApp_gpu)
- 收集 onnxruntime 还是 onnxruntime-gpu
"""
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

VARIANT = os.environ.get("FACESWAP_VARIANT", "cpu").lower()  # cpu | gpu
IS_GPU = VARIANT == "gpu"

block_cipher = None

# 动态导入的模块（insightface/gfpgan 经常用 importlib，PyInstaller 扫不到）
hiddenimports = []
hiddenimports += collect_submodules("insightface")
hiddenimports += collect_submodules("gfpgan")
hiddenimports += collect_submodules("onnxruntime")
if IS_GPU:
    hiddenimports += collect_submodules("onnxruntime.capi._pybind_state")
hiddenimports += [
    "cv2", "numpy", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
]

# 数据文件（模型 onnx 等不打包，外置到安装目录）
datas = []
datas += collect_data_files("insightface")
datas += collect_data_files("gfpgan")
datas += collect_data_files("PySide6", include_py_files=False)

# 二进制（CUDA DLL 仅 GPU 版收集）
binaries = []
if IS_GPU:
    # onnxruntime-gpu 的 CUDA 依赖 DLL 由 collect_dynamic_libs 自动收集
    try:
        from PyInstaller.utils.hooks import collect_dynamic_libs
        binaries += collect_dynamic_libs("onnxruntime")
        binaries += collect_dynamic_libs("torch")
    except Exception:
        pass

a = Analysis(
    # app.py 与 ComfyUI 根均基于 SPECPATH 推导，避免依赖调用时的工作目录
    [os.path.join(SPECPATH, "..", "app.py")],
    pathex=[os.path.abspath(os.path.join(SPECPATH, "..", "..", ".."))],  # ComfyUI 根，用于定位 models
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f"FaceswapApp_{VARIANT}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 程序不显示控制台
    disable_windowed_traceback=False,
    icon=None,  # TODO: 可加 icon="build/app.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=f"FaceswapApp_{VARIANT}",
)
