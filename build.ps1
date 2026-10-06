$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Run start.ps1 first to create the environment.' }
Push-Location -LiteralPath $taskRoot
try {
    & $taskPython -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    & $taskPython tools\make_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Demo generation failed.' }
    & $taskPython tools\make_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
    & $taskPython -m PyInstaller --noconfirm --windowed --onedir --name FloatingLyrics --icon assets\app.ico --add-data 'assets;assets' main.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    Write-Output 'Ready: dist\FloatingLyrics\FloatingLyrics.exe'
} finally {
    Pop-Location
}
