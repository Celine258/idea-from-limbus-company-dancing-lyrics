@echo off
setlocal
cd /d "%~dp0"
if not exist "FloatingLyrics.exe" (
  echo Please extract the entire ZIP before running this file.
  pause
  exit /b 1
)
if not exist "_internal\native\qqmusic_smtc.ps1" (
  echo QQ Music support is missing. Please download and extract the new complete ZIP.
  pause
  exit /b 1
)
start "" "FloatingLyrics.exe" --qqmusic %*
