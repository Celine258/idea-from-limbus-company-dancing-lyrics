"""Documentation must distinguish the new source fix from existing public ZIPs."""
import json
from pathlib import Path
import unittest
from PySide6.QtGui import QImageReader

ROOT = Path(__file__).resolve().parents[1]


class DisplayFixDeliveryTests(unittest.TestCase):
    def test_instructions_and_scope_are_explicit_and_images_decode(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("默认 6 秒", "0–120 秒", "0 表示不额外限制", "包含入场及退场",
                       "切换效果预设不会重置", "没有明确纯音乐提示", "预加载下一句",
                       "本版修复", "三个 Windows 下载包"):
            self.assertIn(phrase, readme)
        for name in ("display-deadline-release.png", "long-entrance-frames.png"):
            image = QImageReader(str(ROOT / "docs/images" / name)).read()
            self.assertFalse(image.isNull())
            self.assertGreaterEqual(image.width(), 900)
            self.assertGreaterEqual(image.height(), 700)

    def test_actual_reports_keep_native_synthetic_and_real_client_evidence_separate(self):
        data = json.loads((ROOT / "docs/research/display-deadlines-20261024.json").read_text(encoding="utf-8"))
        self.assertTrue(data["passed"])
        self.assertEqual(data["scope"], "source_changes_not_packaged_or_published")
        self.assertTrue(data["automatic_tests"]["passed"])
        self.assertEqual(data["automatic_tests"]["count"], 489)
        self.assertTrue(data["actual_source_bat"]["native_window_visible"])
        self.assertTrue(data["actual_source_bat"]["boolean_checks_passed"])
        self.assertTrue(data["actual_source_bat"]["force_source"])
        self.assertEqual(data["max_display_seconds"]["default"], 6)
        self.assertTrue(all(data["windows_smoke"]["boolean_checks"].values()))
        native = data["native_layout_and_synthetic_animation"]
        self.assertEqual([row["dpr"] for row in native], [1, 1.25, 1.5])
        for row in native:
            self.assertTrue(row["passed"] and all(row["checks"].values()))
            self.assertTrue(row["synthetic_lyric_times"])
            self.assertFalse(row["real_playback"])
            self.assertEqual(row["music_client_commands"], 0)
            self.assertEqual(len(row["measurements"]), 4)
            for result in row["measurements"]:
                self.assertLessEqual(result["warm_render_p95_ms"], 33)
        real = data["real_kugou"]
        self.assertTrue(real["passed"] and all(real["checks"].values()))
        self.assertFalse(real["simulated_live_data"] or real["packaged"])
        self.assertEqual(real["playback_commands"], 0)
        for item in ("public_release_updated", "real_netease_this_change", "real_qq_music_this_change", "real_iron_lotus_entrance"):
            self.assertIn(item, data["not_verified"])
