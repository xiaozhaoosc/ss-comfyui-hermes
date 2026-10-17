@echo off
title AIGC Automated Asset Generator Daemon

echo =====================================================================
echo   AIGC Automated Asset Generator Daemon (Anti-Rate-Limit Safe Mode)
echo   - Characters: :00, :30 (1 Asian female character asset)
echo   - Garments:   :15, :45 (1 Standalone garment asset)
echo   - Cooldown:   11-14 min silent rest between every generation run
echo   - Automatic Ingestion into Asset Hub (http://127.0.0.1:8090)
echo =====================================================================

set "PYTHON_EXE=D:\ai_projects\ComfyUI\venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment python not found at: %PYTHON_EXE%
    pause
    exit /b 1
)

echo Starting Hourly Generator Daemon...
"%PYTHON_EXE%" tools\hourly_scheduler.py
pause
