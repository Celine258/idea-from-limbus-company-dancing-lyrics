"""Compare actual Windows panel visibility under two startup window modes."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import time

user32 = ctypes.windll.user32
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.WaitForInputIdle.argtypes = [wintypes.HANDLE, wintypes.DWORD]


def window_snapshot(pid):
    windows = []

    @callback_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            text = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, text, len(text))
            if text.value:
                windows.append({"title": text.value, "visible": bool(user32.IsWindowVisible(hwnd))})
        return True

    user32.EnumWindows(visit, 0)
    return windows


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    reports = []
    for name, mode in (("hidden", 0), ("normal", 1)):
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = mode
        report_dir = root / "artifacts" / ("startup-" + name)
        process = subprocess.Popen([str(root / "dist/FloatingLyrics/FloatingLyrics.exe"),
                                    "--smoke", "--report-dir", str(report_dir)],
                                   startupinfo=startup, cwd=root)
        user32.WaitForInputIdle(int(process._handle), 15000)
        time.sleep(.4)
        snapshots = window_snapshot(process.pid)
        exit_code = process.wait(timeout=30)
        reports.append({"mode": name, "pid": process.pid, "windows": snapshots, "exit_code": exit_code})
    target = root / "artifacts/startup-probe.json"
    target.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(reports, ensure_ascii=True, indent=2))
    expected = {"hidden": (False, 1), "normal": (True, 0)}
    for report in reports:
        panel = next((w for w in report["windows"] if w["title"] == "都市回响"), None)
        visible, code = expected[report["mode"]]
        if panel is None or panel["visible"] != visible or report["exit_code"] != code:
            raise SystemExit("Startup visibility regression check failed")
