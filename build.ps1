param([switch]$SkipDependencies)
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Run start.ps1 first to create the environment.' }
Push-Location -LiteralPath $taskRoot
try {
    if (-not $SkipDependencies) {
        & $taskPython -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    }
    & $taskPython tools\make_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Demo generation failed.' }
    & $taskPython tools\make_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
    & (Join-Path $taskRoot 'tools\build_energy.ps1')
    $staging = Join-Path $taskRoot ('artifacts\package-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    $assets = Join-Path $taskRoot 'assets'
    $energy = Join-Path $taskRoot 'build\native\ProcessEnergy.exe'
    & $taskPython -m PyInstaller --noconfirm --windowed --onedir --name FloatingLyrics --icon (Join-Path $assets 'app.ico') --add-data "$assets;assets" --add-binary "$energy;native" --distpath $staging --workpath (Join-Path $taskRoot 'build\pyinstaller') --specpath (Join-Path $taskRoot 'build\spec') (Join-Path $taskRoot 'main.py')
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    $target = Join-Path $taskRoot 'dist\FloatingLyrics'
    $ready = Join-Path $staging 'FloatingLyrics'
    # Preserve settings in the completed staging copy before replacing the old package.
    if (Test-Path -LiteralPath (Join-Path $target '.state')) {
        Copy-Item -LiteralPath (Join-Path $target '.state') -Destination $ready -Recurse
    }
    $backup = Join-Path $taskRoot ('artifacts\previous-package-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    foreach ($path in @($target,$ready,$backup)) {
        if (-not [IO.Path]::GetFullPath($path).StartsWith($taskRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw '构建目录超出项目边界。' }
    }
    if (Test-Path -LiteralPath $target) { Move-Item -LiteralPath $target -Destination $backup }
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Move-Item -LiteralPath $ready -Destination $target
    } catch {
        if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $target)) { Move-Item -LiteralPath $backup -Destination $target }
        throw
    }
    Write-Output 'Ready: dist\FloatingLyrics\FloatingLyrics.exe'
} finally {
    Pop-Location
}
