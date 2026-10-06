param(
    [string]$ClientDirectory = 'C:\Program Files\NetEase\CloudMusic',
    [string]$ProfileDirectory = 'C:\betterncm',
    [string]$FrameworkDll = (Join-Path $PSScriptRoot '..\artifacts\netease-probe\BetterNCMII-1.3.4.dll')
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$exe = Join-Path $ClientDirectory 'cloudmusic.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "未找到网易云客户端：$exe" }
$version = (Get-Item -LiteralPath $exe).VersionInfo.FileVersion
if ($version -ne '3.1.41.205529') { throw "当前仅验证网易云 3.1.41.205529，检测到 $version；未改动客户端。" }
if (@(Get-Process -Name cloudmusic -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }).Count) {
    throw '请先完全退出网易云，再运行安装脚本。安装不会结束你的音乐进程。'
}
$expected = 'A7C77AF418D7940E63FAA58EA036FBA1F4BAAD497947109EA52ED78C8E86608F'
if (-not (Test-Path -LiteralPath $FrameworkDll)) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $FrameworkDll) -Force | Out-Null
    Invoke-WebRequest -Uri 'https://github.com/std-microblock/chromatic/releases/download/1.3.4/BetterNCMII.dll' -OutFile $FrameworkDll -TimeoutSec 60
}
if ((Get-FileHash -LiteralPath $FrameworkDll -Algorithm SHA256).Hash -ne $expected) { throw 'BetterNCM 下载文件校验失败；未安装。' }
$destination = Join-Path $ClientDirectory 'msimg32.dll'
$hadFramework = Test-Path -LiteralPath $destination
if ($hadFramework -and (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $expected) {
    throw '客户端已有不同的 msimg32.dll，请先确认已有插件框架；安装未覆盖该文件。'
}
$plugin = Join-Path $root 'artifacts\netease-plugin\FloatingLyrics.plugin'
$python = Join-Path $root '.venv\Scripts\python.exe'
& $python (Join-Path $PSScriptRoot 'package_netease.py')
if ($LASTEXITCODE -ne 0) { throw '生成联动插件失败。' }
$pluginsDir = Join-Path $ProfileDirectory 'plugins'
New-Item -ItemType Directory -Path $pluginsDir -Force | Out-Null
$targetPlugin = Join-Path $pluginsDir 'FloatingLyrics.plugin'
$backup = Join-Path $root ('artifacts\netease-install-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$hadPlugin = Test-Path -LiteralPath $targetPlugin
if ($hadPlugin) { Copy-Item -LiteralPath $targetPlugin -Destination (Join-Path $backup 'FloatingLyrics.plugin') }
try {
    if (-not $hadFramework) { Copy-Item -LiteralPath $FrameworkDll -Destination $destination }
    Copy-Item -LiteralPath $plugin -Destination $targetPlugin
} catch {
    if (-not $hadFramework -and (Test-Path -LiteralPath $destination) -and
        (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -eq $expected) { Remove-Item -LiteralPath $destination }
    if ($hadPlugin) { Copy-Item -LiteralPath (Join-Path $backup 'FloatingLyrics.plugin') -Destination $targetPlugin }
    throw
}
@{clientVersion=$version;frameworkVersion='1.3.4';frameworkHash=$expected;client=$ClientDirectory;profile=$ProfileDirectory;createdFramework=(-not $hadFramework);replacedPlugin=$hadPlugin;backup=$backup;installedAt=(Get-Date).ToString('o')} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backup 'receipt.json') -Encoding utf8
Write-Host '联动插件已安装。启动网易云后，播放栏会出现“跳动的词”，右键可以打开设置。'
Write-Host "安装记录：$backup"
