# PowerShell Wrapper to run the robust Python downloader for Krea-2 / Qwen3-VL models
$ScriptPath = Join-Path $PSScriptRoot "download_krea_models.py"
if (Test-Path $ScriptPath) {
    python -u $ScriptPath
} else {
    Write-Error "Error: download_krea_models.py not found at $ScriptPath"
}
