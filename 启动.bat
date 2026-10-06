@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 (
    echo.
    echo Startup failed. The error above can help diagnose the issue.
    pause
    exit /b 1
)
exit /b 0
