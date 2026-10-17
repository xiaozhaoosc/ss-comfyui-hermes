@echo off
chcp 65001 >nul
title Character Generation Task Runner

set "COMFY_DIR=D:\ai_projects\ComfyUI"
set "PYTHON_EXE=%COMFY_DIR%\venv\Scripts\python.exe"

cd /d "%COMFY_DIR%"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python environment not found: %PYTHON_EXE%
    exit /b 1
)

echo [%DATE% %TIME%] Starting Hourly Character Generation Task...
"%PYTHON_EXE%" tools\hourly_character_task.py --count 1
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo [%DATE% %TIME%] Character generation completed successfully.
) else (
    echo [%DATE% %TIME%] Character generation failed with exit code: %EXIT_CODE%
)

exit /b %EXIT_CODE%
