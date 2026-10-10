@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" -QQMusic %*
if errorlevel 1 (
    echo QQ Music companion failed to start. Check the message above.
    pause
    exit /b 1
)
