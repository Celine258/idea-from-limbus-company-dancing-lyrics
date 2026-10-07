import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from dataclasses import replace
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PySide6.QtCore import QObject, QRectF, Signal
from PySide6.QtGui import QColor, QPainterPath, QTransform
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from animation import Glyph, _glyph_layout, build_layout, display_regions
from glyph_motion import GlyphState, glyph_states, noise
from lrc import ActiveLine, LyricTimeline, parse_lrc
from settings import ANIMATION_STYLES, Preferences, SettingsStore
from text_effects import TextEffects, pixels_view

APP = QApplication.instance() or QApplication([])
STYLES = tuple(style for style in ANIMATION_STYLES if style != "classic")


def rectangles():
    result = []
    for index in range(4):
        path = QPainterPath()
        path.addRect(QRectF(0, -20, 16, 20))
        result.append(Glyph(path, index * 30, 0, index))
    return result


class AnimatedTimelineTests(unittest.TestCase):
    def timeline(self, text):
        return LyricTimeline(parse_lrc(text), animation_style="ripple_wave")

    def test_long_line_stays_complete_until_next_sentence_and_short_tail(self):
        timeline = self.timeline("[00:01]一\n[00:11]二\n[00:11.500]三")
        self.assertEqual([line.text for line in timeline.visible(9000)], ["一"])
        first, second = timeline.visible(11100)
        self.assertEqual((first.entry_end_ms, first.exit_start_ms, first.end_ms), (1700, 11000, 11225))
        self.assertEqual(second.entry_end_ms, 11175)
        self.assertEqual(first.opacity, 1)
        self.assertEqual([line.text for line in timeline.visible(11225)], ["二"])

    def test_blank_boundary_and_known_song_end_leave_no_residue(self):
        timeline = self.timeline("[00:01]一\n[00:03]\n[00:09]二")
        self.assertEqual(timeline.visible(2500)[0].exit_start_ms, 2400)
        self.assertEqual(timeline.visible(3000), [])
        self.assertEqual(timeline.visible(8500), [])
        last = timeline.visible(9200, 9500)[0]
        self.assertEqual((last.entry_end_ms, last.exit_start_ms, last.end_ms), (9175, 9350, 9500))
        self.assertEqual(timeline.visible(9500, 9500), [])

    def test_unknown_final_duration_keeps_six_second_fallback(self):
        timeline = self.timeline("[00:01]一")
        self.assertEqual(timeline.visible(6500)[0].end_ms, 7000)
        self.assertEqual(timeline.visible(7000), [])

    def test_dense_lines_and_seek_are_stateless_with_offsets(self):
        text = "[offset:100]\n" + "\n".join(f"[00:00.{index:03d}]第{index}句" for index in range(0, 900, 50))
        timeline = LyricTimeline(parse_lrc(text), 200, "fall_shake")
        for position in range(0, 1400, 7):
            self.assertLessEqual(len(timeline.visible(position)), 2)
        self.assertEqual(timeline.visible(175)[0].start_ms, 150)
        first = timeline.visible(850)
        timeline.visible(200)
        self.assertEqual(first, timeline.visible(850))


class CharacterMotionTests(unittest.TestCase):
    def setUp(self):
        self.glyphs = rectangles()
        self.item = ActiveLine(0, "文字", 1000, 4600, 1, 1700, 4000)

    def states(self, position, style="ripple_wave", jump=0, angle=0, seed=42):
        return glyph_states(self.glyphs, Preferences(animation_style=style, jump=jump),
                            self.item, position, .5, 32, seed, angle)

    def test_entrance_and_exit_follow_reading_order_for_all_four_styles(self):
        for style in STYLES:
            self.assertTrue(all(state.opacity == 0 for state in self.states(1000, style)))
            entering = [state.opacity for state in self.states(1300, style)]
            self.assertEqual(entering, sorted(entering, reverse=True))
            self.assertGreater(entering[0], entering[-1])
            self.assertTrue(all(state.opacity == 1 for state in self.states(1700, style)))
            leaving = [state.opacity for state in self.states(4300, style)]
            self.assertEqual(leaving, sorted(leaving))
            self.assertLess(leaving[0], leaving[-1])
            self.assertTrue(all(state.opacity == 0 for state in self.states(4600, style)))

    def test_single_character_completes_without_waiting_for_stagger(self):
        for style in STYLES:
            prefs = Preferences(animation_style=style)
            states = glyph_states(self.glyphs[:1], prefs, self.item, 1140, 0, 32)
            self.assertEqual(states[0].opacity, 1)
            states = glyph_states(self.glyphs[:1], prefs, self.item, 4350, 0, 32)
            self.assertEqual(states[0].opacity, 0)

    def test_short_stage_compresses_every_character(self):
        item = ActiveLine(0, "字", 0, 145, 1, 35, 100)
        for style in STYLES:
            prefs = Preferences(animation_style=style)
            self.assertTrue(all(state.opacity == 1 for state in glyph_states(self.glyphs, prefs, item, 35, 0, 32)))
            self.assertTrue(all(state.opacity == 0 for state in glyph_states(self.glyphs, prefs, item, 145, 0, 32)))

    def test_spaces_do_not_take_slots_and_clusters_and_rows_keep_order(self):
        glyphs, _, _ = _glyph_layout("你 e\u0301\n好", 32, 300)
        states = glyph_states(glyphs, Preferences(animation_style="ripple_wave", jump=0),
                              self.item, 1300, 0, 32)
        visible = [state for glyph, state in zip(glyphs, states) if not glyph.path.isEmpty()]
        self.assertEqual(len(visible), 3)
        expected = glyph_states(self.glyphs[:3], Preferences(animation_style="ripple_wave", jump=0), self.item, 1300, 0, 32)
        self.assertEqual([state.opacity for state in visible], [state.opacity for state in expected])
        self.assertEqual(states[1].opacity, 0)

    def test_wave_travels_at_one_and_half_hz_and_keeps_music_energy_floor(self):
        prefs = Preferences(animation_style="ripple_wave", jump=10)
        first = glyph_states(self.glyphs, prefs, self.item, 2000, 0, 32)
        later = glyph_states(self.glyphs, prefs, self.item, 2000 + 1000 / 1.5, 0, 32)
        for before, after in zip(first, later):
            self.assertAlmostEqual(before.y, after.y, places=6)
        self.assertTrue(any(abs(state.y) > .1 for state in first))
        louder = glyph_states(self.glyphs, prefs, self.item, 2000, 1, 32)
        self.assertGreater(max(abs(state.y) for state in louder), max(abs(state.y) for state in first))

    def test_shake_is_deterministic_smooth_and_differs_from_wave(self):
        self.assertEqual(self.states(2311, "fall_shake", 10), self.states(2311, "fall_shake", 10))
        self.assertNotEqual(self.states(2311, "fall_shake", 10), self.states(2311, "fall_shake", 10, seed=43))
        self.assertNotEqual(self.states(2311, "ripple_shake", 10), self.states(2311, "ripple_wave", 10))
        boundary = 14 / 6
        self.assertAlmostEqual(noise(42, 0, 0, boundary - .000001), noise(42, 0, 0, boundary + .000001), places=7)

    def test_zero_amplitude_keeps_fade_and_accelerating_screen_vertical_fall(self):
        angle = 25
        early, later = self.states(4100, "fall_wave", angle=angle)[0], self.states(4200, "fall_wave", angle=angle)[0]
        radians = math.radians(angle)
        for state in (early, later):
            dx = state.x * math.cos(radians) - state.y * math.sin(radians)
            self.assertAlmostEqual(dx, 0, places=6)
            self.assertGreater(state.y, 0)
            self.assertLess(state.opacity, 1)
            self.assertLessEqual(abs(state.rotation), 8)
        self.assertAlmostEqual(later.y / early.y, 4)
        for style in STYLES:
            self.assertEqual([(state.x, state.y) for state in self.states(2000, style)],
                             [(glyph.x, glyph.baseline) for glyph in self.glyphs])


class AnimatedDrawingTests(unittest.TestCase):
    def test_character_rgba_fade_keeps_white_core_and_applies_opacity_once(self):
        glyph = rectangles()[0]
        renderer = TextEffects()
        prefs = Preferences(animation_style="ripple_wave", color="#ff4080", jump=0)
        surface = renderer.prepare([glyph], 32, prefs, 1)
        full = renderer.render(surface, prefs, states=[GlyphState(0, 0)]).copy()
        half = renderer.render(surface, prefs, states=[GlyphState(0, 0, .5)]).copy()
        point = (round(8 - surface.origin.x()), round(-10 - surface.origin.y()))
        color = half.pixelColor(*point)
        self.assertEqual((color.red(), color.green(), color.blue()), (255, 255, 255))
        self.assertLessEqual(abs(color.alpha() - 127), 2)
        before, after = pixels_view(full), pixels_view(half)
        self.assertLessEqual(np.max(np.abs(after.astype(int) - before.astype(int) * .5)), 2)
        renderer.render(surface, prefs, states=[GlyphState(0, 0, 0)])
        self.assertFalse(np.any(pixels_view(surface.image)))

    def test_fading_cores_exclude_neighbour_halos_and_solid_fill_is_retained(self):
        glyphs = rectangles()[:2]
        glyphs[1].x = 17
        renderer = TextEffects()
        prefs = Preferences(animation_style="ripple_wave", color="#ff4080", jump=0, glow_strength=100)
        for text_style in ("glow", "solid"):
            prefs.text_style = text_style
            surface = renderer.prepare(glyphs, 32, prefs, 1)
            image = renderer.render(surface, prefs, states=[GlyphState(0, 0, .5), GlyphState(17, 0)])
            color = image.pixelColor(round(8 - surface.origin.x()), round(-10 - surface.origin.y()))
            expected = QColor("white" if text_style == "glow" else prefs.color)
            for channel, value in zip((color.red(), color.green(), color.blue()), (expected.red(), expected.green(), expected.blue())):
                self.assertLessEqual(abs(channel - value), 2)
            self.assertLessEqual(abs(color.alpha() - 127), 2)

    def test_all_modes_custom_font_extreme_layout_and_dpr_have_clear_edges(self):
        from fonts import FontLibrary
        with tempfile.TemporaryDirectory() as directory:
            library = FontLibrary(Path(directory))
            try:
                family = library.import_font(Path(__file__).parent / "fixtures/lyrics-test.ttf")[0][0]
                renderer = TextEffects()
                for style in STYLES:
                    prefs = Preferences(animation_style=style, font_family=family, font_size=64, jump=30, angle=25)
                    regions = display_regions(1024, 720, "edges")
                    layout = build_layout("AAA中 Hello music" * 4, 730, regions, [], prefs)
                    self.assertIsNotNone(layout)
                    self.assertTrue(any(region.contains(layout.bounds) for region in regions))
                    for dpr in (1, 1.25, 1.5):
                        surface = renderer.prepare(layout.glyphs, layout.font_size, prefs, dpr, 30, layout.angle)
                        local = QRectF(surface.origin, surface.image.deviceIndependentSize())
                        transform = QTransform().translate(layout.center.x(), layout.center.y()).rotate(layout.angle)
                        self.assertTrue(layout.bounds.contains(transform.mapRect(local)))
                        item = ActiveLine(0, "", 0, 3800, 1, 700, 3200)
                        misses = renderer.misses
                        buffer_id = id(surface.image)
                        for position in (100, 600, 1700, 3300, 3550, 3799):
                            states = glyph_states(layout.glyphs, prefs, item, position, 1, layout.font_size, 730, layout.angle)
                            renderer.render(surface, prefs, states=states)
                            alpha = pixels_view(surface.image)[:, :, 3]
                            self.assertFalse(np.any(alpha[0]) or np.any(alpha[-1]) or np.any(alpha[:, 0]) or np.any(alpha[:, -1]))
                        self.assertEqual(id(surface.image), buffer_id)
                        self.assertEqual(renderer.misses, misses)
            finally:
                library.close()

    def test_overlay_pause_seek_and_setting_change_preserve_transport(self):
        from overlay import LyricsOverlay
        class Player(QObject):
            changed, discontinuity = Signal(), Signal()
            playing, ended, duration, clock = False, False, 9000, 3300
            def position(self):
                return self.clock
            def energy_at(self, _):
                return .5
        player = Player()
        prefs = Preferences()
        overlay = LyricsOverlay(player, prefs)
        overlay.set_document(parse_lrc("[00:01]第一句\n[00:03]第二句"))
        overlay.show()
        try:
            for style in STYLES:
                prefs.animation_style = style
                overlay.refresh_preferences()
                first = overlay.grab().toImage()
                QTest.qWait(40)
                self.assertEqual(first, overlay.grab().toImage())
                self.assertFalse(overlay.timer.isActive())
                player.clock = 1800
                player.discontinuity.emit()
                self.assertNotEqual(first, overlay.grab().toImage())
                player.clock = 3300
                player.discontinuity.emit()
                self.assertEqual(first, overlay.grab().toImage())
            self.assertEqual(player.clock, 3300)
            self.assertFalse(player.playing)
        finally:
            overlay.hide()
            overlay.deleteLater()


class AnimationSettingsTests(unittest.TestCase):
    def test_styles_persist_and_old_or_invalid_configuration_keeps_classic(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.ini")
            self.assertEqual(store.load().animation_style, "classic")
            for style in ANIMATION_STYLES:
                prefs = Preferences(animation_style=style, font_family="KaiTi", color="#ffaa00", jump=18)
                store.save(prefs)
                self.assertEqual(store.load(), prefs)
            store.store.setValue("animation_style", "unknown")
            self.assertEqual(store.load().animation_style, "classic")


if __name__ == "__main__":
    unittest.main()
