"""Isolated SMTC / read-only native lyric / window OCR companion reader."""
import asyncio
import ctypes
from ctypes import wintypes as w
import json
import math
import os
from pathlib import PureWindowsPath
import re
import struct
import sys
import time
import unicodedata


def is_kugou(source):
    return isinstance(source, str) and PureWindowsPath(source).name.casefold() in ("kugou.exe", "kugou")


def ocr_metadata(lines, width, timing_only=False):
    """Read only playback bar text, with a validated mm:ss/mm:ss anchor."""
    time_match = None
    for line in lines:
        value = re.sub(r"\s", "", unicodedata.normalize("NFKC", line["text"]))
        match = re.search(r"(?<!\d)(\d{1,3}):([0-5]\d)[/|](\d{1,3}):([0-5]\d)(?!\d)", value)
        if match:
            position = (int(match[1]) * 60 + int(match[2])) * 1000
            duration = (int(match[3]) * 60 + int(match[4])) * 1000
            if 0 < duration <= 86400000 and position <= duration:
                time_match = position, duration, line["y"]
                break
    if time_match is None:
        return None
    position, duration, time_y = time_match
    if timing_only:
        return dict(source="kugou", title="", artist="", album="", duration_ms=duration,
                    position_ms=position, playing=False, rate=1.0, mode="ocr")
    candidates = [line for line in lines if line["x"] < width * .40
                  and line["y"] < time_y - 5 and line["text"].strip()
                  and line["text"].strip() not in ("酷狗音乐", "标准", "音效", "伴唱", "词")]
    if not candidates:
        return None
    candidates.sort(key=lambda row: row["y"], reverse=True)
    row = candidates[0]
    text = row["text"].strip()
    # The playback bar places title and singer on the same row, or two rows.
    parts = re.split(r"\s+[-–—]\s+", text, maxsplit=1)
    title, artist = parts[0], parts[1] if len(parts) == 2 else ""
    if len(candidates) >= 2 and candidates[1]["y"] < row["y"] - 8:
        # Only accept a second row if both rows are aligned in the title column.
        other = candidates[1]
        if abs(other["x"] - row["x"]) < 16 and not artist:
            title, artist = other["text"].strip(), text
    if not title or len(title) > 1024 or len(artist) > 1024:
        return None
    return dict(source="KuGou.exe", title=title, artist=artist, album="", duration_ms=duration,
                position_ms=position, playing=False, rate=1.0, mode="ocr")


class WindowReader:
    def __init__(self):
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        u, g, k = self.user, self.gdi, self.kernel
        u.SetProcessDpiAwarenessContext.argtypes = [w.HANDLE]
        u.SetProcessDpiAwarenessContext(w.HANDLE(-4))
        self.callback = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        u.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
        u.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
        u.GetDC.argtypes = [w.HWND]; u.GetDC.restype = w.HDC
        u.ReleaseDC.argtypes = [w.HWND, w.HDC]
        u.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
        u.IsIconic.argtypes = [w.HWND]; u.IsWindowVisible.argtypes = [w.HWND]
        u.GetDpiForWindow.argtypes = [w.HWND]; u.GetDpiForWindow.restype = w.UINT
        u.EnumWindows.argtypes = [self.callback, w.LPARAM]
        k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
        k.CloseHandle.argtypes = [w.HANDLE]
        g.CreateCompatibleDC.argtypes = [w.HDC]; g.CreateCompatibleDC.restype = w.HDC
        g.CreateCompatibleBitmap.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]; g.CreateCompatibleBitmap.restype = w.HBITMAP
        g.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]; g.SelectObject.restype = w.HGDIOBJ
        g.DeleteObject.argtypes = [w.HGDIOBJ]; g.DeleteDC.argtypes = [w.HDC]
        g.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p, ctypes.c_void_p, w.UINT]
        from winrt.windows.media.ocr import OcrEngine
        self.engine = OcrEngine.try_create_from_user_profile_languages()
        self.last = None
        self.last_advance = 0

    def find(self, include_hidden=False):
        found = []
        @self.callback
        def visit(hwnd, _):
            if not include_hidden and not self.user.IsWindowVisible(hwnd):
                return True
            title = ctypes.create_unicode_buffer(1024)
            self.user.GetWindowTextW(hwnd, title, 1024)
            if "酷狗" not in title.value or "歌词" in title.value or "MV" in title.value:
                return True
            pid = w.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            handle = self.kernel.OpenProcess(0x1000, False, pid.value)
            if handle:
                try:
                    path, size = ctypes.create_unicode_buffer(32768), w.DWORD(32768)
                    if self.kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)) and is_kugou(path.value):
                        rect = w.RECT(); self.user.GetClientRect(hwnd, ctypes.byref(rect))
                        found.append((rect.right * rect.bottom, hwnd))
                finally:
                    self.kernel.CloseHandle(handle)
            return True
        self.user.EnumWindows(visit, 0)
        return max(found)[1] if found else None

    def capture(self, hwnd):
        class Info(ctypes.Structure):
            _fields_ = [("size", w.DWORD), ("width", w.LONG), ("height", w.LONG),
                        ("planes", w.WORD), ("bits", w.WORD), ("compression", w.DWORD),
                        ("bytes", w.DWORD), ("x", w.LONG), ("y", w.LONG), ("used", w.DWORD), ("important", w.DWORD)]
        u, g = self.user, self.gdi
        if u.IsIconic(hwnd):
            return None
        rect = w.RECT(); u.GetClientRect(hwnd, ctypes.byref(rect))
        width, height = rect.right, rect.bottom
        if not 200 < width <= 7680 or not 100 < height <= 4320 or width * height > 16000000:
            return None
        dc = u.GetDC(hwnd); mem = g.CreateCompatibleDC(dc)
        bitmap = g.CreateCompatibleBitmap(dc, width, height)
        if not dc or not mem or not bitmap:
            if bitmap: g.DeleteObject(bitmap)
            if mem: g.DeleteDC(mem)
            if dc: u.ReleaseDC(hwnd, dc)
            return None
        old = g.SelectObject(mem, bitmap)
        try:
            if not u.PrintWindow(hwnd, mem, 3):
                return None
            g.SelectObject(mem, old)
            info = Info(ctypes.sizeof(Info), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
            pixels = ctypes.create_string_buffer(width * height * 4)
            if not g.GetDIBits(mem, bitmap, 0, height, pixels, ctypes.byref(info), 0):
                return None
            crop = min(height, round(120 * max(96, u.GetDpiForWindow(hwnd)) / 96))
            return width, crop, pixels.raw[(height - crop) * width * 4:]
        finally:
            g.SelectObject(mem, old); g.DeleteObject(bitmap); g.DeleteDC(mem); u.ReleaseDC(hwnd, dc)

    async def read(self, timing_only=False):
        if not self.engine:
            return None, "系统缺少 OCR 语言包；请安装 Windows 简体中文文字识别组件。"
        hwnd = self.find()
        if not hwnd:
            return None, "等待酷狗音乐启动并播放歌曲。"
        pixels = self.capture(hwnd)
        if pixels is None:
            return None, "酷狗未提供系统媒体接口；界面兼容模式需要还原酷狗主窗口。"
        from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
        from winrt.windows.storage.streams import Buffer
        width, height, data = pixels
        # Large playback windows use small, pale timeline digits. Read a scaled
        # copy of the left playback region instead of relying on screen DPI.
        from PySide6.QtGui import QImage
        from PySide6.QtCore import Qt
        image = QImage(data, width, height, QImage.Format.Format_RGB32)
        image = image.copy(0, height // 2, max(1, round(width * .48)), height - height // 2)
        image = image.scaledToWidth(min(2400, image.width() * 3), Qt.TransformationMode.SmoothTransformation)
        image = image.convertToFormat(QImage.Format.Format_RGB32)
        width, height, data = image.width(), image.height(), bytes(image.constBits())
        buffer = Buffer(len(data)); buffer.length = len(data); memoryview(buffer)[:] = data
        bitmap = SoftwareBitmap.create_copy_from_buffer(buffer, BitmapPixelFormat.BGRA8, width, height)
        result = await asyncio.wait_for(self.engine.recognize_async(bitmap), 3)
        lines = []
        for line in result.lines:
            words = list(line.words)
            if words:
                lines.append(dict(text=line.text, x=min(word.bounding_rect.x for word in words),
                                  y=min(word.bounding_rect.y for word in words)))
        snapshot = ocr_metadata(lines, width, timing_only)
        if snapshot is None:
            self.last = None
            return None, "界面兼容模式：等待播放栏显示可识别的歌名和进度。"
        now = time.monotonic()
        key = (snapshot["title"], snapshot["artist"], snapshot["duration_ms"])
        if self.last and self.last[0] == key:
            if snapshot["position_ms"] > self.last[1]:
                self.last_advance = now
            snapshot["playing"] = now - self.last_advance < 1.3
        else:
            self.last_advance = 0
        self.last = key, snapshot["position_ms"]
        return snapshot, "界面兼容模式 · 约 1 秒精度；请保持酷狗主窗口还原。"


async def smtc_snapshot(manager):
    sessions = [session for session in manager.get_sessions() if is_kugou(session.source_app_user_model_id)]
    if not sessions:
        return None
    if len(sessions) != 1:
        raise ValueError("发现多个酷狗媒体会话，请只保留一个酷狗实例。")
    session = sessions[0]
    props = await asyncio.wait_for(session.try_get_media_properties_async(), 2)
    info = session.get_playback_info(); timeline = session.get_timeline_properties()
    duration = timeline.end_time.total_seconds() * 1000
    position = timeline.position.total_seconds() * 1000
    rate = info.playback_rate if info.playback_rate is not None else 1.0
    if not props.title:
        return None
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status
    playing = info.playback_status == Status.PLAYING
    if playing and duration > 0:
        import datetime
        age = (datetime.datetime.now(datetime.timezone.utc) - timeline.last_updated_time).total_seconds()
        if not -2 <= age <= 86400:
            raise ValueError("酷狗媒体时间轴已失效")
        position += max(0, age) * 1000 * rate
    return dict(source=session.source_app_user_model_id, title=props.title, artist=props.artist,
                album=props.album_title, duration_ms=round(duration), position_ms=min(duration, max(0, position)),
                playing=playing, rate=rate, mode="smtc")


NATIVE_HINTS = {
    "client_x86_unsupported": "此酷狗为 32 位，当前原生后台通道尚未适配",
    "module_unsupported": "此酷狗歌词模块架构尚未适配",
    "read_access_unavailable": "无法读取酷狗进程，请确认两者均以普通用户身份运行",
    "module_unavailable": "未找到可读取的酷狗歌词模块",
    "layout_unrecognized": "此酷狗版本的歌词结构尚未适配",
    "no_matching_lyric_object": "未找到匹配当前歌曲的原生歌词对象，请开启酷狗桌面歌词",
    "timeline_stalled": "原生歌词进度未推进，正在重新寻找后台歌词视图",
}


async def sample_channels(manager, native, windows, window=None):
    media = await smtc_snapshot(manager)
    if media is not None and media["duration_ms"] > 0:
        return media, "系统媒体接口 · 自动读取酷狗歌曲与进度。", window
    pid = windows.pid()
    native_snapshot = None
    if pid:
        try:
            native_snapshot = native.read(pid, media)
        except (ValueError, OSError, KeyError, AttributeError, struct.error):
            # Unknown private layouts fail closed; window OCR remains available.
            native_snapshot = None
    if native_snapshot is not None:
        after = await smtc_snapshot(manager)
        if media is not None and (after is None or (media["title"], media["artist"]) != (after["title"], after["artist"])):
            return None, "正在切歌，等待歌曲信息稳定。", window
        if media is None and after is not None:
            from kugou_identity import titles_match, track_artists_match
            if (not titles_match(native_snapshot["title"], after["title"]) or
                    after["artist"] and not track_artists_match(native_snapshot["artist"], after["artist"],
                                                               native_snapshot["title"], after["title"])):
                return None, "正在切歌，等待歌曲信息稳定。", window
            native_snapshot["playing"], native_snapshot["rate"] = after["playing"], after["rate"]
        message = "原生歌词通道 · 支持最小化；毫秒进度，显示时长取歌词时间范围。"
        if getattr(native, "status", "") == "timeline_stalled":
            message += " " + NATIVE_HINTS["timeline_stalled"] + "。"
        return native_snapshot, message, window
    window = window or WindowReader()
    snapshot, message = await window.read(timing_only=media is not None)
    if snapshot is not None and media is not None:
        after = await smtc_snapshot(manager)
        if after is None or (media["title"], media["artist"]) != (after["title"], after["artist"]):
            return None, "正在切歌，等待歌曲信息稳定。", window
        for key in ("source", "title", "artist", "album", "playing", "rate"):
            snapshot[key] = media[key]
        snapshot["mode"] = "hybrid"
        message = "界面兼容模式 · 约 1 秒精度，需还原主窗口；打开酷狗桌面歌词可尝试后台通道。"
    if snapshot is None and "还原" in message:
        message = "等待酷狗原生歌词数据：请打开酷狗自带的桌面歌词；不支持时请还原主窗口使用界面兼容模式。"
    hint = NATIVE_HINTS.get(getattr(native, "status", "")) if pid else None
    if hint:
        message += " 后台诊断：" + hint + "。"
    return snapshot, message, window


async def reader(once=False, parent_pid=None):
    import winrt.windows.foundation
    import winrt.windows.foundation.collections
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
    from kugou_native import NativeLyricsReader
    from kugou_windows import Windows, NativeVisibility, CommandPipe
    manager = window = None
    windows, native, commands = Windows(), NativeLyricsReader(), CommandPipe()
    visibility = NativeVisibility(windows)
    visibility.close()  # Recover a window leased by a previous dead helper.
    try:
        while True:
            if commands.quit or parent_pid and not windows.alive(parent_pid):
                break
            try:
                if manager is None:
                    manager = await asyncio.wait_for(Manager.request_async(), 3)
                snapshot, message, window = await sample_channels(manager, native, windows, window)
                replace = commands.poll() and snapshot is not None and snapshot["mode"] in ("native", "smtc")
                visibility.replace(windows.pid() if replace else None, replace)
                recoverable = snapshot is None and (native.process is not None or message in (
                    "界面兼容模式：等待播放栏显示可识别的歌名和进度。", "正在切歌，等待歌曲信息稳定。"))
                print(json.dumps(dict(snapshot=snapshot, message=message, recoverable=recoverable, reader_pid=os.getpid()), ensure_ascii=False), flush=True)
            except Exception as error:
                visibility.close()
                print(json.dumps(dict(snapshot=None, message="读取暂不可用，将自动重试。", error=type(error).__name__,
                                      recoverable=True, reader_pid=os.getpid()), ensure_ascii=False), flush=True)
                manager = None
            if once:
                break
            await asyncio.sleep(.15)
    finally:
        visibility.close()
        native.close()


def run(once=False):
    if sys.stdout is None:
        import msvcrt
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetStdHandle.argtypes = [w.DWORD]; kernel.GetStdHandle.restype = w.HANDLE
        handle = kernel.GetStdHandle(w.DWORD(-11 & 0xffffffff))
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY)
        sys.stdout = os.fdopen(fd, "w", encoding="utf-8", buffering=1)
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parent_pid = None
    if "--parent-pid" in sys.argv:
        index = sys.argv.index("--parent-pid")
        parent_pid = int(sys.argv[index + 1])
    asyncio.run(reader(once, parent_pid))
    return 0


if __name__ == "__main__":
    raise SystemExit(run("--once" in sys.argv))
