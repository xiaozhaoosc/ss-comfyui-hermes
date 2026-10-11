@echo off
chcp 65001 >nul
echo ========================================================
echo        OOTD 卡点换装全自动工业化流水线启动器
echo ========================================================
echo.

set PYTHON_EXE=D:\ai_projects\ComfyUI\venv\Scripts\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo [1/2] 检查 ComfyUI 服务...
echo [2/2] 启动流水线脚本...
echo.

"%PYTHON_EXE%" D:\ai_projects\ComfyUI\tools\ootd_study\run_ootd_pipeline.py %*

echo.
echo ========================================================
echo                      执行结束
echo ========================================================
pause
