"""Cold exit materials must not block a long sentence's entrance frames."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import unittest
from unittest.mock import patch
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from animation import _glyph_layout, build_layout, build_layout_steps, display_regions
from lrc import LyricTimeline, parse_lrc
from settings import Preferences
from glyph_motion import glyph_states
from overlay import LyricsOverlay
from text_effects import TextEffects, pixels_view

APP = QApplication.instance() or QApplication([])
LONG_TEXT = "In the quiet city we follow every echo through the night and find another morning."


class Player(QObject):
    changed, discontinuity = Signal(), Signal()
    playing, ended, duration, clock = False, False, 50000, 0
    def position(self):
        return self.clock
    def energy_at(self, _):
        return .5


class PreparedEntranceTests(unittest.TestCase):
    def test_paint_only_schedules_layout_even_at_a_cold_song_transition(self):
        player = Player()
        prefs = Preferences(font_size=64, animation_style="ripple_wave", scramble_exit=True,
                            glow_variant="gradient")
        overlay = LyricsOverlay(player, prefs)
        overlay.set_document(parse_lrc("[00:00]" + LONG_TEXT + "\n[00:02]" + LONG_TEXT + " again"))
        overlay.show()
        try:
            # Neither the old nor the upcoming cue may fit fonts inside paint.
            with patch("animation._glyph_layout", side_effect=AssertionError("layout blocked paint")):
                overlay.grab()
                player.clock = 2100
                overlay.grab()
            self.assertTrue(overlay._warm_jobs)
            self.assertFalse(overlay.layouts)
            self.assertEqual(player.clock, 2100)
            player.discontinuity.emit()
            self.assertFalse(overlay._warm_jobs)
        finally:
            overlay.hide()
            overlay.deleteLater()

    def test_layout_fitting_yields_without_changing_font_positions_or_collision_rules(self):
        prefs = Preferences(font_size=64, animation_style="ripple_wave", angle=12)
        regions = display_regions(1280, 720, "edges")
        expected = build_layout(LONG_TEXT, 730, regions, [], prefs)
        steps = build_layout_steps(LONG_TEXT, 730, regions, [], prefs)
        actual = None
        attempts = 0
        with patch("animation._glyph_layout", wraps=_glyph_layout) as fits:
            for ready in steps:
                # At most one complete font-fit attempt per resumable step.
                self.assertLessEqual(fits.call_count - attempts, 1)
                attempts = fits.call_count
                if ready is not None:
                    actual = ready
        self.assertGreater(attempts, 1)
        self.assertEqual((actual.font_size, actual.center, actual.bounds, actual.angle),
                         (expected.font_size, expected.center, expected.bounds, expected.angle))
        self.assertEqual([(g.x, g.baseline, g.path) for g in actual.glyphs],
                         [(g.x, g.baseline, g.path) for g in expected.glyphs])

    def test_base_material_preparation_yields_before_processing_the_whole_sentence(self):
        glyphs, _, _ = _glyph_layout(LONG_TEXT, 64, 1200)
        prefs = Preferences(animation_style="ripple_wave", scramble_exit=True, glow_variant="gradient")
        renderer = TextEffects()
        steps = renderer.prepare_steps(glyphs, 64, prefs, 1.5)
        # The first visible surface must not call the blocking material adapter.
        with patch.object(renderer, "_materials", side_effect=AssertionError("whole-sentence preparation")):
            surface = next(ready for ready in steps if ready is not None)
        self.assertEqual(len(surface.materials), len(glyphs))
        self.assertIsNone(surface.replacements)
        steps.close()
        item = LyricTimeline(parse_lrc("[00:01]" + LONG_TEXT + "\n[00:08]"),
                             scramble_exit=True, animation_style=prefs.animation_style,
                             max_display_ms=6000).visible(6500)[0]
        samples = []
        for position in (6400, 6520, 6640, 6760, 6880, 6999):
            states = glyph_states(glyphs, prefs, item, position, 0, 64)
            renderer.render(surface, prefs, states=states)
            samples.append(sum(state.opacity for state in states))
        self.assertTrue(all(a > b for a, b in zip(samples, samples[1:])))

    def test_incremental_base_can_enter_before_scramble_symbols_finish(self):
        glyphs, _, _ = _glyph_layout(LONG_TEXT, 32, 700)
        prefs = Preferences(animation_style="ripple_wave", scramble_exit=True, glow_variant="gradient", jump=0)
        renderer = TextEffects()
        steps = renderer.prepare_steps(glyphs, 32, prefs, 1.5)
        surface = next(ready for ready in steps if ready is not None)
        self.assertIsNone(surface.replacements)
        timeline = LyricTimeline(parse_lrc("[00:01]" + LONG_TEXT + "\n[00:08]Next"),
                                 animation_style=prefs.animation_style, scramble_exit=True, max_display_ms=6000)
        item = timeline.visible(1100)[0]
        sums = []
        for position in (1050, 1200, 1400, 1700):
            states = glyph_states(glyphs, prefs, item, position, 0, 32)
            renderer.render(surface, prefs, states=states)
            sums.append(int(pixels_view(surface.image)[:, :, 3].sum()))
        self.assertTrue(all(left < right for left, right in zip(sums, sums[1:])))
        for _ in steps:
            pass
        self.assertIsNotNone(surface.replacements)
        states = glyph_states(glyphs, prefs, item, 6800, 0, 32)
        renderer.render(surface, prefs, states=states)
        alpha = pixels_view(surface.image)[:, :, 3]
        self.assertFalse(np.any(alpha[0]) or np.any(alpha[-1]) or np.any(alpha[:, 0]) or np.any(alpha[:, -1]))

    def test_plain_symbols_share_materials_but_gradient_positions_do_not(self):
        glyphs, _, _ = _glyph_layout("WWii", 32, 500)
        prefs = Preferences(scramble_exit=True)
        surface = TextEffects().prepare(glyphs, 32, prefs, 1.25)
        self.assertIs(surface.replacements[0][0], surface.replacements[1][0])
        self.assertIs(surface.replacements[0][0], surface.replacements[2][0])
        prefs.glow_variant = "gradient"
        surface = TextEffects().prepare(glyphs, 32, prefs, 1.25)
        self.assertIsNot(surface.replacements[0][0], surface.replacements[1][0])

    def test_overlay_preloads_next_cue_without_blocking_paint_or_touching_clock(self):
        player = Player()
        prefs = Preferences(animation_style="ripple_wave", scramble_exit=True, glow_variant="gradient", angle=0)
        overlay = LyricsOverlay(player, prefs)
        overlay.set_document(parse_lrc("[00:01]Short\n[00:05]" + LONG_TEXT + "\n[00:30]Next"))
        overlay.show()
        try:
            # The paint event schedules preparation; it must not drain it.
            with patch("text_effects.TEXT_EFFECTS.prepare", side_effect=AssertionError("blocking paint preparation")):
                overlay.grab()
            self.assertIn(0, overlay._warm_jobs)
            for _ in range(200):
                if not overlay._warm_jobs:
                    break
                QTest.qWait(10)
            self.assertIsNotNone(overlay.layouts[0].surface)
            player.clock = 1200
            overlay.grab()
            for _ in range(200):
                if not overlay._warm_jobs:
                    break
                QTest.qWait(10)
            self.assertIsNotNone(overlay.layouts[1].surface)
            self.assertFalse(overlay.timer.isActive())
            player.clock = 5100
            frame = overlay.grab().toImage()
            QTest.qWait(50)
            self.assertEqual(frame, overlay.grab().toImage())
            self.assertLessEqual(len(overlay.layouts), 3)
            self.assertEqual(player.clock, 5100)
            player.discontinuity.emit()
            self.assertFalse(overlay._warm_jobs)
            self.assertFalse(overlay.layouts)
            prefs.hide_instrumental = True
            overlay.set_document(parse_lrc("[00:00]作曲：某某\n[00:01]纯音乐，请欣赏"))
            self.assertIsNone(overlay.timeline)
            self.assertFalse(overlay._warm_timer.isActive())
        finally:
            overlay.hide()
            overlay.deleteLater()
