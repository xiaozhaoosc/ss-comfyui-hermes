@echo off
setlocal
chcp 936 >nul

if "%HF_TOKEN%"=="" (
  echo [ERROR] HF_TOKEN is not set. Run: setx HF_TOKEN ^<your-token^>
  pause
  exit /b 1
)
if "%IDEOGRAM_API_KEY%"=="" (
  echo [ERROR] IDEOGRAM_API_KEY is not set. Run: setx IDEOGRAM_API_KEY ^<your-key^>
  pause
  exit /b 1
)

set "PY=D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe"
set "SCRIPT=D:\ai_projects\ComfyUI\ideogram4_run_local.py"
set "OUT=D:\ai_projects\ComfyUI\output\ideogram4_test.png"
set "LOG=D:\ai_projects\ComfyUI\ideogram4_test.log"

if not exist "D:\ai_projects\ComfyUI\output" mkdir "D:\ai_projects\ComfyUI\output"
if exist "%LOG%" del "%LOG%"

echo === Ideogram 4 Local Inference === > "%LOG%"
echo Loading model from local directory >> "%LOG%"
echo. >> "%LOG%"

"%PY%" "%SCRIPT%" >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"
echo === DONE === >> "%LOG%"
echo DONE
endlocal
