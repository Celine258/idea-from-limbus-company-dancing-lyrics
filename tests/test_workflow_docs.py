"""Validate the deliverable documentation and the source-control boundary."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = tuple(ROOT / name for name in ("AGENTS.md", "CHANGELOG.md", "README.md", "验证记录.md", "NETEASE.md",
                                         "产品设计方案.md", "技术文档.md", "THIRD_PARTY_NOTICES.md",
                                         "docs/传播文案.md", "release/release-notes.md"))


class WorkflowDocumentationTests(unittest.TestCase):
    def test_brand_name_and_existing_plugin_identity(self):
        from app_info import APP_NAME
        self.assertEqual(APP_NAME, "都市回响")
        self.assertTrue((ROOT / "README.md").read_text(encoding="utf-8").startswith(f"# {APP_NAME}\n"))
        manifest = json.loads((ROOT / "plugins/netease/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], APP_NAME)
        self.assertEqual(manifest["slug"], "floating-lyrics", "改名不能变成另一个安装实例")
        launcher = (ROOT / "start.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("".join(f"\\u{ord(char):04x}" for char in APP_NAME), launcher,
                      "原生启动器必须匹配新窗口名称")

    def test_readme_embeds_desktop_recording_before_download_link(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        image = re.search(r"!\[([^\]]+)\]\((docs/images/lyrics-demo\.gif)\)", text)
        self.assertIsNotNone(image, "首页需要内嵌演示，而不是只提供文件链接")
        self.assertIn("实机演示", image.group(1))
        self.assertLess(image.start(), text.index("下载 Windows x64 试用版"))
        self.assertTrue((ROOT / image.group(2)).is_file())

    def test_readme_gif_decodes_complete_recording_and_loops(self):
        from PySide6.QtGui import QImageReader

        path = ROOT / "docs/images/lyrics-demo.gif"
        self.assertLess(path.stat().st_size, 8 * 1024 * 1024, "避免首页演示文件过大")
        reader = QImageReader(str(path))
        self.assertTrue(reader.supportsAnimation())
        self.assertEqual(reader.loopCount(), -1, "演示需要无限循环播放")
        count = reader.imageCount()
        self.assertGreater(count, 100, "必须保留完整动画，不能退化为静态图片")
        width, height = reader.size().width(), reader.size().height()
        self.assertGreaterEqual(width, 640)
        self.assertLessEqual(width, 1280)
        self.assertAlmostEqual(width / height, 16 / 9)
        duration = 0
        frame_hashes = set()
        for frame in range(count):
            decoded = reader.read()
            self.assertFalse(decoded.isNull(), f"第 {frame} 帧解码失败：{reader.errorString()}")
            self.assertEqual((decoded.width(), decoded.height()), (width, height))
            delay = reader.nextImageDelay()
            self.assertGreater(delay, 0)
            duration += delay
            frame_hashes.add(hashlib.sha256(decoded.constBits()).digest())
        self.assertGreaterEqual(duration, 18_000)
        self.assertLessEqual(duration, 19_000)
        self.assertGreater(len(frame_hashes), 10, "录屏需要有实际画面变化")

    def test_current_guides_describe_all_themes_and_runtime_icon_scope(self):
        from app_info import APP_VERSION
        for name in ("README.md", "NETEASE.md", "产品设计方案.md", "技术文档.md"):
            with self.subTest(document=name):
                text = (ROOT / name).read_text(encoding="utf-8-sig")
                self.assertIn(APP_VERSION, text)
                for theme in ("默认主题", "深色主题", "特殊主题", "但丁钟头", "托盘"):
                    self.assertIn(theme, text)
        guide = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        self.assertIn("EXE 文件图标仍为原图标", guide)
        self.assertIn("固定快捷方式由 Windows 管理", guide)

    @unittest.skipUnless(shutil.which("powershell.exe"), "Windows 启动脚本语法验证")
    def test_launcher_diagnostic_wait_is_bounded_and_powershell_syntax_valid(self):
        script = ROOT / "start.ps1"
        text = script.read_text(encoding="utf-8-sig")
        self.assertIn("$taskWatch.ElapsedMilliseconds -lt 30000", text)
        self.assertIn("$taskSmokeWatch.ElapsedMilliseconds -lt 120000", text)
        self.assertIn("$taskProcess.WaitForExit(1000)", text)
        command = ("$taskTokens=$null;$taskErrors=$null;"
                   f"[System.Management.Automation.Language.Parser]::ParseFile('{str(script).replace(chr(39), chr(39)*2)}',"
                   "[ref]$taskTokens,[ref]$taskErrors)|Out-Null;"
                   "if($taskErrors.Count){$taskErrors|Out-String;exit 1}")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_documents_are_readable_and_local_links_resolve(self):
        for path in DOCUMENTS:
            with self.subTest(document=path.name):
                text = path.read_bytes().decode("utf-8-sig", errors="strict")
                self.assertTrue(text.startswith("# "))
                self.assertNotIn("\x00", text)
                self.assertNotIn("\ufffd", text)
                self.assertEqual(text.count("```") % 2, 0, "代码围栏必须配对")
                for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                    if "://" in target or target.startswith("#"):
                        continue
                    destination = (path.parent / target.split("#", 1)[0]).resolve()
                    self.assertTrue(destination.is_relative_to(ROOT), target)
                    self.assertTrue(destination.is_file(), f"失效的文件链接：{target}")

    def test_changelog_entries_have_date_details_validation_and_impact(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        entries = re.split(r"(?m)^## ", text)[1:]
        self.assertTrue(entries, "需要至少一条变更记录")
        for entry in entries:
            self.assertRegex(entry.splitlines()[0], r"^\d{4}-\d{2}-\d{2}[：:]\S")
            sections = {heading: body for heading, body in re.findall(
                r"(?ms)^### ([^\n]+)\n(.*?)(?=^### |\Z)", entry)}
            for heading in ("改动", "测试与验证", "影响与限制"):
                self.assertIn(heading, sections)
                self.assertTrue(sections[heading].strip(), f"{heading}不能为空")

    def test_runtime_files_ignored_and_source_files_trackable(self):
        ignored = [".venv/probe.txt", ".state/probe.txt", "build/probe.txt",
                   "dist/probe.txt", "artifacts/probe.txt", "__pycache__/probe.pyc", "debug.log"]
        sources = ["AGENTS.md", "CHANGELOG.md", "main.py", "controls.py", "validation.py", "themes.py", "app_info.py",
                   "assets/app.ico", "assets/check-white.svg", "assets/dante-clock.svg", "assets/special-blueprint.svg",
                   "tests/test_controls.py", "tests/test_workflow_docs.py"]
        result = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "check-ignore", "--no-index", "--stdin", "-z"],
            cwd=ROOT, input="\0".join(ignored + sources) + "\0", text=True,
            encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.rstrip("\0").split("\0")), set(ignored))


if __name__ == "__main__":
    unittest.main()
