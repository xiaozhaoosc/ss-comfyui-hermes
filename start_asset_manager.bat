@echo off
title AIGC Local Asset Hub

echo =====================================================================
echo   AIGC Local Asset Hub
echo   Zero-VRAM Architecture (Pure CPU Math + ComfyUI 8188 Delegation)
echo =====================================================================

set "PYTHON_EXE=D:\ai_projects\ComfyUI\venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment python not found at: %PYTHON_EXE%
    pause
    exit /b 1
)

echo Starting Asset Hub on http://127.0.0.1:8090 ...
"%PYTHON_EXE%" tools\asset_manager\run.py --port 8090
pause
