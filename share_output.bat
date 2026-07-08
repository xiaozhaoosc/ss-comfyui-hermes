@echo off
echo === ComfyUI Output SMB Share Setup ===
echo.

:: Create the share
net share ComfyUI-Output="D:\ai_projects\ComfyUI\output" /GRANT:Everyone,READ /REMARK:"ComfyUI generated images/videos"

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! Share created.
    echo Access from network: \\%COMPUTERNAME%\ComfyUI-Output
    echo.
    echo Current shares:
    net share
) else (
    echo.
    echo FAILED. Make sure you are running as Administrator.
)

pause
