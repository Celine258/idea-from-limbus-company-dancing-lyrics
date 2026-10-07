"""User-tunable animation timing, deterministic motion and reserved bounds."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication
from animation import build_layout, display_regions
from glyph_motion import glyph_states, noise
from lrc import ActiveLine, LyricTimeline, parse_lrc
from settings import Preferences, SettingsStore
from text_effects import TextEffects, pixels_view
from tests.test_glyph_motion import rectangles

APP = QApplication.instance() or QApplication([])


class EffectParameterTests(unittest.TestCase):
    def test_old_configuration_defaults_and_new_values_round_trip_and_clamp(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.ini")
            self.assertEqual((store.load().entry_speed, store.load().exit_speed, store.load().shake_frequency,
                              store.load().fall_distance), (100, 100, 6, 48))
            prefs = Preferences(entry_speed=25, exit_speed=300, shake_frequency=15, fall_distance=128)
            store.save(prefs)
            self.assertEqual(store.load(), prefs)
            for key, value in (("entry_speed", 0), ("exit_speed", 999), ("shake_frequency", -1), ("fall_distance", 999)):
                store.store.setValue(key, value)
            loaded = store.load()
            self.assertEqual((loaded.entry_speed, loaded.exit_speed, loaded.shake_frequency, loaded.fall_distance),
                             (25, 300, 1, 128))

    def test_speed_scales_classic_and_staggered_stages_without_changing_default(self):
        doc = parse_lrc("[00:01]甲乙丙\n[00:05]下一句\n[00:12]结束")
        for style in ("classic", "ripple_wave", "fall_shake"):
            slow = LyricTimeline(doc, animation_style=style, entry_speed=50, exit_speed=50)
            fast = LyricTimeline(doc, animation_style=style, entry_speed=200, exit_speed=200)
            if style == "classic":
                self.assertLess(slow.visible(1100)[0].opacity, fast.visible(1100)[0].opacity)
            else:
                self.assertGreater(slow.visible(1100)[0].entry_end_ms, fast.visible(1100)[0].entry_end_ms)
            self.assertGreater(slow.visible(5100)[0].end_ms, fast.visible(5100)[0].end_ms)
            baseline = LyricTimeline(doc, animation_style=style)
            explicit = LyricTimeline(doc, animation_style=style, entry_speed=100, exit_speed=100)
            self.assertEqual(baseline.visible(1200), explicit.visible(1200))

    def test_extreme_slow_dense_and_blank_or_end_boundaries_leave_no_residue(self):
        doc = parse_lrc("[00:01]甲\n[00:01.100]乙\n[00:01.200]\n[00:03]丙")
        timeline = LyricTimeline(doc, animation_style="fall_wave", entry_speed=25, exit_speed=25)
        self.assertEqual(timeline.visible(1010)[0].entry_end_ms, 1035)
        for time in range(1000, 1210):
            self.assertLessEqual(len(timeline.visible(time)), 2)
        self.assertEqual(timeline.visible(1200), [])
        self.assertEqual(timeline.visible(3500, 3500), [])

    def test_frequency_uses_the_same_deterministic_samples_and_zero_distance_still_fades(self):
        self.assertEqual(noise(7, 2, 1, .25, 12), noise(7, 2, 1, .5, 6))
        glyphs = rectangles()
        item = ActiveLine(0, "", 0, 3800, 1, 700, 3200)
        prefs = Preferences(animation_style="fall_shake", jump=0, fall_distance=0)
        states = glyph_states(glyphs, prefs, item, 3450, 0, 32)
        self.assertEqual(states[0].y, glyphs[0].baseline)
        self.assertLess(states[0].opacity, 1)
        prefs.fall_distance = 128
        self.assertGreater(glyph_states(glyphs, prefs, item, 3450, 0, 64)[0].y, states[0].y + 50)

    def test_maximum_fall_and_shake_reserve_visible_glow_at_all_scales(self):
        prefs = Preferences(animation_style="fall_shake", fall_distance=128, jump=30, angle=25)
        regions = display_regions(1280, 900, "edges")
        layout = build_layout("歌词试验 Hello", 730, regions, [], prefs)
        self.assertIsNotNone(layout)
        self.assertTrue(any(region.contains(layout.bounds) for region in regions))
        for dpr in (1, 1.25, 1.5):
            renderer = TextEffects()
            surface = renderer.prepare(layout.glyphs, layout.font_size, prefs, dpr, prefs.jump, layout.angle)
            for position in (3400, 3550, 3799):
                states = glyph_states(layout.glyphs, prefs, ActiveLine(0, "", 0, 3800, 1, 700, 3200),
                                      position, 1, layout.font_size, 730, layout.angle)
                renderer.render(surface, prefs, states=states)
                alpha = pixels_view(surface.image)[:, :, 3]
                self.assertFalse(alpha[0].any() or alpha[-1].any() or alpha[:, 0].any() or alpha[:, -1].any())


if __name__ == "__main__":
    unittest.main()
