param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..\build\native'))
$ErrorActionPreference = 'Stop'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) { throw '需要 Visual Studio C++ 工具和 Windows SDK 来构建音频助手。打包版已附带此助手。' }
$installation = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $installation) { throw '未找到 Visual Studio C++ 工具。' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$output = (Resolve-Path -LiteralPath $OutputDirectory).Path
$source = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\native\process_energy.cpp')).Path
$developer = Join-Path $installation 'Common7\Tools\VsDevCmd.bat'
# These verified paths are compiler arguments. No file operation crosses shells.
$command = 'call "{0}" -arch=x64 >nul && cl /nologo /std:c++17 /EHsc /O2 /MT /utf-8 "{1}" /Fo"{2}\ProcessEnergy.obj" /Fe"{2}\ProcessEnergy.exe" /link ole32.lib mmdevapi.lib' -f $developer,$source,$output
& $env:ComSpec /d /c $command
if ($LASTEXITCODE -ne 0) { throw '音频助手构建失败。' }
