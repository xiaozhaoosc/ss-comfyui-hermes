@echo off
chcp 65001 >nul
title ComfyUI Agent HTTP Webhook Bridge (Port 8095)

set "COMFY_DIR=D:\ai_projects\ComfyUI"
set "PYTHON_EXE=%COMFY_DIR%\venv\Scripts\python.exe"

cd /d "%COMFY_DIR%"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found: %PYTHON_EXE%
    pause
    exit /b 1
)

echo Starting ComfyUI Agent HTTP Bridge on port 8095...
"%PYTHON_EXE%" docs\automations_migration\scripts\agent_api_bridge.py
pause
