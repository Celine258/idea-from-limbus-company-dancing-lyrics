"""Recover a desktop lyric window's topmost layer without activating it."""
import sys
import os
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication


class WindowsLayer:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.types = ctypes, wintypes
        self.user = ctypes.windll.user32
        self.process_id = os.getpid()
        signatures = {
            "SetWindowPos": ([wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL),
            "GetWindowLongW": ([wintypes.HWND, ctypes.c_int], ctypes.c_long),
            "GetForegroundWindow": ([], wintypes.HWND),
            "GetWindow": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
            "GetAncestor": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
            "IsWindowVisible": ([wintypes.HWND], wintypes.BOOL),
            "IsIconic": ([wintypes.HWND], wintypes.BOOL),
            "GetWindowRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            "GetClassNameW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "GetWindowThreadProcessId": ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            "UnhookWinEvent": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.user, name)
            function.argtypes, function.restype = arguments, result
        self.callback_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
            wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        self.user.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
            self.callback_type, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        self.user.SetWinEventHook.restype = wintypes.HANDLE
        self.hooks, self.callback = [], None

    def watch(self, notify):
        if self.hooks:
            return
        def event(_hook, kind, hwnd, obj, child, _thread, _time):
            if kind == 3:
                notify(0)
            elif obj == 0 and child == 0 and self.topmost_candidate(hwnd):
                notify(int(hwnd))
        self.callback = self.callback_type(event)
        # Out-of-context notifications, skipping our own changes; no injection.
        for first, last in ((3, 3), (0x8002, 0x8004)):
            hook = self.user.SetWinEventHook(first, last, None, self.callback, 0, 0, 2)
            if hook:
                self.hooks.append(hook)

    def close(self):
        for hook in self.hooks:
            self.user.UnhookWinEvent(hook)
        self.hooks.clear()
        self.callback = None

    def topmost_candidate(self, hwnd):
        if not hwnd or not self.user.IsWindowVisible(hwnd) or self.user.IsIconic(hwnd):
            return False
        style = self.user.GetWindowLongW(hwnd, -20)
        if not style & 8 or style & 0x20:
            return False
        owner = self.types.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, self.ctypes.byref(owner))
        if owner.value == self.process_id:
            return False
        name = self.ctypes.create_unicode_buffer(128)
        self.user.GetClassNameW(hwnd, name, len(name))
        return name.value not in ("#32768", "tooltips_class32", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")

    def needs_repair(self, hwnd, candidate=0):
        if not self.user.GetWindowLongW(hwnd, -20) & 8:
            return True
        candidate = self.user.GetAncestor(candidate, 2) if candidate else 0
        a = self.types.RECT()
        if not self.user.GetWindowRect(hwnd, self.ctypes.byref(a)):
            return False
        above = self.user.GetWindow(hwnd, 3)
        for _ in range(256):
            if not above:
                break
            if (not candidate or above == candidate) and self.topmost_candidate(above):
                b = self.types.RECT()
                if (self.user.GetWindowRect(above, self.ctypes.byref(b)) and
                    a.right > b.left and b.right > a.left and a.bottom > b.top and b.bottom > a.top):
                    return True
            above = self.user.GetWindow(above, 3)
        return False

    def apply(self, hwnd):
        # Preserve position/size and the foreground application's focus.
        return bool(self.user.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x213))


class TopmostGuard(QObject):
    def __init__(self, widget, backend=None):
        super().__init__(widget)
        self.widget = widget
        native = sys.platform == "win32" and QApplication.instance().platformName() == "windows"
        self.backend = backend if backend is not None else WindowsLayer() if native else None
        self.running = self.force = False
        self.candidate = 0
        self.pending = QTimer(self)
        self.pending.setSingleShot(True)
        self.pending.setInterval(60)
        self.pending.timeout.connect(self._repair)
        self.watchdog = QTimer(self)
        self.watchdog.setInterval(250)
        self.watchdog.timeout.connect(self._repair)
        if self.backend:
            widget.destroyed.connect(self.backend.close)
            QApplication.instance().aboutToQuit.connect(self.backend.close)

    def start(self):
        if not self.backend or not self.widget.isVisible():
            return
        self.running = True
        self.backend.watch(self._notify)
        self.force = True
        self._repair()
        self.watchdog.start()

    def request(self, *, force=False):
        if self.running and self.widget.isVisible():
            self.force |= force
            if not self.pending.isActive():
                self.pending.start()

    def _notify(self, hwnd):
        if hwnd:
            self.candidate = hwnd
        self.request()

    def _repair(self):
        if not self.running or not self.widget.isVisible():
            return
        hwnd = int(self.widget.winId())
        needed = self.force or self.backend.needs_repair(hwnd, self.candidate)
        if not needed and self.candidate:
            needed = self.backend.needs_repair(hwnd)
        if needed:
            self.backend.apply(hwnd)
        self.force = False

    def stop(self):
        self.running = self.force = False
        self.pending.stop()
        self.watchdog.stop()
        self.candidate = 0
        if self.backend:
            self.backend.close()
