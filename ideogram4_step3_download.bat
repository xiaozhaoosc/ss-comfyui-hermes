@echo off
setlocal
chcp 936 >nul

set "PY=D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe"
set "SCRIPT=D:\ai_projects\ComfyUI\ideogram4_download_model.py"
set "LOG=D:\ai_projects\ComfyUI\ideogram4_download.log"

if exist "%LOG%" del "%LOG%"

echo === Ideogram 4 NF4 Model Download === > "%LOG%"
echo Using hf-mirror.com >> "%LOG%"
echo. >> "%LOG%"

"%PY%" "%SCRIPT%" >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"
echo === DONE === >> "%LOG%"
echo DONE
endlocal
