Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "  Starting Google Chrome with Remote Debugging Port 9222..." -ForegroundColor Green
Write-Host "===================================================================" -ForegroundColor Cyan

$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$profileDir = "d:\ai_projects\ComfyUI\flow_chrome_profile"
$proxy = "http://127.0.0.1:7897"
$url = "https://flow.google.com/"

Start-Process -FilePath $chromePath -ArgumentList @(
    "--remote-debugging-port=9222",
    "--user-data-dir=$profileDir",
    "--proxy-server=$proxy",
    $url
)

Write-Host "[OK] Chrome 浏览器窗口已在桌面弹出！" -ForegroundColor Yellow
Write-Host "请在弹出的 Chrome 窗口中完成一次 Google 账号登录。" -ForegroundColor White
Write-Host "登录完成后，在对话中回复【已登录】即可全自动接管生片！" -ForegroundColor Cyan
