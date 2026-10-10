"""Release boundaries: dependencies, private files, links and immutable bundles."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import stat
import struct
import json
import hashlib
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import main_mac
from tools.package_macos import APP_BUNDLE, archive_name, audit_archive, record_runtime_licenses

ROOT = Path(__file__).resolve().parents[1]


def runtime_entries():
    prefix = "CityEchoes/"
    names = [f"{APP_BUNDLE}/Contents/MacOS/CityEchoes", f"{APP_BUNDLE}/Contents/Info.plist",
             "使用说明.txt", "安装播放读取工具.command", "LICENSE", "THIRD_PARTY_NOTICES.md",
             "build-info.json", "licenses/Python-LICENSE.txt", "licenses/NumPy-LICENSE.txt",
             "licenses/LGPL-3.0.txt"]
    names += [f"{APP_BUNDLE}/Contents/Frameworks/PySide6/{module}.abi3.so"
              for module in ("QtCore", "QtGui", "QtWidgets", "QtMultimedia")]
    names += [f"{APP_BUNDLE}/Contents/Frameworks/PySide6/Qt/plugins/platforms/libqcocoa.dylib",
              f"{APP_BUNDLE}/Contents/Frameworks/numpy/core/_multiarray_umath.so",
              f"{APP_BUNDLE}/Contents/Resources/base_library.zip"]
    return {prefix + name: b"fixture" for name in names}


def write_archive(path, entries, extra=(), executable=True):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
            archive.writestr(entry, content)
        for entry, content in extra:
            archive.writestr(entry, content)


class MacDistributionTests(unittest.TestCase):
    def test_license_manifest_uses_actual_runtime_and_architecture_specific_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "sources.json").write_text(json.dumps([{"python": "3.11.8", "numpy": "old"}]))
            (directory / "Python-LICENSE.txt").write_bytes(b"actual python runtime license")
            (directory / "NumPy-LICENSE.txt").write_bytes(b"arm64 wheel license")
            record_runtime_licenses(directory, "3.12.10", "1.26.4", "arm64")
            entries = json.loads((directory / "sources.json").read_text())
            self.assertEqual(entries[0], {"python": "3.12.10", "numpy": "1.26.4", "architecture": "arm64"})
            for entry in entries[1:]:
                self.assertEqual(entry["sha256"], hashlib.sha256((directory / entry["file"]).read_bytes()).hexdigest())

    def test_frozen_settings_live_outside_app_bundle_and_survive_location_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with patch.object(main_mac.sys, "frozen", True, create=True), patch.object(main_mac.Path, "home", return_value=home):
                first = main_mac.default_state_directory()
                first.mkdir(parents=True)
                (first / "settings.ini").write_text("existing user settings", encoding="utf-8")
                with patch.object(main_mac.sys, "executable", str(home / "Applications/都市回响.app/Contents/MacOS/CityEchoes")):
                    self.assertEqual(main_mac.default_state_directory(), first)
                    self.assertEqual((first / "settings.ini").read_text(), "existing user settings")
                self.assertEqual(first, home / "Library/Application Support/CityEchoes")

    def test_source_settings_remain_in_existing_project_directory(self):
        with patch.object(main_mac.sys, "frozen", False, create=True):
            self.assertEqual(main_mac.default_state_directory(), ROOT / ".state")

    def test_smoke_requires_explicit_isolated_directories(self):
        for args in (["--smoke"], ["--smoke", "--state-dir", "example"],
                     ["--smoke", "--state-dir", "example", "--report-dir", "reports", "--local"]):
            with self.subTest(args=args), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                main_mac.main(args)
            self.assertEqual(error.exception.code, 2)

    def test_architecture_names_are_distinct_and_reject_unknown_builds(self):
        self.assertNotEqual(archive_name("arm64"), archive_name("x86_64"))
        with self.assertRaises(ValueError):
            archive_name("universal2")

    def test_release_audit_accepts_complete_structure_and_safe_framework_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "中文 path.zip"
            link = zipfile.ZipInfo(f"CityEchoes/{APP_BUNDLE}/Contents/Frameworks/PySide6/QtCore.so")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            write_archive(archive, runtime_entries(), [(link, b"QtCore.abi3.so")])
            result = audit_archive(archive)
            self.assertGreater(result["entries"], 10)
            self.assertEqual(len(result["sha256"]), 64)

    def test_missing_qtcore_or_cocoa_plugin_fails_before_publication(self):
        for token in ("/QtCore.", "libqcocoa.dylib"):
            with self.subTest(token=token), tempfile.TemporaryDirectory() as temporary:
                archive = Path(temporary) / "missing.zip"
                write_archive(archive, {k: v for k, v in runtime_entries().items() if token not in k})
                with self.assertRaisesRegex(ValueError, "运行依赖"):
                    audit_archive(archive)

    def test_ditto_utf8_names_without_zip_language_flag_are_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "ditto.zip"
            write_archive(archive, runtime_entries())
            data = bytearray(archive.read_bytes())
            # Match ditto's UTF-8 metadata with the language flag unset.
            for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
                offset = 0
                while (offset := data.find(signature, offset)) >= 0:
                    flags = struct.unpack_from("<H", data, offset + flag_offset)[0]
                    struct.pack_into("<H", data, offset + flag_offset, flags & ~0x800)
                    offset += 4
            archive.write_bytes(data)
            self.assertGreater(audit_archive(archive)["entries"], 10)

    def test_private_settings_and_external_binary_cannot_enter_archive(self):
        for private in (".state/settings.ini", "fonts/debug.log", "nowplaying-cli", "effect-presets.json"):
            with self.subTest(private=private), tempfile.TemporaryDirectory() as temporary:
                archive = Path(temporary) / "private.zip"
                entries = runtime_entries()
                entries["CityEchoes/" + private] = b"private"
                write_archive(archive, entries)
                with self.assertRaisesRegex(ValueError, "禁止发布"):
                    audit_archive(archive)

    def test_archive_rejects_path_traversal_and_escaping_framework_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "bad.zip"
            entries = runtime_entries()
            entries["CityEchoes/../outside"] = b"bad"
            write_archive(archive, entries)
            with self.assertRaisesRegex(ValueError, "无效"):
                audit_archive(archive)
            link = zipfile.ZipInfo(f"CityEchoes/{APP_BUNDLE}/Contents/Frameworks/bad")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            write_archive(archive, runtime_entries(), [(link, b"../../../../outside")])
            with self.assertRaisesRegex(ValueError, "符号链接"):
                audit_archive(archive)

    def test_executable_permissions_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "not-executable.zip"
            write_archive(archive, runtime_entries(), executable=False)
            with self.assertRaisesRegex(ValueError, "可执行权限"):
                audit_archive(archive)

    def test_build_refuses_cross_compilation_on_windows(self):
        from tools.build_macos import build
        from tools.verify_macos import verify
        with patch("sys.platform", "win32"):
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                build("unused")
            with self.assertRaisesRegex(RuntimeError, "原生 macOS"):
                verify("unused.zip", "unused")


if __name__ == "__main__":
    unittest.main()
