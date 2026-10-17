# HuggingFace 登录脚本
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== HuggingFace 登录 ===" -ForegroundColor Cyan

if (-not $env:HF_TOKEN) {
    Write-Host "[ERROR] 请先设置 HF_TOKEN 环境变量（不要把 token 写进仓库）" -ForegroundColor Red
    Write-Host "        例如: setx HF_TOKEN <你的token>  然后重开终端" -ForegroundColor Yellow
    [Console]::ReadLine() | Out-Null
    exit 1
}
$Python = "D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe"

& $Python -c "from huggingface_hub import login; login(token='$Env:HF_TOKEN'); print('Login successful')" 2>&1 | Write-Host

Write-Host "按 Enter 键关闭..."
[Console]::ReadLine() | Out-Null
