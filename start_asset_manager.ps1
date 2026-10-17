# AIGC Local Asset Hub Launcher for PowerShell
$PythonExe = "D:\ai_projects\ComfyUI\venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Virtual environment python not found at: $PythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  AIGC Local Asset Hub" -ForegroundColor Cyan
Write-Host "  Starting on http://127.0.0.1:8090 ..." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

& $PythonExe tools\asset_manager\run.py --port 8090
