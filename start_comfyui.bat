@echo off
REM ==========================================
REM  ComfyUI Launch Script
REM  GPU: RTX 4060 Ti 16GB | RAM: 32GB
REM  All data on D: drive
REM ==========================================
setlocal

REM === 缓存/模型路径全放 D 盘 ===
set "HF_HOME=D:\OLLAMA_MODELS\cache\huggingface"
set "HUGGINGFACE_HUB_CACHE=D:\OLLAMA_MODELS\cache\huggingface\hub"
set "TORCH_HOME=D:\OLLAMA_MODELS\cache\torch"
set "TRANSFORMERS_CACHE=D:\OLLAMA_MODELS\cache\transformers"
set "XDG_CACHE_HOME=D:\OLLAMA_MODELS\cache"
set "PIP_CACHE_DIR=D:\OLLAMA_MODELS\cache\pip"

set "KMP_DUPLICATE_LIB_OK=TRUE"

REM === ComfyUI 配置（用脚本自身所在目录，双击/在任意目录调用都不会走错）===
set "COMFYUI_PATH=%~dp0"
if "%COMFYUI_PATH:~-1%"=="\" set "COMFYUI_PATH=%COMFYUI_PATH:~0,-1%"

REM === 固定用项目自带的 venv 解释器，不依赖 PATH 上的 python ===
REM     venv 与 anaconda 两个环境的依赖版本一致，都可用；此处显式指定是为了消除歧义。
set "PYTHON=%COMFYUI_PATH%\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo [错误] 找不到虚拟环境解释器:
    echo        %PYTHON%
    echo        请确认项目下的 venv 目录完整，或改用 start_comfyui_lowvram.bat。
    pause
    exit /b 1
)

REM === requirements.txt 缺失会让 get_required_packages_versions() 返回 None，
REM     /system_stats 随即 AttributeError（界面系统信息面板报错）===
if not exist "%COMFYUI_PATH%\requirements.txt" (
    echo [警告] 缺少 requirements.txt，界面会因 /system_stats 报错而异常。
    echo        恢复办法（项目根目录执行）：
    echo            git show v0.30.0:requirements.txt ^> requirements.txt
    echo.
)

cd /d "%COMFYUI_PATH%"

echo ========================================
echo   ComfyUI - RTX 4060 Ti 16GB
echo   Python: %PYTHON%
echo   Models: D:\OLLAMA_MODELS
echo   Cache:  D:\OLLAMA_MODELS\cache
echo   VRAM mode: LOWVRAM (H3 int8 optimized)
echo ========================================

"%PYTHON%" main.py ^
    --lowvram ^
    --listen 0.0.0.0 ^
    --port 8188

pause
