@echo off
setlocal enabledelayedexpansion

set PIP=D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\pip.exe
set PY=D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe
set LOG=D:\ai_projects\ComfyUI\install_ideogram4.log

echo ===== Step 1: upgrade pip/setuptools/wheel ===== > "%LOG%"
"%PIP%" install --upgrade pip setuptools wheel >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"

echo ===== Step 2: install regex ===== >> "%LOG%"
"%PIP%" install regex >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"

echo ===== Step 3: install core deps ===== >> "%LOG%"
"%PIP%" install transformers accelerate safetensors einops sentencepiece pillow huggingface-hub requests bitsandbytes >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"

echo ===== Step 4: install ideogram4 (no-deps) ===== >> "%LOG%"
"%PIP%" install -e D:\ai_projects\ideogram4 --no-deps >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"

echo ===== Verify ===== >> "%LOG%"
"%PY%" -c "import ideogram4; print('ideogram4 OK'); import torch; print('torch:', torch.__version__, 'cuda:', torch.cuda.is_available()); import transformers; print('transformers:', transformers.__version__)" >> "%LOG%" 2>&1
echo [EXIT_CODE] %ERRORLEVEL% >> "%LOG%"

echo ===== DONE ===== >> "%LOG%"
echo DONE
endlocal
