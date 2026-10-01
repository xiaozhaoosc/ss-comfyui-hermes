$ErrorActionPreference = "Continue"
$logFile = "D:\ai_projects\ComfyUI\install_ideogram4.log"
"" | Out-File -FilePath $logFile -Encoding UTF8

function Run-Step {
    param(
        [string]$StepName,
        [scriptblock]$Action
    )
    Write-Host "===== $StepName =====" -ForegroundColor Cyan
    "===== $StepName =====" | Out-File -FilePath $logFile -Append -Encoding UTF8
    try {
        & $Action 2>&1 | Tee-Object -FilePath $logFile -Append
        $code = $LASTEXITCODE
        Write-Host "[EXIT_CODE] $code" -ForegroundColor Yellow
        "[EXIT_CODE] $code" | Out-File -FilePath $logFile -Append -Encoding UTF8
        return $code
    } catch {
        Write-Host "[ERROR] $_" -ForegroundColor Red
        "[ERROR] $_" | Out-File -FilePath $logFile -Append -Encoding UTF8
        return -1
    }
}

$pip = "D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\pip.exe"
$py = "D:\ai_projects\ComfyUI\ideogram4_venv\Scripts\python.exe"

# Step 1
Run-Step "Step 1: upgrade pip/setuptools/wheel" { & $pip install --upgrade pip setuptools wheel } | Out-Null

# Step 2
Run-Step "Step 2: install regex" { & $pip install regex } | Out-Null

# Step 3
Run-Step "Step 3: install core deps" { & $pip install transformers accelerate safetensors einops sentencepiece pillow huggingface-hub requests bitsandbytes } | Out-Null

# Step 4
Run-Step "Step 4: install ideogram4 (no-deps)" { & $pip install -e D:\ai_projects\ideogram4 --no-deps } | Out-Null

# Verify
Run-Step "Verify" { & $py -c "import ideogram4; print('ideogram4 OK'); import torch; print('torch:', torch.__version__, 'cuda:', torch.cuda.is_available()); import transformers; print('transformers:', transformers.__version__)" } | Out-Null

Write-Host "===== DONE =====" -ForegroundColor Green
