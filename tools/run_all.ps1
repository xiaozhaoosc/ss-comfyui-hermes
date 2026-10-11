# ============================================================
# 换脸全流程脚本 — 一键执行
# 用法: 在 PowerShell 中运行此脚本即可
#   powershell -ExecutionPolicy Bypass -File "D:\ai_projects\ComfyUI\tools\run_all.ps1"
# ============================================================

$ErrorActionPreference = "Stop"

# ========== 环境变量 ==========
$env:HF_HOME = "D:\OLLAMA_MODELS\cache\huggingface"
$env:HUGGINGFACE_HUB_CACHE = "D:\OLLAMA_MODELS\cache\huggingface\hub"
$env:TORCH_HOME = "D:\OLLAMA_MODELS\cache\torch"
$env:TRANSFORMERS_CACHE = "D:\OLLAMA_MODELS\cache\transformers"
$env:XDG_CACHE_HOME = "D:\OLLAMA_MODELS\cache"
$env:PIP_CACHE_DIR = "D:\OLLAMA_MODELS\cache\pip"
$env:KMP_DUPLICATE_LIB_OK = "TRUE"

$ComfyRoot = "D:\ai_projects\ComfyUI"
$Python = "$ComfyRoot\venv\Scripts\python.exe"
$Port = 8188
$MaxWaitSec = 300
$CheckInterval = 3

# ========== Step 1-2: 检查 / 启动 ComfyUI ==========
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Step 1: 检查 ComfyUI 状态" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$comfyRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/system_stats" -TimeoutSec 3 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        $comfyRunning = $true
        Write-Host "[OK] ComfyUI 已在运行 (端口 $Port)" -ForegroundColor Green
    }
} catch {
    Write-Host "ComfyUI 未运行，正在启动..." -ForegroundColor Yellow
}

if (-not $comfyRunning) {
    $comfy = Start-Process -FilePath $Python `
        -ArgumentList "main.py", "--highvram", "--enable-manager", "--listen", "0.0.0.0", "--port", "$Port" `
        -WorkingDirectory $ComfyRoot `
        -PassThru -NoNewWindow

    Write-Host "ComfyUI PID: $($comfy.Id)" -ForegroundColor Green

    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Step 2: 等待 ComfyUI 就绪" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    $waited = 0
    $ready = $false
    while ($waited -lt $MaxWaitSec) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/system_stats" -TimeoutSec 3 -UseBasicParsing
            if ($resp.StatusCode -eq 200) {
                Write-Host "[OK] ComfyUI 已就绪！(耗时 ${waited}s)" -ForegroundColor Green
                $ready = $true
                break
            }
        } catch {
            Write-Host "[${waited}s] 等待中..." -ForegroundColor Gray
        }
        Start-Sleep -Seconds $CheckInterval
        $waited += $CheckInterval
    }

    if (-not $ready) {
        Write-Host "[FAIL] ComfyUI 启动超时 (${MaxWaitSec}s)" -ForegroundColor Red
        exit 1
    }
}

# ========== Step 3: 执行换脸 ==========
$script = "$ComfyRoot\tools\batch_faceswap_overlay.py"
$videoDir = "$ComfyRoot\input\美羊羊滴视频号"
$faceImg = "$ComfyRoot\input\ken4\face\ken-14岁.png"
$outputBase = "$ComfyRoot\output\美羊羊_ken_overlay"

# Step 3a: 换脸
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Step 3a: 执行换脸 (--no-music)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
& $Python $script --input $videoDir --face $faceImg --output $outputBase --no-music
if ($LASTEXITCODE -ne 0) { throw "换脸失败 (exit=$LASTEXITCODE)" }
Write-Host "[OK] 换脸完成 → $outputBase" -ForegroundColor Green

# Step 3b: v1 原版BGM
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Step 3b: 生成 v1 原版BGM" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
$outV1 = "${outputBase}_v1_原版BGM"
& $Python $script --skip-faceswap --input $outputBase --output $outV1 --original-dir $videoDir --no-music
if ($LASTEXITCODE -ne 0) { throw "v1 失败 (exit=$LASTEXITCODE)" }
Write-Host "[OK] v1 完成 → $outV1" -ForegroundColor Green

# Step 3c: v2 原创BGM
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Step 3c: 生成 v2 原创BGM" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
$outV2 = "${outputBase}_v2_原创BGM"
$bgmOriginal = "$ComfyRoot\input\ken4\face\bgm原创\Afternoon_in_Amber.mp3"
& $Python $script --skip-faceswap --input $outputBase --output $outV2 --original-dir $videoDir --bg-music $bgmOriginal --bg-volume 0.75
if ($LASTEXITCODE -ne 0) { throw "v2 失败 (exit=$LASTEXITCODE)" }
Write-Host "[OK] v2 完成 → $outV2" -ForegroundColor Green

# Step 3d: v3 BGM目录
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Step 3d: 生成 v3 BGM目录" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
$outV3 = "${outputBase}_v3_BGM目录"
$bgmDir = "$ComfyRoot\input\ken4\face\bgm\歌名---前奏一响就心动，这首很适合做铃声啊！#音乐分享 #微信铃声 #甜歌 #夏天.m4a"
& $Python $script --skip-faceswap --input $outputBase --output $outV3 --original-dir $videoDir --bg-music $bgmDir --bg-volume 0.75
if ($LASTEXITCODE -ne 0) { throw "v3 失败 (exit=$LASTEXITCODE)" }
Write-Host "[OK] v3 完成 → $outV3" -ForegroundColor Green

# ========== 完成 ==========
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  全部完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "v1 (原版BGM): $outV1"
Write-Host "v2 (原创BGM): $outV2"
Write-Host "v3 (BGM目录): $outV3"