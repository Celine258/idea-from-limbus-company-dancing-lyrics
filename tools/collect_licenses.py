"""Collect runtime notices from the actual environment and versioned primary sources."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "LGPL-3.0.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.8.3/LICENSES/LGPL-3.0-only.txt",
    "GPL-3.0.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.8.3/LICENSES/GPL-3.0-only.txt",
    "LGPL-2.1.txt": "https://raw.githubusercontent.com/FFmpeg/FFmpeg/n7.1/COPYING.LGPLv2.1",
    "Qt-third-party.html": "https://doc.qt.io/qtforpython-6.8/licenses.html",
    "Qt-FFmpeg.html": "https://doc.qt.io/qt-6.8/qtmultimedia-attribution-ffmpeg.html",
    "PyInstaller-COPYING.txt": "https://raw.githubusercontent.com/pyinstaller/pyinstaller/v6.11.1/COPYING.txt",
    "BetterNCM-GPL-3.0.txt": "https://raw.githubusercontent.com/std-microblock/chromatic/1.3.4/LICENSE",
    "GFDL-1.3.txt": "https://www.gnu.org/licenses/fdl-1.3.txt",
}


def collect():
    directory = ROOT / "release/licenses"
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for name, url in SOURCES.items():
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()
        if len(content) < 1000:
            raise ValueError(f"许可内容不完整：{name}")
        (directory / name).write_bytes(content)
        records.append({"file": name, "source": url, "sha256": hashlib.sha256(content).hexdigest()})
    shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", directory / "Python-LICENSE.txt")
    numpy = importlib.metadata.distribution("numpy")
    license_file = next(path for path in numpy.files if str(path).endswith("dist-info/LICENSE.txt"))
    shutil.copyfile(numpy.locate_file(license_file), directory / "NumPy-LICENSE.txt")
    for name in ("PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6"):
        distribution = importlib.metadata.distribution(name)
        for path in distribution.files:
            if "dist-info" in str(path) and ("LICENSE" in path.name.upper() or "COPYING" in path.name.upper()):
                target = directory / (name + "-" + path.name)
                shutil.copyfile(distribution.locate_file(path), target)
    records.append({"python": sys.version.split()[0], "pyside6": importlib.metadata.version("PySide6"),
                    "numpy": numpy.version, "qtSources": "https://download.qt.io/archive/qt/6.8/6.8.3/single/"})
    (directory / "sources.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Collected {len(list(directory.iterdir()))} runtime license files")


if __name__ == "__main__":
    collect()
