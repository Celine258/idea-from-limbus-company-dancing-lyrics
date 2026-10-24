"""Release entry points exercise the frozen engine without controlling music."""
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch
from app_info import APP_VERSION, KUGOU_VERSION
from tools import validate_scramble_transitions

ROOT = Path(__file__).resolve().parents[1]


class ScrambleReleaseTests(unittest.TestCase):
    def test_diagnostic_dispatch_exits_before_normal_player_startup(self):
        arguments = [str(ROOT / "main.py"), "--scramble-smoke", "--scale", "1.25",
                     "--output", "中文 验证目录"]
        with patch.object(sys, "argv", arguments), patch.object(validate_scramble_transitions, "main", return_value=0) as run:
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(ROOT / "main.py"), run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        run.assert_called_once_with(arguments[2:])

    def test_diagnostic_accepts_scale_and_unicode_output_path(self):
        with patch.object(validate_scramble_transitions, "validate", return_value=0) as validate:
            result = validate_scramble_transitions.main(["--scale", "1.5", "--output", "中文 验证目录"])
        self.assertEqual(result, 0)
        validate.assert_called_once_with(Path("中文 验证目录"), 1.5)

    def test_all_current_guides_explain_scramble_fix_and_preserved_data(self):
        for name in ("README.md", "NETEASE.md", "QQMUSIC.md", "KUGOU.md", "release/使用说明.txt",
                     "release/netease/使用说明.txt", "release/qqmusic/使用说明.txt", "release/kugou-guide.txt",
                     "release/release-notes.md", "release/kugou-release-notes.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in (APP_VERSION, "乱码退场", "切句", "分批", "保留"):
                self.assertIn(phrase, text, name)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"releases/download/v{KUGOU_VERSION}/dancing-lyrics-{KUGOU_VERSION}-windows-x64.zip", readme)
