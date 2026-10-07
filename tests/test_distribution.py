"""Public installer transactions and clean release boundary."""
import json
from pathlib import Path
import tempfile
import unittest
import os
import subprocess
from unittest.mock import patch, PropertyMock
import zipfile
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from installer_ui import InstallerWindow
import netease_install as ni
from tools.package_release import package_release

ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.app = root / "中文 歌词目录"
        self.app.mkdir()
        (self.app / "FloatingLyrics.exe").write_bytes(b"test engine")
        self.client = root / "网易云 客户端"
        self.client.mkdir()
        # Minimal PE header fixture; real native tests use the original executable resource.
        data = bytearray(128)
        data[0x3c:0x40] = (64).to_bytes(4, "little")
        data[64:70] = b"PE\0\0\x64\x86"
        (self.client / "cloudmusic.exe").write_bytes(data)
        self.profile = root / "插件 数据"
        self.framework = root / "framework.dll"
        self.framework.write_bytes(b"verified test framework")
        self.validator = patch.object(ni, "framework_valid", side_effect=lambda path: Path(path).read_bytes() == b"verified test framework")
        self.validator.start()
        self.addCleanup(self.validator.stop)
        self.installer = ni.NeteaseInstaller(self.app, ROOT / "plugins/netease",
                                             version_reader=lambda exe: ni.CLIENT_VERSION, running=lambda: False)

    @property
    def plugin(self):
        return self.profile / "plugins" / ni.PLUGIN_NAME

    def install(self):
        return self.installer.install(self.client, self.profile, self.framework)

    def test_install_repeat_update_and_uninstall_preserve_personal_files(self):
        state = self.app / ".state"
        state.mkdir()
        personal = {"settings.ini": b"font=SimSun", "effect-presets.json": b'{"version":1}', "fonts/mine.ttf": b"font"}
        for name, data in personal.items():
            (state / name).parent.mkdir(parents=True, exist_ok=True)
            (state / name).write_bytes(data)
        self.install()
        config = json.loads((state / "netease-bridge.json").read_text(encoding="utf-8"))
        self.assertEqual(len(config["token"]), 64)
        self.assertIn(str(self.app / "FloatingLyrics.exe"), config["command"])
        with zipfile.ZipFile(self.plugin) as archive:
            self.assertEqual(json.loads(archive.read("bridge-config.json")), config)
        self.assertFalse(self.install()["createdFramework"])
        self.assertEqual(json.loads((state / "netease-bridge.json").read_text(encoding="utf-8")), config)
        self.assertTrue(self.installer.uninstall(self.client, self.profile)["removedPlugin"])
        self.assertFalse(self.installer.uninstall(self.client, self.profile)["removedPlugin"])
        self.assertTrue((self.client / "msimg32.dll").exists())
        for name, data in personal.items():
            self.assertEqual((state / name).read_bytes(), data)
        self.assertTrue((state / "netease-bridge.json").exists())

    def test_two_computers_generate_independent_tokens(self):
        first = ni.bridge_contents(self.app / ".state", self.installer.command)
        second = ni.bridge_contents(self.app / ".other", self.installer.command)
        self.assertNotEqual(json.loads(first)["token"], json.loads(second)["token"])

    def test_client_running_wrong_version_and_x86_are_rejected_before_writes(self):
        for failure in ("running", "version", "x86"):
            with self.subTest(failure=failure):
                if failure == "running":
                    self.installer.running = lambda: True
                elif failure == "version":
                    self.installer.running = lambda: False
                    self.installer.version_reader = lambda exe: "3.2.0"
                else:
                    self.installer.version_reader = lambda exe: ni.CLIENT_VERSION
                    path = self.client / "cloudmusic.exe"
                    data = bytearray(path.read_bytes())
                    data[68:70] = b"\x4c\x01"
                    path.write_bytes(data)
                with self.assertRaises(ni.InstallError):
                    self.install()
                self.assertFalse(self.plugin.exists())
                self.assertFalse((self.client / "msimg32.dll").exists())

    def test_download_failure_and_bad_hash_leave_client_untouched(self):
        self.installer.downloader = lambda path: (_ for _ in ()).throw(ni.InstallError("网络失败"))
        with self.assertRaisesRegex(ni.InstallError, "网络"):
            self.installer.install(self.client, self.profile)
        self.installer.downloader = lambda path: Path(path).write_bytes(b"wrong hash")
        with self.assertRaisesRegex(ni.InstallError, "SHA-256"):
            self.installer.install(self.client, self.profile)
        self.assertFalse(self.plugin.exists())
        self.assertFalse((self.client / "msimg32.dll").exists())

    def test_existing_framework_reused_without_network_and_unknown_never_overwritten(self):
        dll = self.client / "msimg32.dll"
        dll.write_bytes(self.framework.read_bytes())
        self.installer.downloader = lambda path: self.fail("已有框架不能下载")
        self.installer.install(self.client, self.profile)
        dll.write_bytes(b"other framework")
        with self.assertRaisesRegex(ni.InstallError, "不同版本"):
            self.install()
        self.assertEqual(dll.read_bytes(), b"other framework")

    def test_transaction_restores_config_plugin_receipt_after_write_failure(self):
        self.install()
        paths = [self.plugin, self.app / ".state/netease-bridge.json", self.app / ".state/netease-install.json"]
        before = {path: path.read_bytes() for path in paths}
        original = ni.atomic_write
        def failing(path, data):
            if path == paths[2]:
                raise PermissionError("fixture permission failure")
            original(path, data)
        with patch.object(ni.NeteaseInstaller, "command", new_callable=PropertyMock,
                          return_value='"D:/new app/FloatingLyrics.exe" --netease --background'), \
                patch.object(ni, "atomic_write", side_effect=failing), self.assertRaises(PermissionError):
            self.install()
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)

    def test_first_install_failure_removes_only_created_files(self):
        original = ni.atomic_write
        def failing(path, data):
            if path == self.plugin:
                raise PermissionError("fixture permission failure")
            original(path, data)
        with patch.object(ni, "atomic_write", side_effect=failing), self.assertRaises(PermissionError):
            self.install()
        self.assertFalse((self.client / "msimg32.dll").exists())
        self.assertFalse(self.plugin.exists())
        self.assertFalse((self.app / ".state/netease-bridge.json").exists())

    def test_corrupted_token_and_unknown_plugin_not_overwritten(self):
        state = self.app / ".state"
        state.mkdir()
        config = state / "netease-bridge.json"
        config.write_text('{"token":"bad"}', encoding="utf-8")
        with self.assertRaisesRegex(ni.InstallError, "配置损坏"):
            self.install()
        self.assertEqual(config.read_text(encoding="utf-8"), '{"token":"bad"}')
        config.unlink()
        self.plugin.parent.mkdir(parents=True)
        self.plugin.write_bytes(b"unknown plugin")
        with self.assertRaisesRegex(ni.InstallError, "无法识别"):
            self.install()
        self.assertEqual(self.plugin.read_bytes(), b"unknown plugin")

    def test_uninstall_refuses_other_installation(self):
        self.install()
        self.installer.app_dir = self.app / "other"
        with self.assertRaisesRegex(ni.InstallError, "另一份"):
            self.installer.uninstall(self.client, self.profile)
        self.assertTrue(self.plugin.exists())

    def test_installer_window_keeps_failure_visible_and_allows_retry(self):
        args = SimpleNamespace(uninstall_netease=False, client_directory=self.client,
                               profile_directory=self.profile, framework_dll=self.framework, installer_elevated=False)
        window = InstallerWindow(self.installer, args)
        window.start()
        self.assertTrue(window.worker.wait(10000), "安装工作线程应在有界时间内完成")
        APP.processEvents()
        self.assertIn("安装完成", window.status.text())
        window.complete(None, PermissionError("目录无法写入"))
        self.assertIn("权限", window.status.text())
        self.assertFalse(window.admin.isHidden())
        window.close()

    def test_installer_remembers_chosen_paths_and_survives_corrupt_receipt(self):
        self.install()
        args = SimpleNamespace(uninstall_netease=True, client_directory=None, profile_directory=None,
                               framework_dll=None, installer_elevated=False)
        window = InstallerWindow(self.installer, args)
        self.assertEqual(Path(window.client.text()), self.client)
        self.assertEqual(Path(window.profile.text()), self.profile)
        window.close()
        (self.app / ".state/netease-install.json").write_text("[]", encoding="utf-8")
        window = InstallerWindow(self.installer, args)
        self.assertTrue(window.apply.isEnabled())
        window.close()

    def test_real_download_errors_have_retry_guidance(self):
        import urllib.error
        with patch.object(ni.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(ni.InstallError, "下载失败"):
                ni.download_framework(self.framework)


class ReleaseTests(unittest.TestCase):
    def test_upstream_license_bytes_match_provenance_and_survive_git_checkout(self):
        import hashlib
        directory = ROOT / "release/licenses"
        records = json.loads((directory / "sources.json").read_text(encoding="utf-8"))
        for record in records:
            if "file" in record:
                self.assertEqual(hashlib.sha256((directory / record["file"]).read_bytes()).hexdigest(), record["sha256"])
        result = subprocess.run(["git", "check-attr", "text", "whitespace", "--", "release/licenses/Qt-third-party.html"],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertIn(": text: unset", result.stdout)
        self.assertIn(": whitespace: unset", result.stdout)

    @unittest.skipUnless(os.name == "nt" and Path("C:/Program Files/NetEase/CloudMusic/cloudmusic.exe").is_file(), "本机网易云版本资源")
    def test_windows_version_resource_preserves_full_build_string(self):
        expected = subprocess.check_output(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "(Get-Item -LiteralPath 'C:\\Program Files\\NetEase\\CloudMusic\\cloudmusic.exe').VersionInfo.FileVersion"],
            text=True).strip()
        self.assertEqual(ni.file_version(Path("C:/Program Files/NetEase/CloudMusic/cloudmusic.exe")), expected)

    def test_public_zip_excludes_state_tokens_logs_and_development_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            (package / "_internal/plugins/netease").mkdir(parents=True)
            (package / "FloatingLyrics.exe").write_bytes(b"engine")
            (package / "_internal/python311.dll").write_bytes(b"runtime")
            for name in ("Qt6VirtualKeyboard.dll", "qtvirtualkeyboardplugin.dll", "Qt6Pdf.dll", "qpdf.dll"):
                (package / "_internal" / name).write_bytes(b"unused Qt plugin")
            for name in ("manifest.json", "adapter.js", "index.js"):
                (package / "_internal/plugins/netease" / name).write_bytes(b"template")
            (package / "_internal/plugins/netease/bridge-config.json").write_bytes(b"DO NOT PUBLISH THIS TOKEN")
            (package / ".state/fonts").mkdir(parents=True)
            (package / ".state/netease-bridge.json").write_text("DO NOT PUBLISH THIS TOKEN")
            (package / ".state/fonts/private.ttf").write_bytes(b"private font")
            (package / "debug.log").write_text("private logs")
            output = package_release(package, root / "output")
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertTrue(any(name.endswith("安装网易云联动.bat") for name in names))
                self.assertTrue(any(name.endswith("licenses/LGPL-3.0.txt") for name in names))
                self.assertFalse(any(".state" in name or "bridge-config" in name or name.endswith(".log") for name in names))
                self.assertFalse(any(Path(name).name in ("Qt6VirtualKeyboard.dll", "qtvirtualkeyboardplugin.dll", "Qt6Pdf.dll", "qpdf.dll") for name in names))
                self.assertFalse(any(b"DO NOT PUBLISH" in archive.read(name) for name in names))
            self.assertTrue(output.with_suffix(".zip.sha256").exists())

    def test_release_documentation_uses_real_repository_and_three_step_install(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        self.assertIn("Celine258/idea-from-limbus-company-dancing-lyrics", readme)
        self.assertIn("安装网易云联动.bat", readme)
        self.assertIn("3.1.41.205529", readme)
        self.assertTrue((ROOT / "LICENSE").read_text().startswith("MIT License"))
        self.assertIn("GPLv3", (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"))
        for name in ("安装网易云联动.bat", "卸载网易云联动.bat", "启动.bat"):
            script = (ROOT / "release" / name).read_text(encoding="utf-8")
            self.assertNotIn("python", script.lower())
            self.assertIn('cd /d "%~dp0"', script)
            self.assertIn("if errorlevel 1", script)
            self.assertIn("pause", script)


if __name__ == "__main__":
    unittest.main()
