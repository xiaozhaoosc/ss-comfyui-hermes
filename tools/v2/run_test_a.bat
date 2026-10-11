@echo off
REM ============================================================
REM GPU 利用率测试 - 方案 A：跳过换脸，专注 IDM-VTON 换装
REM ============================================================
chcp 65001 >nul
cd /d D:\ai_projects\ComfyUI

if not exist output mkdir output

echo ============================================================
echo  开始测试: IDM-VTON 换装 GPU 利用率
echo  时间: %date% %time%
echo ============================================================

python tools\v2\run_pipeline_with_gpu_monitor.py ^
  --mode image ^
  --skip-faceswap ^
  --input "input\pics\idm_vton_human.jpg" ^
  --garment "input\pics\idm_vton_garment.jpg" ^
  --output "output\gpu_test_tryon.png" ^
  --garment-desc "a white t-shirt" ^
  --steps 20

echo.
echo ============================================================
echo  测试结束: %date% %time%
echo  结果报告: output\gpu_test_tryon.png_gpu_report.json
echo ============================================================
pause
