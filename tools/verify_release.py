"""Exercise the real frozen installer and BAT windows from a fresh public ZIP."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_info import APP_VERSION


def capture_window(hwnd, path):
    """Print the window itself, so unrelated foreground windows never enter public media."""
    from PIL import Image
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowDC.argtypes = [wintypes.HWND]
    user.GetWindowDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.GetBitmapBits.argtypes = [wintypes.HBITMAP, wintypes.LONG, ctypes.c_void_p]
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    rect = wintypes.RECT()
    user.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    source = user.GetWindowDC(hwnd)
    target = gdi.CreateCompatibleDC(source)
    bitmap = gdi.CreateCompatibleBitmap(source, width, height)
    old = gdi.SelectObject(target, bitmap)
    try:
        if not user.PrintWindow(hwnd, target, 2):
            raise RuntimeError("原生窗口截图失败，未使用桌面替代画面。")
        buffer = ctypes.create_string_buffer(width * height * 4)
        if gdi.GetBitmapBits(bitmap, len(buffer), buffer) != len(buffer):
            raise RuntimeError("原生窗口像素读取不完整。")
        Image.frombytes("RGB", (width, height), buffer.raw, "raw", "BGRX").save(path)
    finally:
        gdi.SelectObject(target, old)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(target)
        user.ReleaseDC(hwnd, source)


def check_bat_window(bat, directory):
    user = ctypes.windll.user32
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback, wintypes.LPARAM]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    title = f"都市回响 {APP_VERSION} · 网易云联动"
    os.startfile(str(bat))
    found = []
    @callback
    def visitor(hwnd, _):
        text = ctypes.create_unicode_buffer(512)
        user.GetWindowTextW(hwnd, text, len(text))
        if text.value == title and user.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not found:
        user.EnumWindows(visitor, 0)
        time.sleep(.2)
    if not found:
        raise RuntimeError(f"实际 BAT 未显示安装窗口：{bat.name}")
    # A native screenshot is optional when Pillow is installed on the developer machine.
    try:
        time.sleep(.3)
        capture_window(found[0], directory / (bat.stem + ".png"))
    except ImportError:
        pass
    user.PostMessageW(found[0], 0x0010, 0, 0)
    time.sleep(.5)
    return {"entry": bat.name, "nativeWindowVisible": True}


def verify(archive_path, directory, client_exe, framework):
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    directory = Path(directory).resolve()
    if directory.exists():
        raise ValueError("验证目录必须是新的空路径，以免覆盖个人文件。")
    directory.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        if any(".state" in Path(name).parts or "bridge-config.json" in name for name in archive.namelist()):
            raise ValueError("公开 ZIP 中出现个人连接配置。")
        archive.extractall(directory / "中文 解压路径")
    app = directory / "中文 解压路径/DancingLyrics"
    exe = app / "FloatingLyrics.exe"
    client, profile = directory / "网易云 隔离客户端", directory / "BetterNCM 数据"
    client.mkdir()
    shutil.copyfile(client_exe, client / "cloudmusic.exe")
    env = dict(os.environ)
    for name in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "QT_QPA_PLATFORM"):
        env.pop(name, None)
        os.environ.pop(name, None)
    env["PATH"] = os.pathsep.join((str(app), str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    os.environ["PATH"] = env["PATH"]
    checks = []
    def action(name, uninstall=False):
        report = directory / (name + ".json")
        command = [str(exe), "--uninstall-netease" if uninstall else "--install-netease", "--client-directory", str(client),
                   "--profile-directory", str(profile), "--framework-dll", str(framework), "--installer-report", str(report)]
        result = subprocess.run(command, cwd=app, env=env, timeout=120)
        data = json.loads(report.read_text(encoding="utf-8"))
        if result.returncode or not data["passed"]:
            raise RuntimeError(f"成品 {name} 失败：{data}")
        checks.append({"name": name, "passed": True})
    action("install")
    state = app / ".state"
    personal = {"settings.ini": b"[General]\nfont_family=SimSun\nvolume=24\n",
                "effect-presets.json": b'{"version":1,"presets":[]}', "fonts/retained.ttf": b"preservation fixture"}
    for name, data in personal.items():
        path = state / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    token = json.loads((state / "netease-bridge.json").read_text(encoding="utf-8"))["token"]
    # Re-extract the update ZIP over the current installation without a .state payload.
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(directory / "中文 解压路径")
    action("update")
    if json.loads((state / "netease-bridge.json").read_text(encoding="utf-8"))["token"] != token:
        raise RuntimeError("更新改变了本机连接令牌。")
    action("uninstall", True)
    action("uninstall-again", True)
    if (profile / "plugins/FloatingLyrics.plugin").exists():
        raise RuntimeError("卸载后插件仍存在。")
    if not (client / "msimg32.dll").exists():
        raise RuntimeError("卸载删除了共用框架。")
    for name, data in personal.items():
        if (state / name).read_bytes() != data:
            raise RuntimeError("更新或卸载改变了个人文件。")
    checks.append({"name": "update-uninstall-preserves-settings-fonts-presets-token-framework", "passed": True})
    for name in ("安装网易云联动.bat", "卸载网易云联动.bat"):
        checks.append(check_bat_window(app / name, directory))
    # Remove only our invalid font placeholder before the application's ordinary smoke check.
    (state / "fonts/retained.ttf").unlink()
    smoke = directory / "portable-smoke"
    os.startfile(str(app / "启动.bat"), arguments=f'--smoke --report-dir "{smoke}"')
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and not (smoke / "smoke-report.json").is_file():
        time.sleep(.3)
    data = json.loads((smoke / "smoke-report.json").read_text(encoding="utf-8"))
    if not data["passed"]:
        raise RuntimeError("公开包真实启动入口静音验证失败。")
    checks.append({"name": "public-start-bat-smoke", "passed": True})
    report = {"passed": True, "checks": checks, "developerPathRemoved": True,
              "cleanMachine": False, "version": APP_VERSION,
              "zipSha256": hashlib.sha256(Path(archive_path).read_bytes()).hexdigest()}
    (directory / "release-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--client-exe", type=Path, default=Path("C:/Program Files/NetEase/CloudMusic/cloudmusic.exe"))
    parser.add_argument("--framework", type=Path, default=Path("artifacts/netease-probe/BetterNCMII-1.3.4.dll"))
    args = parser.parse_args()
    verify(args.archive, args.directory, args.client_exe, args.framework.resolve())
