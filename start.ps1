param(
    [switch]$Smoke,
    [switch]$ForceSource,
    [string]$ReportDirectory = '',
    [string]$Executable = ''
)

$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot

try {
    # Check the actual control panel, not the always-on-top transparent overlay.
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class LyricsLauncherWindows {
    private delegate bool EnumWindowsCallback(IntPtr hwnd, IntPtr param);
    [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsCallback callback, IntPtr param);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int max);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hwnd);
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ProcessEntry {
        public uint size, usage, pid;
        public IntPtr heap;
        public uint module, threads, parentPid;
        public int priority;
        public uint flags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string filename;
    }
    [DllImport("kernel32.dll")] private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint pid);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern bool Process32FirstW(IntPtr snapshot, ref ProcessEntry entry);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern bool Process32NextW(IntPtr snapshot, ref ProcessEntry entry);
    [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr handle);
    private static HashSet<uint> RelatedPids(int processId) {
        HashSet<uint> related = new HashSet<uint>();
        related.Add((uint)processId);
        IntPtr snapshot = CreateToolhelp32Snapshot(2, 0);
        if (snapshot == new IntPtr(-1)) return related;
        try {
            Dictionary<uint, uint> parents = new Dictionary<uint, uint>();
            ProcessEntry entry = new ProcessEntry();
            entry.size = (uint)Marshal.SizeOf(typeof(ProcessEntry));
            if (Process32FirstW(snapshot, ref entry)) {
                do { parents[entry.pid] = entry.parentPid; } while (Process32NextW(snapshot, ref entry));
            }
            bool changed;
            do {
                changed = false;
                foreach (KeyValuePair<uint, uint> pair in parents) {
                    if (related.Contains(pair.Value) && related.Add(pair.Key)) changed = true;
                }
            } while (changed);
        } finally { CloseHandle(snapshot); }
        return related;
    }
    public static IntPtr FindVisiblePanel(int processId) {
        IntPtr result = IntPtr.Zero;
        // Windows venv pythonw.exe hands off to a child interpreter.
        HashSet<uint> related = RelatedPids(processId);
        EnumWindows(delegate(IntPtr hwnd, IntPtr unused) {
            uint pid;
            GetWindowThreadProcessId(hwnd, out pid);
            if (!related.Contains(pid)) return true;
            StringBuilder title = new StringBuilder(256);
            GetWindowText(hwnd, title, title.Capacity);
            if (title.ToString() == "\u8df3\u52a8\u7684\u6b4c\u8bcd" && IsWindowVisible(hwnd)) {
                result = hwnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }
}
'@

    $taskPackedExe = Join-Path $taskRoot 'dist\FloatingLyrics\FloatingLyrics.exe'
    $taskArguments = @()
    $taskWorkDirectory = $taskRoot
    $taskLog = Join-Path $taskRoot '.state\app.log'
    if ($Executable) {
        $taskProgram = $Executable
    } elseif (-not $ForceSource -and (Test-Path -LiteralPath $taskPackedExe)) {
        $taskProgram = $taskPackedExe
        $taskWorkDirectory = Split-Path -Parent $taskPackedExe
        $taskLog = Join-Path $taskWorkDirectory '.state\app.log'
    } else {
        $taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
        $taskPythonw = Join-Path $taskRoot '.venv\Scripts\pythonw.exe'
        if (-not (Test-Path -LiteralPath $taskPython)) {
            python -m venv (Join-Path $taskRoot '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Cannot create the project virtual environment.' }
        }
        & $taskPython -c 'import PySide6, numpy'
        if ($LASTEXITCODE -ne 0) {
            & $taskPython -m pip install -r (Join-Path $taskRoot 'requirements.txt')
            if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
        }
        $taskProgram = $taskPythonw
        $taskArguments += '"' + (Join-Path $taskRoot 'main.py') + '"'
    }

    if ($Smoke) { $taskArguments += '--smoke' }
    if ($ReportDirectory) { $taskArguments += @('--report-dir', ('"' + $ReportDirectory + '"')) }
    Write-Output 'Opening the Floating Lyrics control panel...'
    $taskOptions = @{
        FilePath = $taskProgram
        WorkingDirectory = $taskWorkDirectory
        WindowStyle = 'Normal'
        PassThru = $true
    }
    if ($taskArguments.Count) { $taskOptions.ArgumentList = $taskArguments }
    $taskProcess = Start-Process @taskOptions

    $taskWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $taskPanel = [IntPtr]::Zero
    while ($taskWatch.ElapsedMilliseconds -lt 30000) {
        if ($taskProcess.WaitForExit(150)) {
            $taskProcess.Refresh()
            throw ('The app exited before showing its control panel. Exit code: ' + $taskProcess.ExitCode)
        }
        $taskPanel = [LyricsLauncherWindows]::FindVisiblePanel($taskProcess.Id)
        if ($taskPanel -ne [IntPtr]::Zero) { break }
    }
    if ($taskPanel -eq [IntPtr]::Zero) {
        throw 'The control panel did not become visible within 30 seconds. The app may be blocked or still loading.'
    }
    Write-Output ('Control panel is visible. Process ID: ' + $taskProcess.Id)
    if ($Smoke) {
        # Screenshot and warm-cache checks cover both themes and all animation modes.
        # Keep the ordinary visible-window deadline above at 30 seconds.
        $taskSmokeWatch = [Diagnostics.Stopwatch]::StartNew()
        while (-not $taskProcess.HasExited -and $taskSmokeWatch.ElapsedMilliseconds -lt 120000) {
            $taskProcess.WaitForExit(1000) | Out-Null
        }
        if (-not $taskProcess.HasExited) { throw 'The integration check timed out.' }
        $taskProcess.Refresh()
        if ($taskProcess.ExitCode -ne 0) { throw ('The integration check failed. Exit code: ' + $taskProcess.ExitCode) }
    }
    exit 0
} catch {
    Write-Output ('Startup failed: ' + $_.Exception.Message)
    if ($taskLog -and (Test-Path -LiteralPath $taskLog)) {
        Write-Output ('Log: ' + $taskLog)
        Get-Content -Tail 20 -Encoding UTF8 -LiteralPath $taskLog
    }
    exit 1
}
