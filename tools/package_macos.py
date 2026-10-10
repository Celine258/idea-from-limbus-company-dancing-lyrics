"""Audit a ditto archive, including permissions and framework symlinks."""
import hashlib
from pathlib import Path, PurePosixPath
import posixpath
import stat
import zipfile

MAC_RELEASE_TAG = "v0.6.0-beta.2-macos.1"
MAC_PACKAGE_PREFIX = "city-echoes-0.6.0-beta.2-macos.1"
APP_BUNDLE = "都市回响.app"
FORBIDDEN = {".git", ".venv", ".state", "__pycache__", "settings.ini", "effect-presets.json",
             "offsets.json", "bridge-config.json", "netease-bridge.json", "nowplaying-cli"}


def archive_name(architecture):
    if architecture not in ("arm64", "x86_64"):
        raise ValueError("仅支持原生 arm64 / x86_64 构建")
    return f"{MAC_PACKAGE_PREFIX}-{architecture}.zip"


def audit_archive(archive_path):
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise ValueError("ZIP CRC 校验失败")
        names = archive.namelist()
        seen = set()
        for entry in archive.infolist():
            name = entry.filename
            path = PurePosixPath(name)
            if name in seen or path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError(f"无效或重复路径：{name}")
            seen.add(name)
            if "__MACOSX" in path.parts:  # ditto's resource fork metadata
                continue
            if any(part in FORBIDDEN for part in path.parts) or path.suffix.lower() == ".log":
                raise ValueError(f"禁止发布个人文件或外部工具：{name}")
            if stat.S_ISLNK(entry.external_attr >> 16):
                target = archive.read(entry).decode("utf-8")
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                if target.startswith("/") or not resolved.startswith(path.parts[0] + "/"):
                    raise ValueError(f"符号链接越过发布目录：{name}")
        required = [f"{APP_BUNDLE}/Contents/MacOS/CityEchoes", f"{APP_BUNDLE}/Contents/Info.plist",
                    "使用说明.txt", "安装播放读取工具.command", "LICENSE", "THIRD_PARTY_NOTICES.md",
                    "build-info.json", "licenses/Python-LICENSE.txt", "licenses/NumPy-LICENSE.txt",
                    "licenses/LGPL-3.0.txt"]
        for suffix in required:
            if not any(name.endswith("/" + suffix) for name in names):
                raise ValueError(f"发布包缺少 {suffix}")
        for token in ("/PySide6/QtCore.", "/PySide6/QtGui.", "/PySide6/QtWidgets.",
                      "/PySide6/QtMultimedia.", "libqcocoa.dylib", "_multiarray_umath", "base_library.zip"):
            if not any(token in name for name in names):
                raise ValueError(f"发布包缺少运行依赖：{token}")
        executable = next(entry for entry in archive.infolist()
            if entry.filename.endswith(f"/{APP_BUNDLE}/Contents/MacOS/CityEchoes"))
        if not executable.external_attr >> 16 & 0o111:
            raise ValueError("Mac 主程序缺少可执行权限")
        return {"entries": len(names), "sha256": hashlib.sha256(Path(archive_path).read_bytes()).hexdigest(),
                "size": Path(archive_path).stat().st_size}
