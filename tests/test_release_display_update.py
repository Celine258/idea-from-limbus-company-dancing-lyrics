"""The Windows downloads must advertise the fixes included in this release."""
import hashlib
import json
from pathlib import Path
import unittest
from app_info import APP_VERSION, KUGOU_VERSION

ROOT = Path(__file__).resolve().parents[1]


class DisplayUpdateReleaseTests(unittest.TestCase):
    def test_published_packages_and_native_results_match_exact_runtime(self):
        record = json.loads((ROOT / "docs/research/display-release-20261024.json").read_text(encoding="utf-8"))
        self.assertTrue(record["passed"] and record["same_engine"])
        self.assertEqual(record["versions"], {"shared": "0.8.0-beta.2", "kugou": "0.8.0-beta.2-kugou.1"})
        self.assertEqual({row["player"] for row in record["archives"]}, {"netease", "qqmusic", "kugou"})
        self.assertEqual(len({row["exe_sha256"] for row in record["archives"]}), 1)
        assets = {row["name"]: row for row in record["public_downloads"]["assets"]}
        self.assertEqual(len(assets), 6)
        for package in record["archives"]:
            row = assets[package["name"]]
            self.assertEqual(row["anonymous_head_status"], 200)
            self.assertTrue(row["server_digest_matches"])
            self.assertEqual(row["sha256"], package["sha256"])
            self.assertEqual(row["tag_commit"], record["runtime_source_commit"])
        self.assertTrue(record["frozen_lifetime_control"]["passed"])
        self.assertTrue(record["personal_data"]["settings_fonts_presets_unchanged"])
        live = record["kugou_real_background"]
        self.assertTrue(live["passed"] and live["actual_bat_entry"] and live["packaged"])
        self.assertFalse(live["simulated_live_data"])
        self.assertEqual(live["playback_commands"], 0)
        self.assertFalse(record["kugou_initial_attempt"]["passed"])
        self.assertFalse(record["kugou_initial_attempt"]["runtime_changed_between_attempts"])
        self.assertTrue(record["kugou_initial_attempt"]["retry_passed"])
        self.assertIn("frozen_positive_netease_install_this_release", record["not_verified"])

    def test_all_player_guides_explain_deadline_migration_and_independence(self):
        for name in ("README.md", "NETEASE.md", "QQMUSIC.md", "KUGOU.md", "release/使用说明.txt",
                     "release/netease/使用说明.txt", "release/qqmusic/使用说明.txt", "release/kugou-guide.txt",
                     "release/release-notes.md", "release/kugou-release-notes.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in ("默认 6 秒", "0–120 秒", "不额外限制", "退场", "长句", "预设"):
                self.assertIn(phrase, text, name)
        self.assertTrue(KUGOU_VERSION.startswith(APP_VERSION))
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+-beta\.\d+$")

    def test_shared_engine_dependencies_ship_exact_license_bytes(self):
        records = json.loads((ROOT / "release/licenses/sources.json").read_text(encoding="utf-8"))
        for name in ("winrt-runtime", "winrt-Windows.Media.Control", "winrt-Windows.Media.Ocr", "pefile", "typing_extensions"):
            found = [row for row in records if row.get("distribution") == name]
            self.assertTrue(found, name)
            for row in found:
                self.assertEqual(hashlib.sha256((ROOT / "release/licenses" / row["file"]).read_bytes()).hexdigest(), row["sha256"])
