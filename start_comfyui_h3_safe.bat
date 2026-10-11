@echo off
REM ComfyUI H3 one-click start - 4060Ti 16GB + 32GB RAM safe config
REM 2026-09-08: removed --disable-cuda-malloc (caused driver-level hang at 8:30 when H3 TE ~14.9GB force pre-load; no OOM traceback, system rebooted). Keep --lowvram for Sequential Offload.
setlocal
cd /d D:\ai_projects\ComfyUI
set TQDM_DISABLE=1
set PYTHONUNBUFFERED=1
REM H3 37GB weights rely on 32GB DDR5 RAM + pagefile for Sequential Offload.
REM Stable combo: --lowvram only (Sequential Offload). Do NOT add --disable-cuda-malloc (kills PyTorch allocator reuse -> driver VRAM pressure -> hang).
REM Do NOT run a second ComfyUI instance simultaneously (splits the 16GB VRAM and guarantees OOM).
"C:\Users\kenzhao\anaconda3\python.exe" -u main.py --lowvram --listen 0.0.0.0 --port 8188
endlocal