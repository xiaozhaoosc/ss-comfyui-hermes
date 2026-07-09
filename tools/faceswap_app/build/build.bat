@echo off
chcp 65001 >nul
REM ============================================================
REM 换脸客户端一键打包脚本
REM 用法:
REM   build.bat cpu    REM 打包 CPU 版安装包
REM   build.bat gpu    REM 打包 GPU 版安装包
REM   build.bat both   REM 打包两个版本
REM ============================================================

setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
cd /d "%ROOT%"

set "VARIANT=%1"
if "%VARIANT%"=="" set "VARIANT=both"

REM 检查 PyInstaller
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 pyinstaller，请先 pip install pyinstaller
    exit /b 1
)

REM 检查 Inno Setup
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [警告] 未找到 Inno Setup 6，将跳过安装包生成
    echo        请从 https://jrsoftware.org/isdl.php 安装
    set "ISCC="
)

REM 准备 ffmpeg（如 build/bin/ 不存在，尝试从 PATH 复制）
if not exist "build\bin\ffmpeg.exe" (
    where ffmpeg >nul 2>&1
    if not errorlevel 1 (
        mkdir "build\bin" 2>nul
        for /f "delims=" %%i in ('where ffmpeg') do copy "%%i" "build\bin\ffmpeg.exe" >nul 2>&1 & goto :got_ffmpeg
    )
    echo [警告] 未找到 ffmpeg，安装包将不包含，需用户自行配置 PATH
    :got_ffmpeg
)
if not exist "build\bin\ffprobe.exe" (
    where ffprobe >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%i in ('where ffprobe') do copy "%%i" "build\bin\ffprobe.exe" >nul 2>&1
    )
)

REM 打包
if /i "%VARIANT%"=="both" (
    call :build_one cpu
    call :build_one gpu
) else (
    call :build_one %VARIANT%
)

echo.
echo ============================================================
echo 打包完成
echo ============================================================
endlocal
goto :eof

:build_one
set "V=%1"
if /i not "%V%"=="cpu" if /i not "%V%"=="gpu" (
    echo [错误] 变体必须是 cpu 或 gpu，当前: %V%
    exit /b 1
)

echo.
echo ============================================================
echo 构建 %V 版本
echo ============================================================

REM 安装对应依赖
echo [1/4] 安装依赖...
if /i "%V%"=="cpu" (
    pip install -r requirements_cpu.txt
) else (
    pip install -r requirements_gpu.txt
)
pip install pyinstaller

REM PyInstaller 打包
echo [2/4] PyInstaller 打包...
set "FACESWAP_VARIANT=%V%"
pyinstaller build\faceswap_app.spec --noconfirm --distpath dist --workpath build\work_%V%
if errorlevel 1 (
    echo [错误] PyInstaller 打包失败
    exit /b 1
)

REM 验证产物
set "OUT_DIR=dist\FaceswapApp_%V%"
if not exist "%OUT_DIR%\FaceswapApp_%V%.exe" (
    echo [错误] 未找到输出: %OUT_DIR%\FaceswapApp_%V%.exe
    exit /b 1
)

REM 复制 models（如存在）
echo [3/4] 复制模型文件...
if exist "..\models\insightface\inswapper_128.onnx" (
    mkdir "%OUT_DIR%\models\insightface" 2>nul
    copy "..\models\insightface\inswapper_128.onnx" "%OUT_DIR%\models\insightface\" >nul
    echo   已复制 inswapper_128.onnx
)
if exist "..\models\facerestore_models\GFPGANv1.4.pth" (
    mkdir "%OUT_DIR%\models\facerestore_models" 2>nul
    copy "..\models\facerestore_models\GFPGANv1.4.pth" "%OUT_DIR%\models\facerestore_models\" >nul
    echo   已复制 GFPGANv1.4.pth
)

REM 复制 ffmpeg
if exist "build\bin\ffmpeg.exe" (
    copy "build\bin\ffmpeg.exe" "%OUT_DIR%\" >nul
    copy "build\bin\ffprobe.exe" "%OUT_DIR%\" >nul
    echo   已复制 ffmpeg
)

REM Inno Setup 生成安装包
echo [4/4] 生成安装包...
if defined ISCC (
    if exist "%ISCC%" (
        "%ISCC%" /DVARIANT=%V% build\installer.iss
        echo   安装包: dist_installer\FaceswapApp_%V%_setup.exe
    ) else (
        echo   [跳过] Inno Setup 未安装
    )
) else (
    echo   [跳过] Inno Setup 未安装
)

echo %V 版本构建完成: %OUT_DIR%
goto :eof
