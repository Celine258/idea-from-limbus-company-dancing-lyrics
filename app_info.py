"""Application branding and release version, shared by source and packaged UI."""
import ctypes
import sys

APP_VERSION = "0.5.0"
WINDOWS_APP_ID = "FloatingLyrics.Desktop"
CREATOR = "创作者：Bilibili-鈴仙優昙華院因幡"
MOTTO = "FACE THE SIN. SAVE THE E.G.O"


def set_taskbar_identity():
    """Give source and packaged windows their own Windows taskbar identity."""
    if sys.platform != "win32":
        return True
    setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    setter.argtypes = [ctypes.c_wchar_p]
    setter.restype = ctypes.c_long
    return setter(WINDOWS_APP_ID) == 0
