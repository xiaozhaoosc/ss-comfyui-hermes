# ============================================================
# RunCommand 故障诊断脚本
# 在独立 PowerShell 窗口中执行: powershell -File diagnose_runcommand.ps1
# ============================================================

Write-Host "`n========== 环境变量诊断 ==========" -ForegroundColor Cyan

# 1. PATH 长度
$pathLen = $env:PATH.Length
Write-Host "`n[1] PATH 环境变量长度: $pathLen 字符" -ForegroundColor Yellow
Write-Host "    (Windows 单变量上限约 32767，TRAE RunCommand 限制 32000)"

if ($pathLen -gt 30000) {
    Write-Host "    !!! PATH 过长，这是 RunCommand 失败的可能原因 !!!" -ForegroundColor Red
} elseif ($pathLen -gt 20000) {
    Write-Host "    !! PATH 较长，可能接近限制 !!" -ForegroundColor DarkYellow
} else {
    Write-Host "    OK" -ForegroundColor Green
}

# 2. 所有环境变量总长度
$totalLen = 0
$envVars | ForEach-Object {
    $totalLen += $_.Value.Length + $_.Key.Length + 2  # key=value;
}
Write-Host "`n[2] 所有环境变量总长度: $totalLen 字符" -ForegroundColor Yellow
Write-Host "    (TRAE RunCommand 编码后上限约 32000)"

if ($totalLen -gt 30000) {
    Write-Host "    !!! 环境变量总长度过大，这是 RunCommand 失败的根因 !!!" -ForegroundColor Red
}

# 3. 列出最大的前 10 个环境变量
Write-Host "`n[3] 最大的环境变量 (前 10):" -ForegroundColor Yellow
$envVars | Sort-Object { $_.Value.Length } -Descending | Select-Object -First 10 | ForEach-Object {
    $truncVal = if ($_.Value.Length -gt 80) { $_.Value.Substring(0, 80) + "..." } else { $_.Value }
    Write-Host ("    {0,-30} [{1,6} 字符]  {2}" -f $_.Key, $_.Value.Length, $truncVal)
}

# 4. PATH 条目统计
Write-Host "`n[4] PATH 条目统计:" -ForegroundColor Yellow
$pathEntries = $env:PATH -split ';'
Write-Host "    条目数: $($pathEntries.Count)"
Write-Host "    最长条目:"
$pathEntries | Where-Object { $_.Length -gt 0 } | Sort-Object Length -Descending | Select-Object -First 5 | ForEach-Object {
    Write-Host ("      [{0,4} 字符] {1}" -f $_.Length, $_)
}

# 5. 验证 nvidia-smi 是否可用
Write-Host "`n[5] nvidia-smi 可用性:" -ForegroundColor Yellow
$nvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidia) {
    Write-Host "    路径: $($nvidia.Source)" -ForegroundColor Green
    & nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv
} else {
    Write-Host "    未找到 nvidia-smi" -ForegroundColor Red
}

# 6. 验证 python 是否可用
Write-Host "`n[6] Python 可用性:" -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    Write-Host "    路径: $($python.Source)" -ForegroundColor Green
    & python --version
} else {
    Write-Host "    未找到 python" -ForegroundColor Red
}

# 7. 结论与建议
Write-Host "`n========== 诊断结论 ==========" -ForegroundColor Cyan
if ($totalLen -gt 30000) {
    Write-Host @"

根因确认: 环境变量总长度 ($totalLen 字符) 超过 TRAE RunCommand 的 32000 字符编码限制。

恢复方案:
  1. 清理 PATH 中重复/无效的条目 (见下方脚本)
  2. 或清理其他过大的环境变量
  3. 重启 TRAE IDE

备份当前 PATH:
  $env:PATH | Out-File -FilePath "$PWD\path_backup.txt" -Encoding utf8

清理 PATH (移除空条目和重复条目，不修改系统):
  $cleanPath = ($env:PATH -split ';' | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique) -join ';'
  Write-Host "清理后 PATH 长度: $($cleanPath.Length) 字符"

要永久修改系统 PATH，请用"系统属性 > 环境变量"GUI 编辑。
"@ -ForegroundColor Yellow
} else {
    Write-Host "`n环境变量总长度 ($totalLen) 未超过 32000，问题可能在其他地方。" -ForegroundColor Yellow
    Write-Host "建议: 重启 TRAE IDE，或检查 TRAE 版本是否有已知 bug。"
}

Write-Host "`n按任意键退出..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
