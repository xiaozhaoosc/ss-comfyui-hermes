@echo off
chcp 65001 >nul 2>&1
REM ==========================================
REM  美羊羊换脸 + 3版本BGM 一键执行脚本
REM  使用 batch_faceswap_overlay.py
REM ==========================================

set COMFY_ROOT=D:\ai_projects\ComfyUI
set PYTHON=%COMFY_ROOT%\venv\Scripts\python.exe
set SCRIPT=%COMFY_ROOT%\tools\batch_faceswap_overlay.py

set VIDEO_DIR=%COMFY_ROOT%\input\美羊羊滴视频号
set FACE_IMG=%COMFY_ROOT%\input\ken4\face\ken-14岁.png
set OUTPUT_BASE=%COMFY_ROOT%\output\美羊羊_ken_overlay

REM BGM 文件
set BGM_ORIGINAL=输入\ken4\face\bgm原创\Afternoon_in_Amber.mp3
set BGM_DIR=输入\ken4\face\bgm\歌名---前奏一响就心动，这首很适合做铃声啊！#音乐分享 #微信铃声 #甜歌 #夏天.m4a

REM 换脸结果目录（ComfyUI 直接输出到这里）
set FACESWAP_RESULT=%OUTPUT_BASE%

REM 3个BGM版本的输出目录
set OUT_V1=%OUTPUT_BASE%_v1_原版BGM
set OUT_V2=%OUTPUT_BASE%_v2_原创BGM
set OUT_V3=%OUTPUT_BASE%_v3_BGM目录

echo ========================================
echo   美羊羊换脸 + 3版本BGM 一键工具
echo ========================================
echo   视频目录: %VIDEO_DIR%
echo   人脸图片: %FACE_IMG%
echo   输出基目录: %OUTPUT_BASE%
echo ========================================
echo.

REM ===== Step 0: 检查 ComfyUI 是否运行 =====
echo [Step 0] 检查 ComfyUI 是否运行...
%PYTHON% -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8188/system_stats', timeout=3); print('ComfyUI RUNNING')"
if errorlevel 1 (
    echo.
    echo ❌ ComfyUI 未运行！请先启动 ComfyUI:
    echo    双击 start_comfyui.bat 或在终端运行:
    echo    cd /d %COMFY_ROOT% ^&^& start_comfyui.bat
    echo.
    echo 启动后等待 ComfyUI 完全加载（看到 "To see the GUI..." 提示）
    echo 然后重新运行此脚本。
    echo.
    pause
    exit /b 1
)
echo ✅ ComfyUI 运行中
echo.

REM ===== Step 1: 换脸（ComfyUI API）=====
echo [Step 1/4] 提交换脸任务到 ComfyUI...
echo   人脸: ken-14岁.png
echo   输出: %FACESWAP_RESULT%
echo.

%PYTHON% %SCRIPT% ^
    --input "%VIDEO_DIR%" ^
    --face "%FACE_IMG%" ^
    --output "%FACESWAP_RESULT%" ^
    --no-music

if errorlevel 1 (
    echo.
    echo ❌ 换脸步骤失败！请检查 ComfyUI 日志。
    pause
    exit /b 1
)

echo.
echo ✅ 换脸完成，结果在: %FACESWAP_RESULT%
echo.

REM ===== Step 2: 生成 v1 原版BGM版本 =====
echo [Step 2/4] 生成 v1 原版BGM版本（仅原声，无BGM）...
echo   输出: %OUT_V1%
echo.

%PYTHON% %SCRIPT% ^
    --skip-faceswap ^
    --input "%FACESWAP_RESULT%" ^
    --output "%OUT_V1%" ^
    --original-dir "%VIDEO_DIR%" ^
    --no-music

echo.

REM ===== Step 3: 生成 v2 原创BGM版本 =====
echo [Step 3/4] 生成 v2 原创BGM版本...
echo   BGM: Afternoon_in_Amber.mp3
echo   输出: %OUT_V2%
echo.

%PYTHON% %SCRIPT% ^
    --skip-faceswap ^
    --input "%FACESWAP_RESULT%" ^
    --output "%OUT_V2%" ^
    --original-dir "%VIDEO_DIR%" ^
    --bg-music "%COMFY_ROOT%\%BGM_ORIGINAL%" ^
    --bg-volume 0.75

echo.

REM ===== Step 4: 生成 v3 BGM目录版本 =====
echo [Step 4/4] 生成 v3 BGM目录版本...
echo   BGM: 前奏一响就心动.m4a
echo   输出: %OUT_V3%
echo.

%PYTHON% %SCRIPT% ^
    --skip-faceswap ^
    --input "%FACESWAP_RESULT%" ^
    --output "%OUT_V3%" ^
    --original-dir "%VIDEO_DIR%" ^
    --bg-music "%COMFY_ROOT%\%BGM_DIR%" ^
    --bg-volume 0.75

echo.
echo ========================================
echo   全部完成！
echo ========================================
echo   换脸结果: %FACESWAP_RESULT%
echo   v1 原版BGM: %OUT_V1%
echo   v2 原创BGM: %OUT_V2%
echo   v3 BGM目录: %OUT_V3%
echo ========================================
echo.
pause
