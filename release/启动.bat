@echo off
setlocal
cd /d "%~dp0"
if not exist "FloatingLyrics.exe" (
  echo Please extract the entire ZIP before running this file.
  pause
  exit /b 1
)
start "" "FloatingLyrics.exe" %*
if errorlevel 1 (
  echo The app could not start. Check that _internal is present.
  pause
  exit /b 1
)
