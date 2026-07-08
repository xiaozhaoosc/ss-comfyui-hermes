# PowerShell Wrapper to run the robust Python downloader script
$ScriptPath = Join-Path $PSScriptRoot "download_models.py"
if (Test-Path $ScriptPath) {
    python -u $ScriptPath
} else {
    Write-Error "Error: download_models.py not found at $ScriptPath"
}
