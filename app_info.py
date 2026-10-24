"""Application branding and release version, shared by source and packaged UI."""
import ctypes
import sys
from pathlib import PureWindowsPath

APP_VERSION = "0.8.0-beta.3"
KUGOU_VERSION = "0.8.0-beta.3-kugou.1"
NETEASE_VERSIONS = ("3.1.40.205461", "3.1.41.205529")
APP_NAME = "都市回响"
EFFECT_PREVIEW_TEXT = "啊，对了！但丁。有一天，去一趟图书馆吧。"
WINDOWS_APP_ID = "FloatingLyrics.Desktop"
CREATOR = "创作者：Bilibili-鈴仙優昙華院因幡"
MOTTO = "FACE THE SIN. SAVE THE E.G.O"


def kugou_default_mode(executable, frozen, arguments):
    """Only the dedicated KuGou EXE defaults to that source on double-click."""
    return bool(frozen and not arguments and PureWindowsPath(executable).name.casefold() == "dancinglyrics-kugou.exe")


def set_taskbar_identity():
    """Give source and packaged windows their own Windows taskbar identity."""
    if sys.platform != "win32":
        return True
    setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    setter.argtypes = [ctypes.c_wchar_p]
    setter.restype = ctypes.c_long
    return setter(WINDOWS_APP_ID) == 0
