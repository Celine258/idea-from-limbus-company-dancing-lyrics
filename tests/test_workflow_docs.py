"""Validate the deliverable documentation and the source-control boundary."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = tuple(ROOT / name for name in ("AGENTS.md", "CHANGELOG.md", "README.md", "验证记录.md"))


class WorkflowDocumentationTests(unittest.TestCase):
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
                   "dist/probe.txt", "artifacts/probe.txt", "__pycache__/probe.pyc"]
        sources = ["AGENTS.md", "CHANGELOG.md", "main.py", "controls.py", "validation.py",
                   "assets/app.ico", "tests/test_controls.py", "tests/test_workflow_docs.py"]
        result = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "check-ignore", "--no-index", "--stdin", "-z"],
            cwd=ROOT, input="\0".join(ignored + sources) + "\0", text=True,
            encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.rstrip("\0").split("\0")), set(ignored))


if __name__ == "__main__":
    unittest.main()
