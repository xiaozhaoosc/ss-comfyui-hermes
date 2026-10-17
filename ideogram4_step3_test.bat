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
set "RUN=D:\ai_projects\ideogram4\run_inference.py"
set "OUT=D:\ai_projects\ComfyUI\output\ideogram4_test.png"
set "LOG=D:\ai_projects\ComfyUI\ideogram4_test.log"
set "HF_ENDPOINT=https://hf-mirror.com"

if not exist "D:\ai_projects\ComfyUI\output" mkdir "D:\ai_projects\ComfyUI\output"
if exist "%LOG%" del "%LOG%"

echo === Ideogram 4 Test Inference === > "%LOG%"
echo Using HF-Mirror endpoint >> "%LOG%"
echo First run downloads NF4 model about 6GB >> "%LOG%"

"%PY%" "%RUN%" --prompt "a ginger cat wearing a tiny wizard hat" --output "%OUT%" --quantization nf4 --magic-prompt-key "%IDEOGRAM_API_KEY%" >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"
echo === DONE === >> "%LOG%"
echo DONE
endlocal
