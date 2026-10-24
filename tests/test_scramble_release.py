"""Release entry points exercise the frozen engine without controlling music."""
from pathlib import Path
import json
import runpy
import sys
import unittest
from unittest.mock import patch
from app_info import APP_VERSION, KUGOU_VERSION
from tools import validate_scramble_transitions

ROOT = Path(__file__).resolve().parents[1]


class ScrambleReleaseTests(unittest.TestCase):
    def test_beta3_public_evidence_matches_frozen_engine_and_preserves_scope(self):
        record = json.loads((ROOT / "docs/research/scramble-release-20261024.json").read_text(encoding="utf-8"))
        self.assertTrue(record["passed"] and record["same_engine"] and record["public_packages_updated"])
        self.assertEqual(record["versions"], {"shared": "0.8.0-beta.3", "kugou": "0.8.0-beta.3-kugou.1"})
        self.assertEqual(len({row["exe_sha256"] for row in record["archives"]}), 1)
        assets = {row["name"]: row for row in record["public_downloads"]["assets"]}
        self.assertEqual(len(assets), 6)
        for archive in record["archives"]:
            asset = assets[archive["name"]]
            self.assertEqual(asset["sha256"], archive["sha256"])
            self.assertEqual(asset["bytes"], archive["bytes"])
            self.assertEqual(asset["anonymous_head_status"], 200)
            self.assertEqual(asset["tag_commit"], record["runtime_source_commit"])
        native = record["frozen_scramble_transitions"]
        self.assertTrue(native["packaged"] and native["developer_path_removed"] and native["passed"])
        self.assertTrue(native["synthetic_clock"])
        self.assertFalse(native["real_music_playback_verified"])
        self.assertTrue(all(native["checks"].values()))
        for measurement in native["measurements"]:
            self.assertLessEqual(measurement["paint_p95_ms"], 33)
            self.assertLessEqual(measurement["preparation_max_ms"], 33)
            self.assertGreaterEqual(min(measurement["transition_exit_frames"]), 5)
        self.assertTrue(record["personal_data"]["settings_fonts_presets_unchanged"])
        self.assertFalse(record["personal_data"]["installed_executables_replaced"])
        self.assertIn("new_real_netease_qq_kugou_playback", record["not_verified"])
        from PySide6.QtGui import QImageReader
        screenshot = QImageReader(str(ROOT / "docs/images/scramble-release-beta3.png")).read()
        self.assertFalse(screenshot.isNull())
        self.assertGreaterEqual(screenshot.width(), 900)

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
