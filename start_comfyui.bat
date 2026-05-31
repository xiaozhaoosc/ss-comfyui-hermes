@echo off
REM ==========================================
REM  ComfyUI Launch Script
REM  GPU: RTX 4060 Ti 16GB | RAM: 32GB
REM  All data on D: drive
REM ==========================================

REM === 缓存/模型路径全放 D 盘 ===
set HF_HOME=D:\OLLAMA_MODELS\cache\huggingface
set HUGGINGFACE_HUB_CACHE=D:\OLLAMA_MODELS\cache\huggingface\hub
set TORCH_HOME=D:\OLLAMA_MODELS\cache\torch
set TRANSFORMERS_CACHE=D:\OLLAMA_MODELS\cache\transformers
set XDG_CACHE_HOME=D:\OLLAMA_MODELS\cache
set PIP_CACHE_DIR=D:\OLLAMA_MODELS\cache\pip

REM === ComfyUI 配置 ===
set COMFYUI_PATH=D:\ai_projects\ComfyUI

REM === 启动 ComfyUI ===
cd /d %COMFYUI_PATH%

echo ========================================
echo   ComfyUI - RTX 4060 Ti 16GB
echo   Models: D:\OLLAMA_MODELS
echo   Cache:  D:\OLLAMA_MODELS\cache
echo ========================================

venv\Scripts\python.exe main.py ^
    --highvram ^
    --listen 0.0.0.0 ^
    --port 8188

pause
