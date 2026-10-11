@echo off
echo ===================================================================
echo   Starting Google Chrome with Remote Debugging Port 9222
echo ===================================================================
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="d:\ai_projects\ComfyUI\flow_chrome_profile" --proxy-server="http://127.0.0.1:7897" "https://flow.google.com/"
echo.
echo [OK] Chrome window has been launched!
echo Please sign in with your Google account in the Chrome window.
echo Once logged in, return to the chat and say: logged in
echo.
pause
