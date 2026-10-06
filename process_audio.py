"""Find NetEase's main HWND and collect only its process-tree audio energy."""
import ctypes
from ctypes import wintypes
import json
import sys
from PySide6.QtCore import QObject, QProcess, QTimer
from settings import resource_path


def netease_pid():
    if sys.platform != "win32":
        return 0
    user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    found = []

    @callback_type
    def visit(hwnd, _):
        name = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(hwnd, name, 256)
        if name.value != "OrpheusBrowserHost":
            return True
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel.OpenProcess(0x1000, False, pid.value)
        if handle:
            path, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            if kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)) and path.value.lower().endswith("\\cloudmusic.exe"):
                found.append(pid.value)
            kernel.CloseHandle(handle)
        return True

    user.EnumWindows(visit, 0)
    return found[0] if found else 0


class ProcessAudio(QObject):
    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.player = player
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.errorOccurred.connect(lambda _: self._failed("音频助手无法启动"))
        self.pending = b""
        self.pid = 0
        self.helper = resource_path("native/ProcessEnergy.exe")
        if not self.helper.is_file():
            self.helper = resource_path("build/native/ProcessEnergy.exe")
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def _poll(self):
        pid = netease_pid() if self.player.connected and self.player.enabled else 0
        if pid != self.pid:
            self.stop_process()
            self.pid = pid
        if pid and self.process.state() == QProcess.ProcessState.NotRunning:
            if not self.helper.is_file():
                self._failed("音频助手缺失，请构建或使用完整打包版")
                return
            self.pending = b""
            self.process.start(str(self.helper), [str(pid)])

    def _read(self):
        self.pending += bytes(self.process.readAllStandardOutput())
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            try:
                data = json.loads(line)
                if "level" in data:
                    self.player.set_energy(float(data["level"]))
                elif "error" in data:
                    self._failed(data["error"])
            except (ValueError, TypeError):
                self._failed("音频助手返回无效数据")

    def _failed(self, text):
        self.player.has_audio_data = False
        self.player.analysis_error = text

    def stop_process(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(1000):
                self.process.kill()
                self.process.waitForFinished(1000)
        self.player.has_audio_data = False

    def close(self):
        self.timer.stop()
        self.stop_process()
