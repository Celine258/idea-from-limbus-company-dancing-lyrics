"""Application branding and release version, shared by source and packaged UI."""
import ctypes
import sys

APP_VERSION = "0.6.0-beta.2"
NETEASE_VERSIONS = ("3.1.40.205461", "3.1.41.205529")
APP_NAME = "都市回响"
EFFECT_PREVIEW_TEXT = "啊，对了！但丁。有一天，去一趟图书馆吧。"
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
