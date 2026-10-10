"""Build on a real Mac, preserve .app symlinks, and never collect user state."""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_info import APP_VERSION
from tools.package_macos import APP_BUNDLE, archive_name, audit_archive, MAC_RELEASE_TAG

ROOT = Path(__file__).resolve().parents[1]


def build(output_dir):
    if sys.platform != "darwin":
        raise RuntimeError("必须在对应架构的 macOS 环境中构建，Windows 不能交叉生成 Mac 应用")
    architecture = platform.machine()
    output = Path(output_dir).resolve() / archive_name(architecture)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"输出已存在，请使用新目录：{output}")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    iconset = ROOT / "build/macos/CityEchoes.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    icon = QIcon(str(ROOT / "assets/app.ico"))
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            label = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
            if not icon.pixmap(QSize(size * scale, size * scale)).save(str(iconset / label)):
                raise RuntimeError("无法生成应用图标")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(iconset.with_suffix(".icns"))], check=True)
    dist = ROOT / "build/macos-dist"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(dist),
                    "--workpath", str(ROOT / "build/macos-cache"), str(ROOT / "CityEchoes.spec")], cwd=ROOT, check=True)
    bundle = dist / APP_BUNDLE
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
    with tempfile.TemporaryDirectory(prefix="mac-release-", dir=ROOT / "build") as temporary:
        stage = Path(temporary) / "CityEchoes"
        stage.mkdir()
        shutil.copytree(bundle, stage / APP_BUNDLE, symlinks=True)
        for name in ("使用说明.txt", "安装播放读取工具.command"):
            shutil.copy2(ROOT / "release/macos" / name, stage / name)
        (stage / "安装播放读取工具.command").chmod(0o755)
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            shutil.copy2(ROOT / name, stage / name)
        shutil.copytree(ROOT / "release/licenses", stage / "licenses")
        numpy_license = metadata.distribution("numpy").read_text("LICENSE.txt")
        if not numpy_license:
            raise RuntimeError("缺少本架构 NumPy 许可")
        (stage / "licenses/NumPy-LICENSE.txt").write_text(numpy_license, encoding="utf-8")
        version = platform.python_version()
        candidates = [Path(sys.base_prefix) / "LICENSE.txt", Path(os.__file__).parent / "LICENSE.txt"]
        license_path = next((path for path in candidates if path.is_file()), None)
        if license_path:
            python_license = license_path.read_bytes()
        else:
            url = f"https://raw.githubusercontent.com/python/cpython/v{version}/LICENSE"
            with urllib.request.urlopen(url, timeout=30) as response:
                python_license = response.read()
        (stage / "licenses/Python-LICENSE.txt").write_bytes(python_license)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        info = {"version": APP_VERSION, "release_tag": MAC_RELEASE_TAG, "architecture": architecture,
                "macos_build": platform.mac_ver()[0], "python": version, "pyside6": metadata.version("PySide6"),
                "numpy": metadata.version("numpy"), "pyinstaller": metadata.version("pyinstaller"),
                "source_commit": commit, "notarized": False, "live_playback_verified": False,
                "external_dependency": "nowplaying-cli (not bundled)"}
        (stage / "build-info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(stage), str(output)], check=True)
    audit = audit_archive(output)
    output.with_suffix(".zip.sha256").write_text(f"{audit['sha256']}  {output.name}\n", encoding="ascii")
    print(json.dumps({"archive": str(output), **audit}, ensure_ascii=False))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/mac-release")
    build(parser.parse_args().output_dir)
