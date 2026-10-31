"""Keep downloadable binaries and the actual local upgrade distinct from fixtures."""
import json
from pathlib import Path
import unittest
from PySide6.QtGui import QImageReader

ROOT = Path(__file__).resolve().parents[1]


class PauseReleaseTests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT / "docs/research/pause-release-20261101.json").read_text(encoding="utf-8"))

    def test_all_three_public_packages_use_verified_runtime_and_prerelease_tags(self):
        record = self.record()
        self.assertTrue(record["passed"] and record["same_engine"] and record["public_packages_updated"])
        self.assertEqual(record["versions"], dict(shared="0.8.0-beta.5", kugou="0.8.0-beta.5-kugou.1"))
        self.assertEqual(len(record["releases"]), 2)
        for release in record["releases"]:
            self.assertTrue(release["prerelease"])
            self.assertEqual(release["commit"], record["runtime_source_commit"])
        public = {asset["name"]: asset for asset in record["public_downloads"]["assets"]}
        self.assertEqual(len(public), 6)
        self.assertEqual({row["player"] for row in record["archives"]}, {"netease", "qqmusic", "kugou"})
        self.assertEqual(len({row["exe_sha256"] for row in record["archives"]}), 1)
        for row in record["archives"]:
            self.assertTrue(row["crc"] and row["private_files_excluded"] and row["qt_runtime_complete"])
            self.assertTrue(row["license_bytes_verified"] and row["developer_path_removed"])
            for name in (row["name"], row["name"] + ".sha256"):
                self.assertEqual(public[name]["anonymous_head_status"], 200)
                self.assertEqual(public[name]["tag_commit"], record["runtime_source_commit"])
            self.assertEqual(public[row["name"]]["sha256"], row["sha256"])
            self.assertEqual(public[row["name"]]["bytes"], row["bytes"])
            native = row["native_pause"]
            self.assertTrue(native["passed"] and native["packaged"] and all(native["checks"].values()))
            self.assertTrue(native["synthetic_source_packets"])
            self.assertFalse(native["real_client_pause_verified"])
        self.assertEqual(sorted(row["smoke_checks"] for row in record["archives"] if row["smoke_checks"]), [75, 75])
        self.assertEqual(sum(len(row["native_pause"]["checks"]) for row in record["archives"]), 129)

    def test_local_paths_settings_and_manual_toggle_preserved_without_live_claim(self):
        record = self.record()
        local = record["installed"]
        self.assertTrue(local["passed"] and local["old_setting_values_unchanged"])
        self.assertTrue(local["fonts_presets_and_bridge_files_unchanged"])
        self.assertEqual(len(local["upgrades"]), 3)
        self.assertEqual(local["profiles_preserved"], 2)
        for row in local["upgrades"]:
            self.assertTrue(row["path_preserved"] and row["backup_available"])
            self.assertEqual(row["exe_sha256"], record["archives"][0]["exe_sha256"])
        ui = record["installed_ui"]
        self.assertTrue(ui["passed"] and ui["native_option_present"] and ui["toggle_works"])
        self.assertTrue(ui["original_option_restored"])
        self.assertEqual(ui["exe_sha256"], record["archives"][0]["exe_sha256"])
        for name in ("qq_entries", "kugou_entries"):
            self.assertTrue(record[name]["passed"] and all(record[name]["checks"].values()))
        self.assertIn("three_real_clients_manual_pause_resume", record["not_verified"])
        self.assertEqual(record["music_client_commands"], 0)
        self.assertFalse(record["real_client_pause_verified"])
        self.assertNotIn("running_before", local)
        self.assertFalse(QImageReader(str(ROOT / "docs/images/pause-display-beta5.png")).read().isNull())
        self.assertIn("pause-release-20261101.json", (ROOT / "README.md").read_text(encoding="utf-8"))
