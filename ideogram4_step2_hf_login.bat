@echo off
setlocal
chcp 936 >nul

if "%HF_TOKEN%"=="" (
  echo [ERROR] HF_TOKEN is not set. Run: setx HF_TOKEN ^<your-token^>
  pause
  exit /b 1
)

set PY=D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe
set LOG=D:\ai_projects\ComfyUI\ideogram4_hf_login.log

if exist "%LOG%" del "%LOG%"

echo === HuggingFace Login === > "%LOG%"
"%PY%" -c "from huggingface_hub import login; login(token='%HF_TOKEN%'); print('Login successful')" >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"

echo === DONE === >> "%LOG%"
echo DONE
endlocal
