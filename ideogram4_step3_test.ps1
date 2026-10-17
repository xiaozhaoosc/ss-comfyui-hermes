# Ideogram 4 测试推理脚本
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not $env:HF_TOKEN) {
    Write-Host "[ERROR] 请先设置 HF_TOKEN 环境变量" -ForegroundColor Red
    [Console]::ReadLine() | Out-Null
    exit 1
}
if (-not $env:IDEOGRAM_API_KEY) {
    Write-Host "[ERROR] 请先设置 IDEOGRAM_API_KEY 环境变量" -ForegroundColor Red
    [Console]::ReadLine() | Out-Null
    exit 1
}
$Python = "D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe"
$RunScript = "D:\ai_projects\ideogram4\run_inference.py"
$OutputDir = "D:\ai_projects\ComfyUI\output"

if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }

Write-Host "=== Ideogram 4 测试推理 ===" -ForegroundColor Cyan
Write-Host "首次运行将下载模型约6GB，请耐心等待..." -ForegroundColor Yellow

& $Python $RunScript `
  --prompt "a ginger cat wearing a tiny wizard hat" `
  --output "$OutputDir\ideogram4_test.png" `
  --quantization nf4 `
  --magic-prompt-key "$Env:IDEOGRAM_API_KEY" 2>&1 | Write-Host

Write-Host "按 Enter 键关闭..."
[Console]::ReadLine() | Out-Null
