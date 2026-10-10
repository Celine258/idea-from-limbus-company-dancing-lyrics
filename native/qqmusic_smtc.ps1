# Read-only Windows media session bridge. Windows PowerShell 5.1 / Win10 1809+.
param([switch]$Once)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$taskManagerType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime]
$taskMediaType = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties, Windows.Media.Control, ContentType=WindowsRuntime]
$taskAwaitMethod = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1
} | Select-Object -First 1
function Read-Async($Operation, $ResultType) {
    $taskAsync = $taskAwaitMethod.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    if (-not $taskAsync.Wait(2000)) { throw 'SMTC read timed out' }
    return $taskAsync.Result
}
$taskManager = $null
do {
    try {
        if ($null -eq $taskManager) { $taskManager = Read-Async ($taskManagerType::RequestAsync()) $taskManagerType }
        # Never use the global current session: it may belong to a browser/NetEase.
        $taskSessions = @($taskManager.GetSessions() | Where-Object {
            [IO.Path]::GetFileName($_.SourceAppUserModelId) -ieq 'QQMusic.exe'
        })
        if ($taskSessions.Count -gt 1) { throw 'Multiple QQ Music media sessions' }
        $taskSnapshot = $null
        if ($taskSessions.Count -eq 1) {
            $taskSession = $taskSessions[0]
            $taskMedia = Read-Async ($taskSession.TryGetMediaPropertiesAsync()) $taskMediaType
            $taskTimeline = $taskSession.GetTimelineProperties()
            $taskPlayback = $taskSession.GetPlaybackInfo()
            $taskRate = if ($null -eq $taskPlayback.PlaybackRate) { 1.0 } else { [double]$taskPlayback.PlaybackRate }
            $taskSnapshot = [ordered]@{
                source = $taskSession.SourceAppUserModelId
                title = $taskMedia.Title
                artist = $taskMedia.Artist
                album = $taskMedia.AlbumTitle
                state = $taskPlayback.PlaybackStatus.ToString()
                position_ms = $taskTimeline.Position.TotalMilliseconds
                duration_ms = $taskTimeline.EndTime.TotalMilliseconds
                updated_ms = $taskTimeline.LastUpdatedTime.ToUnixTimeMilliseconds()
                observed_ms = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
                rate = $taskRate
            }
        }
        [Console]::WriteLine((ConvertTo-Json -InputObject @{ snapshot = $taskSnapshot } -Depth 4 -Compress))
    } catch {
        [Console]::WriteLine('{"snapshot":null,"error":"Windows media session read failed"}')
        $taskManager = $null
        if (-not $Once) { Start-Sleep -Milliseconds 1000 }
    }
    if (-not $Once) { Start-Sleep -Milliseconds 250 }
} while (-not $Once)
