"""Extended lifetimes are independent of cue transitions and the song clock."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
import runpy
import sys
import json
from unittest.mock import patch
from animation import _glyph_layout
from glyph_motion import glyph_states
from lrc import LyricDocument, LyricLine, TimedWord, LyricTimeline, parse_lrc, display_document
from settings import Preferences, SettingsStore, ANIMATION_STYLES
from presets import EFFECT_KEYS
from overlay import LyricsOverlay
import test_controls as controls_fixture
from test_prepared_entrance import Player, APP


class ExtendedTimelineTests(unittest.TestCase):
    def test_native_evidence_and_usage_explain_limits(self):
        root = Path(__file__).resolve().parents[1]
        record = json.loads((root / "docs/research/extended-display-20261030.json").read_text(encoding="utf-8"))
        self.assertTrue(record["passed"])
        self.assertFalse(record["default_enabled"] or record["real_playback_verified"])
        self.assertEqual(record["maximum_simultaneous_blocks"], 4)
        self.assertEqual([row["dpr"] for row in record["reports"]], [1, 1.25, 1.5])
        for report in record["reports"]:
            self.assertTrue(all(report["checks"].values()))
            self.assertTrue(report["synthetic_lyric_times"])
            self.assertEqual(len(report["measurements"]), 5)
            self.assertLessEqual(max(row["warm_render_p95_ms"] for row in report["measurements"]), 33)
        readme = (root / "README.md").read_text(encoding="utf-8")
        for text in ("新句出现后保留旧句", "1–120 秒", "四组", "独占全屏"):
            self.assertIn(text, readme)

    def test_packaged_diagnostic_dispatch_does_not_start_a_music_client(self):
        from tools import validate_extended_display
        arguments = ["main.py", "--display-smoke", "--scale", "1.5", "--output", "中文 测试"]
        with patch.object(sys, "argv", arguments), patch.object(validate_extended_display, "main", return_value=0) as run:
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"), run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        run.assert_called_once_with(arguments[2:])

    def test_old_settings_default_off_and_new_ranges_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            path.write_text("[General]\nmax_display_seconds=9\n", encoding="utf-8")
            prefs = SettingsStore(path).load()
            self.assertFalse(prefs.extended_display)
            self.assertEqual((prefs.extended_display_seconds, prefs.max_display_seconds), (10, 9))
            for raw, expected in ((-3, 1), (10, 10), (300, 120)):
                prefs.extended_display, prefs.extended_display_seconds = True, raw
                SettingsStore(path).save(prefs)
                loaded = SettingsStore(path).load()
                self.assertTrue(loaded.extended_display)
                self.assertEqual(loaded.extended_display_seconds, expected)
        self.assertTrue(set(EFFECT_KEYS).isdisjoint(("extended_display", "extended_display_seconds")))

    def test_every_animation_outlives_next_cue_and_ignores_old_cap(self):
        document = parse_lrc("[00:01]第一句\n[00:03]第二句\n[00:20]第三句")
        for style in ANIMATION_STYLES:
            for scramble in (False, True):
                with self.subTest(style=style, scramble=scramble):
                    timeline = LyricTimeline(document, animation_style=style, scramble_exit=scramble,
                                             max_display_ms=1000, extended_display_ms=10000)
                    items = timeline.visible(9500, 50000)
                    self.assertEqual([item.index for item in items], [0, 1])
                    first = items[0]
                    self.assertEqual((first.start_ms, first.end_ms, first.exit_start_ms), (1000, 11000, 10400))
                    self.assertEqual([item.index for item in timeline.visible(11000, 50000)], [1])
                    self.assertEqual(timeline.visible(9500, 50000), items)  # Seek/repeat, no accumulated state.
        self.assertFalse(LyricTimeline(document, max_display_ms=1000).visible(9500, 50000))

    def test_density_caps_four_with_exit_before_fifth_and_blank_or_end_clears(self):
        document = LyricDocument([LyricLine(i * 1000, str(i)) for i in range(8)] + [LyricLine(9000, "")], [])
        timeline = LyricTimeline(document, extended_display_ms=120000)
        first = timeline.visible(3800)[0]
        self.assertEqual(first.end_ms, 4000)
        self.assertLess(first.exit_start_ms, 3800)
        for position in range(0, 10001, 37):
            self.assertLessEqual(len(timeline.visible(position)), 4)
        self.assertEqual([item.index for item in timeline.visible(4000)], [1, 2, 3, 4])
        self.assertFalse(timeline.visible(9000))
        self.assertFalse(timeline.visible(8500, 8500))
        self.assertFalse(timeline.visible(7000, 5000))

    def test_vocal_end_does_not_truncate_hold_and_offsets_apply_once(self):
        word = TimedWord(1000, 2000, 0, 1)
        document = LyricDocument([LyricLine(1000, "词", (word,), end_ms=2000), LyricLine(4000, "")], [], offset_ms=100)
        timeline = LyricTimeline(document, delay_ms=300, extended_display_ms=10000)
        item = timeline.visible(3000)[0]
        self.assertEqual((item.start_ms, item.end_ms), (1200, 4200))
        self.assertEqual((item.words[0].start_ms, item.words[0].end_ms), (1200, 2200))
        self.assertFalse(timeline.visible(4200))

    def test_unknown_last_line_is_finite_and_small_lifetimes_compress(self):
        document = parse_lrc("[00:01]末句")
        for style in ANIMATION_STYLES:
            timeline = LyricTimeline(document, animation_style=style, entry_speed=25, exit_speed=25,
                                     extended_display_ms=1000)
            item = timeline.visible(1500)[0]
            self.assertEqual((item.entry_end_ms, item.exit_start_ms, item.end_ms), (1350, 1700, 2000))
            self.assertFalse(timeline.visible(2000))
            self.assertFalse(timeline.visible(1800, 1800))
        self.assertTrue(LyricTimeline(document, extended_display_ms=10000).visible(8000))
        self.assertFalse(LyricTimeline(document, extended_display_ms=10000).visible(11000))

    def test_bilingual_is_one_block_and_glyph_exit_is_stateless(self):
        doc = display_document(LyricDocument([LyricLine(0, "Café 😀", translation="都市回响")], []),
                               mode="bilingual_original")
        for style in ANIMATION_STYLES:
            prefs = Preferences(animation_style=style, scramble_exit=True)
            timeline = LyricTimeline(doc, animation_style=style, scramble_exit=True, extended_display_ms=10000)
            item = timeline.visible(9600)[0]
            self.assertGreater(item.secondary_start, 0)
            glyphs, _, _ = _glyph_layout(item.text, 32, 600, secondary_start=item.secondary_start)
            earlier = glyph_states(glyphs, prefs, item, 9450, .5, 32, 70)
            later = glyph_states(glyphs, prefs, item, 9999, .5, 32, 70)
            self.assertGreater(sum(s.opacity for s in earlier), sum(s.opacity for s in later))
            self.assertEqual(earlier, glyph_states(glyphs, prefs, item, 9450, .5, 32, 70))
            self.assertFalse(timeline.visible(10000))

    def test_cold_seek_prepares_newest_active_before_old_history_or_future(self):
        player = Player()
        prefs = Preferences(extended_display=True, extended_display_seconds=120, region="full")
        overlay = LyricsOverlay(player, prefs)
        overlay.set_document(parse_lrc("[00:00]甲\n[00:01]乙\n[00:02]丙\n[00:03]丁\n[00:08]戊"))
        player.clock = 3500
        overlay.show()
        order = []
        def prepare(index, line):
            order.append(index)
            yield None
        try:
            with patch.object(overlay, "_prepare_line", side_effect=prepare):
                overlay._prepare_lines(overlay.timeline.visible(3500), 3500)
            overlay._warm_step()
            self.assertEqual(order, [3, 2, 1, 0, 4])
            self.assertEqual(overlay._warm_priority[3], 0)
            self.assertEqual(overlay._warm_priority[4], 4)
            self.assertLessEqual(len(overlay.layouts) + len(overlay._warm_jobs), 5)
            self.assertEqual(player.clock, 3500)
        finally:
            overlay.hide(); overlay.deleteLater()


class ExtendedControlTests(unittest.TestCase):
    setUp = controls_fixture.ControlPanelTests.setUp
    tearDown = controls_fixture.ControlPanelTests.tearDown

    def test_mode_saves_controls_and_presets_preserve_it_without_transport(self):
        self.player.clock, self.player.playing = 6500, True
        self.assertFalse(self.panel.spins["extended_display_seconds"].isEnabled())
        self.panel.extended_checkbox.setChecked(True)
        self.panel.spins["extended_display_seconds"].setValue(20)
        self.assertFalse(self.panel.spins["max_display_seconds"].isEnabled())
        self.assertTrue(self.panel.spins["extended_display_seconds"].isEnabled())
        self.panel.apply_preset("builtin:quiet")
        loaded = self.store.load()
        self.assertEqual((loaded.extended_display, loaded.extended_display_seconds, loaded.max_display_seconds), (True, 20, 6))
        self.assertEqual(self.panel.font_preview._preview_item().end_ms, 20000)
        self.panel.extended_checkbox.setChecked(False)
        self.assertTrue(self.panel.spins["max_display_seconds"].isEnabled())
        self.assertFalse(self.store.load().extended_display)
        self.assertEqual((self.player.clock, self.player.playing, self.player.seeks), (6500, True, []))

    def test_new_controls_are_reachable_at_minimum_window_and_preview_stops_hidden(self):
        self.panel.resize(900, 560)
        self.panel.nav_buttons[1].click()
        self.panel.extended_checkbox.setChecked(True)
        self.panel.font_preview.replay()
        for control in (self.panel.extended_checkbox, self.panel.spins["extended_display_seconds"]):
            self.panel.effects_scroll.ensureWidgetVisible(control, 0, 20)
            APP.processEvents()
            self.assertFalse(control.visibleRegion().isEmpty())
        self.panel.nav_buttons[0].click()
        APP.processEvents()
        self.assertFalse(self.panel.font_preview.timer.isActive())
