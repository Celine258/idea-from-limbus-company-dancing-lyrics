"""Portable, transactional BetterNCM installer; no Python installation required when frozen."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import urllib.request
import zipfile

CLIENT_VERSION = "3.1.41.205529"
FRAMEWORK_VERSION = "1.3.4"
FRAMEWORK_URL = "https://github.com/std-microblock/chromatic/releases/download/1.3.4/BetterNCMII.dll"
FRAMEWORK_HASH = "a7c77af418d7940e63faa58ea036fba1f4baad497947109ea52ed78c8e86608f"
PLUGIN_NAME = "FloatingLyrics.plugin"


class InstallError(ValueError):
    pass


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def file_version(executable):
    """Read the executable's own version resource, rather than registry display strings."""
    api = ctypes.windll.version
    api.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    api.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    size = api.GetFileVersionInfoSizeW(str(executable), None)
    if not size:
        raise InstallError("无法读取网易云版本，请选择原版 cloudmusic.exe。")
    data = ctypes.create_string_buffer(size)
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not api.GetFileVersionInfoW(str(executable), 0, size, data) or not api.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        raise InstallError("网易云版本信息损坏。")
    # The fixed resource only has 16 bits per component (205529 becomes 8921).
    # Match Windows FileVersionInfo's full string instead of the truncated numeric build.
    translations, translation_size = ctypes.c_void_p(), wintypes.UINT()
    if api.VerQueryValueW(data, r"\VarFileInfo\Translation", ctypes.byref(translations), ctypes.byref(translation_size)):
        words = ctypes.cast(translations, ctypes.POINTER(wintypes.WORD))
        for index in range(0, translation_size.value // 2, 2):
            query = f"\\StringFileInfo\\{words[index]:04x}{words[index + 1]:04x}\\FileVersion"
            version_string, string_size = ctypes.c_void_p(), wintypes.UINT()
            if api.VerQueryValueW(data, query, ctypes.byref(version_string), ctypes.byref(string_size)):
                return ctypes.wstring_at(version_string).strip().replace(",", ".").replace(" ", "")
    values = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
    high, low = values[2], values[3]
    return f"{high >> 16}.{high & 65535}.{low >> 16}.{low & 65535}"


def client_running():
    result = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq cloudmusic.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    if result.returncode:
        raise InstallError("无法检查网易云进程，请完全退出网易云后重试。")
    return b'"cloudmusic.exe"' in result.stdout.lower()


def find_client():
    candidates = []
    if os.name == "nt":
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\App Paths\cloudmusic.exe", 0, winreg.KEY_READ | view) as key:
                        candidates.append(Path(winreg.QueryValue(key, None).strip('"')).parent)
                except OSError:
                    pass
    for name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(name):
            candidates.append(Path(os.environ[name]) / "NetEase/CloudMusic")
    return next((path for path in candidates if (path / "cloudmusic.exe").is_file()), None)


def default_profile():
    # BetterNCM 1.3.4 stores its profile at the root of the Windows system drive.
    return Path(os.environ.get("SystemDrive", "C:") + "\\betterncm")


def bridge_contents(state_dir, command):
    config_path = Path(state_dir) / "netease-bridge.json"
    if config_path.exists():
        try:
            token = json.loads(config_path.read_text(encoding="utf-8-sig"))["token"]
            if not isinstance(token, str) or len(token) != 64 or any(c not in "0123456789abcdefABCDEF" for c in token):
                raise ValueError()
        except (ValueError, KeyError, TypeError) as error:
            raise InstallError("现有连接配置损坏；请先备份 .state/netease-bridge.json 后重试。") from error
    else:
        token = secrets.token_hex(32)
    return json.dumps({"token": token, "command": command}, ensure_ascii=False, indent=2).encode("utf-8")


def plugin_bytes(templates, config):
    import io
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("manifest.json", "adapter.js", "index.js"):
            archive.write(Path(templates) / name, name)
        archive.writestr("bridge-config.json", config)
    return result.getvalue()


def package_plugin(state_dir, output, command):
    templates = Path(__file__).parent / "plugins/netease"
    config = bridge_contents(state_dir, command)
    data = plugin_bytes(templates, config)
    atomic_write(output, data)
    atomic_write(Path(state_dir) / "netease-bridge.json", config)
    return Path(output)


def verify_plugin(path):
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            config = json.loads(archive.read("bridge-config.json"))
        if manifest.get("slug") != "floating-lyrics" or not isinstance(config.get("command"), str):
            raise ValueError()
        return config
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        raise InstallError("目标位置已有无法识别的插件；请备份后处理，未覆盖或删除。") from error


def download_framework(target):
    try:
        with urllib.request.urlopen(FRAMEWORK_URL, timeout=30) as response, Path(target).open("wb") as output:
            size = 0
            while chunk := response.read(65536):
                size += len(chunk)
                if size > 32 * 1024 * 1024:
                    raise InstallError("框架下载大小异常。")
                output.write(chunk)
    except OSError as error:
        raise InstallError("BetterNCM 下载失败。请检查网络后重试；也可从使用说明中的官方地址下载 DLL 并在安装窗口选择。") from error


def framework_valid(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() == FRAMEWORK_HASH


class NeteaseInstaller:
    def __init__(self, app_dir, templates, *, version_reader=file_version, running=client_running, downloader=download_framework):
        self.app_dir = Path(app_dir).resolve()
        self.state = self.app_dir / ".state"
        self.templates = Path(templates)
        self.version_reader, self.running, self.downloader = version_reader, running, downloader

    @property
    def command(self):
        return f'"{self.app_dir / "FloatingLyrics.exe"}" --netease --background'

    def check_client(self, client, install=True):
        client = Path(client).resolve()
        exe = client / "cloudmusic.exe"
        if not exe.is_file():
            raise InstallError("未找到 cloudmusic.exe，请选择网易云安装目录。")
        if self.running():
            raise InstallError("请先完全退出网易云（包括托盘），再重试。安装器不会结束音乐进程。")
        if install:
            if not (self.app_dir / "FloatingLyrics.exe").is_file():
                raise InstallError("请使用完整解压的成品安装，不要从源码目录直接安装。")
            version = self.version_reader(exe)
            if version != CLIENT_VERSION:
                raise InstallError(f"当前仅支持网易云 {CLIENT_VERSION} x64；检测到 {version}，未改动客户端。")
            # PE machine type 0x8664 is required by the pinned x64 framework.
            with exe.open("rb") as stream:
                stream.seek(0x3c)
                offset = int.from_bytes(stream.read(4), "little")
                stream.seek(offset)
                if stream.read(6) != b"PE\0\0\x64\x86":
                    raise InstallError("当前仅支持网易云 64 位客户端。")
        return client

    def install(self, client, profile, framework=None):
        client = self.check_client(client)
        profile = Path(profile).resolve()
        dll, plugin = client / "msimg32.dll", profile / "plugins" / PLUGIN_NAME
        if dll.exists() and not framework_valid(dll):
            raise InstallError("已有不同版本的 msimg32.dll，未覆盖；请先确认现有 BetterNCM 版本。")
        if plugin.exists():
            verify_plugin(plugin)
        config = bridge_contents(self.state, self.command)
        data = plugin_bytes(self.templates, config)
        self.state.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="install-", dir=self.state) as temporary:
            source = dll if dll.exists() else Path(framework) if framework else Path(temporary) / "BetterNCMII.dll"
            if not source.exists():
                self.downloader(source)
            if not framework_valid(source):
                raise InstallError("BetterNCM 文件 SHA-256 校验失败，未安装。")
            paths = [plugin, self.state / "netease-bridge.json", self.state / "netease-install.json"]
            previous = {path: path.read_bytes() if path.exists() else None for path in paths}
            created_dll = not dll.exists()
            receipt = {"version": 1, "client": str(client), "profile": str(profile), "app": str(self.app_dir),
                       "clientVersion": CLIENT_VERSION, "frameworkVersion": FRAMEWORK_VERSION,
                       "frameworkHash": FRAMEWORK_HASH, "createdFramework": created_dll, "installed": True}
            try:
                if created_dll:
                    atomic_write(dll, source.read_bytes())
                atomic_write(plugin, data)
                atomic_write(paths[1], config)
                atomic_write(paths[2], json.dumps(receipt, ensure_ascii=False, indent=2).encode("utf-8"))
            except OSError:
                for path, original in previous.items():
                    if original is None:
                        path.unlink(missing_ok=True)
                    elif not path.exists() or path.read_bytes() != original:
                        atomic_write(path, original)
                if created_dll and dll.exists() and framework_valid(dll):
                    dll.unlink()
                raise
        return receipt

    def uninstall(self, client, profile):
        self.check_client(client, install=False)
        plugin = Path(profile).resolve() / "plugins" / PLUGIN_NAME
        removed = False
        if plugin.exists():
            config = verify_plugin(plugin)
            if config["command"] != self.command:
                raise InstallError("此插件指向另一份歌词程序，请从那份程序的卸载入口操作。")
            plugin.unlink()
            removed = True
        # Preferences, token, imported fonts, presets and the shared framework stay intact.
        return {"removedPlugin": removed, "preservedFramework": True, "preservedSettings": True}
