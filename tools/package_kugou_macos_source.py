"""Allowlisted portable sources; a source ZIP is never labelled a Mac binary."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_info import APP_VERSION
from tools.package_macos import source_commit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "DancingLyrics-Kugou-Mac-Source"
SOURCE_FILES = (
    "main_mac.py", "main_mac_kugou.py", "macos_kugou.py", "macos_netease.py", "macos_smoke.py",
    "kugou_lyrics.py", "kugou_identity.py", "lrc.py", "controls.py", "overlay.py", "player.py",
    "audio_energy.py", "animation.py", "glyph_motion.py", "text_effects.py", "gradients.py", "window_layer.py",
    "scramble.py", "fonts.py", "settings.py", "presets.py", "screens.py", "themes.py", "app_info.py",
    "CityEchoes.spec", "requirements.txt", "requirements-build.txt", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "AGENTS.md", "CHANGELOG.md", "MACOS.md", "KUGOU-MACOS.md", "安装酷狗Mac.command", "启动酷狗Mac.command",
    "docs/research/kugou-macos-20261017.json",
    "检查酷狗Mac.command", "打包酷狗Mac.command", "tools/build_macos.py", "tools/package_macos.py",
    "tools/verify_macos.py", "tools/probe_kugou_macos.py", "tools/package_kugou_macos_source.py",
    ".github/workflows/kugou-macos-package.yml", "tests/test_kugou_macos.py",
)


def package(output_dir, root=ROOT):
    root, output_dir = Path(root), Path(output_dir)
    paths = list(SOURCE_FILES)
    for folder in ("assets", "release/licenses", "release/kugou-macos"):
        paths.extend(p.relative_to(root).as_posix() for p in sorted((root / folder).rglob("*")) if p.is_file())
    if len(paths) != len(set(paths)):
        raise ValueError("源码清单中存在重复文件")
    for name in paths:
        if not (root / name).is_file() or (root / name).is_symlink():
            raise ValueError(f"源码文件缺失或是符号链接：{name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"dancing-lyrics-{APP_VERSION}-kugou-macos.1-source.zip"
    commit = source_commit(root)
    manifest = {"version": APP_VERSION, "player": "kugou", "format": "source",
                "source_commit": commit, "native_app_included": False,
                "macos_live_verified": False, "architecture": "detected-on-Mac"}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in paths:
            entry = zipfile.ZipInfo(f"{PREFIX}/{name}")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | (0o755 if name.endswith(".command") else 0o644)) << 16
            content = (root / name).read_bytes()
            if name.endswith((".py", ".command", ".spec", ".yml")):
                content = content.replace(b"\r\n", b"\n")
            archive.writestr(entry, content, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr(f"{PREFIX}/source-info.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError("源码 ZIP 校验失败")
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{checksum}  {output.name}\n", encoding="ascii")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/mac-source")
    print(package(parser.parse_args().output_dir))
