<#
.SYNOPSIS
    一键在 Windows 任务计划程序中注册两项定时自动化任务
    - ComfyUI_Hourly_Character_Task: 每小时 :00, :30 执行角色生成
    - ComfyUI_Hourly_Garment_Task:   每小时 :15, :45 执行服装生成
.NOTES
    请以普通用户或管理员身份在 PowerShell 中运行本脚本。
#>

$ComfyRoot = "D:\ai_projects\ComfyUI"
$CharScript = "$ComfyRoot\docs\automations_migration\scripts\run_character_task.bat"
$GarmentScript = "$ComfyRoot\docs\automations_migration\scripts\run_garment_task.bat"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 正在配置 Windows 任务计划程序 (Windows Task Scheduler)..." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. 注册角色生成任务 (:00, :30)
$CharAction = New-ScheduledTaskAction -Execute "$CharScript" -WorkingDirectory "$ComfyRoot"
$CharTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 30)
$CharSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

try {
    Unregister-ScheduledTask -TaskName "ComfyUI_Hourly_Character_Task" -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName "ComfyUI_Hourly_Character_Task" -Action $CharAction -Trigger $CharTrigger -Settings $CharSettings -Description "ComfyUI 每 30 分钟生成 1 位亚洲女性角色资产 (9视角独立高清大图)"
    Write-Host "[✓] 成功注册计划任务: ComfyUI_Hourly_Character_Task (每30分钟)" -ForegroundColor Green
} catch {
    Write-Host "[!] 注册角色任务失败: $_" -ForegroundColor Red
}

# 2. 注册服装生成任务 (:15, :45 偏移 15 分钟启动)
$StartTimeGarment = (Get-Date).Date.AddMinutes(15)
$GarmentAction = New-ScheduledTaskAction -Execute "$GarmentScript" -WorkingDirectory "$ComfyRoot"
$GarmentTrigger = New-ScheduledTaskTrigger -Once -At $StartTimeGarment -RepetitionInterval (New-TimeSpan -Minutes 30)
$GarmentSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

try {
    Unregister-ScheduledTask -TaskName "ComfyUI_Hourly_Garment_Task" -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName "ComfyUI_Hourly_Garment_Task" -Action $GarmentAction -Trigger $GarmentTrigger -Settings $GarmentSettings -Description "ComfyUI 每 30 分钟生成 1 款独立服装资产并去底入库"
    Write-Host "[✓] 成功注册计划任务: ComfyUI_Hourly_Garment_Task (每30分钟，错峰15分钟)" -ForegroundColor Green
} catch {
    Write-Host "[!] 注册服装任务失败: $_" -ForegroundColor Red
}

Write-Host "`n所有计划任务配置完成！可在 Windows '任务计划程序' (taskschd.msc) 中查看或手动测试运行。" -ForegroundColor Yellow
