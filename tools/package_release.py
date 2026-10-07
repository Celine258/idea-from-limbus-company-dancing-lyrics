"""Build an allowlisted public archive, never copying the developer's .state."""
import argparse
import hashlib
from pathlib import Path
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_info import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {".state", ".venv", "__pycache__", "artifacts", ".git"}
PRIVATE_FILES = {"bridge-config.json", "netease-bridge.json", "settings.ini", "effect-presets.json", "BetterNCMII.dll", "msimg32.dll"}
# General Qt hooks collect Virtual Keyboard (GPL-only) and PDF, neither used by this app.
# Keep the public runtime limited to the interfaces used by this application.
UNUSED_QT = {"qt6virtualkeyboard.dll", "qtvirtualkeyboardplugin.dll", "qt6pdf.dll", "qpdf.dll"}


def package_release(package, output_dir, root=ROOT):
    package, output_dir, root = Path(package), Path(output_dir), Path(root)
    if not (package / "FloatingLyrics.exe").is_file() or not (package / "_internal").is_dir():
        raise ValueError("先构建完整的 FloatingLyrics 成品。")
    licenses = root / "release/licenses"
    if not licenses.is_dir() or not any(licenses.iterdir()):
        raise ValueError("缺少第三方许可文件，不能发布。")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"dancing-lyrics-{APP_VERSION}-windows-x64.zip"
    prefix = "DancingLyrics"
    entries = [(package / "FloatingLyrics.exe", "FloatingLyrics.exe")]
    for path in sorted((package / "_internal").rglob("*")):
        if path.is_file():
            relative = path.relative_to(package)
            if path.name.lower() in UNUSED_QT:
                continue
            if any(part in FORBIDDEN for part in relative.parts) or path.name in PRIVATE_FILES or path.suffix.lower() in (".log", ".pyc"):
                continue
            entries.append((path, relative.as_posix()))
    for path in sorted((root / "release").rglob("*")):
        if path.is_file() and path.name != "release-notes.md":
            entries.append((path, path.relative_to(root / "release").as_posix()))
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        entries.append((root / name, name))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, relative in entries:
            if any(part in FORBIDDEN for part in Path(relative).parts):
                raise ValueError(f"禁止发布个人文件：{relative}")
            archive.write(path, f"{prefix}/{relative}")
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"发布包校验失败：{bad}")
    checksum = output.with_suffix(".zip.sha256")
    checksum.write_text(f"{hashlib.sha256(output.read_bytes()).hexdigest()}  {output.name}\n", encoding="ascii")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=ROOT / "dist/FloatingLyrics")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/releases")
    args = parser.parse_args()
    print(package_release(args.package, args.output_dir))
