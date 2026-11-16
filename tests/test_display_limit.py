"""Selectable block capacity retires history without changing the music clock."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from lrc import LyricDocument, LyricLine, LyricTimeline, display_document, parse_lrc
from overlay import LyricsOverlay
from presets import EFFECT_KEYS
from settings import ANIMATION_STYLES, Preferences, SettingsStore
from test_prepared_entrance import APP, Player
import test_controls as fixture


class DisplayLimitTests(unittest.TestCase):
    def test_old_settings_keep_four_and_new_values_persist_with_range_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            path.write_text("[General]\nextended_display=true\nextended_display_seconds=17\n", encoding="utf-8")
            store = SettingsStore(path)
            prefs = store.load()
            self.assertEqual((prefs.extended_display_limit, prefs.extended_display_seconds), (4, 17))
            self.assertTrue(prefs.extended_display)
            for value, expected in ((2, 2), (3, 3), (4, 4), (-1, 2), (20, 4)):
                prefs.extended_display_limit = value
                store.save(prefs)
                self.assertEqual(SettingsStore(path).load().extended_display_limit, expected)
            store.store.setValue("extended_display_limit", "not-a-number")
            store.store.sync()
            self.assertEqual(SettingsStore(path).load().extended_display_limit, 4)
        self.assertNotIn("extended_display_limit", EFFECT_KEYS)

    def test_two_three_four_and_all_animation_exits_complete_before_next_block(self):
        document = LyricDocument([LyricLine(i * 1000, str(i)) for i in range(10)], [])
        for limit in (2, 3, 4):
            for style in ANIMATION_STYLES:
                for scramble in (False, True):
                    with self.subTest(limit=limit, style=style, scramble=scramble):
                        timeline = LyricTimeline(document, animation_style=style, scramble_exit=scramble,
                                                 extended_display_ms=120000, extended_display_limit=limit)
                        before = timeline.visible(limit * 1000 - 1)
                        self.assertEqual([item.index for item in before], list(range(limit)))
                        oldest = before[0]
                        self.assertLess(oldest.exit_start_ms, limit * 1000 - 1)
                        self.assertEqual(oldest.end_ms, limit * 1000)
                        if style == "classic" and not scramble:
                            self.assertLess(oldest.opacity, .01)
                        self.assertEqual([item.index for item in timeline.visible(limit * 1000)], list(range(1, limit + 1)))
                        for position in range(0, 11000, 137):
                            self.assertLessEqual(len(timeline.visible(position)), limit)

    def test_blank_song_end_and_offsets_override_long_holds_at_every_capacity(self):
        document = parse_lrc("[offset:100]\n[00:01]甲\n[00:02]乙\n[00:03]丙\n[00:05]\n[00:08]丁")
        for limit in (2, 3, 4):
            timeline = LyricTimeline(document, delay_ms=300, extended_display_ms=120000, extended_display_limit=limit)
            self.assertTrue(timeline.visible(5100))
            self.assertFalse(timeline.visible(5200))
            self.assertFalse(timeline.visible(4800, 4800))
            self.assertFalse(timeline.visible(8000))
            self.assertEqual([item.text for item in timeline.visible(8200)], ["丁"])

    def test_bilingual_is_one_group_and_reading_order_is_preserved(self):
        document = display_document(LyricDocument([
            LyricLine(i * 1000, f"Café 😀 {i}", translation=f"翻译 {i}") for i in range(7)], []),
            mode="bilingual_original")
        for limit in (2, 3, 4):
            items = LyricTimeline(document, extended_display_ms=10000, extended_display_limit=limit).visible(5500)
            self.assertEqual([item.index for item in items], list(range(6 - limit, 6)))
            self.assertTrue(all(item.secondary_start > 0 and "Café 😀" in item.text for item in items))

    def test_seeks_pause_repeats_and_duration_expiry_are_stateless(self):
        document = LyricDocument([LyricLine(i * 1000, str(i)) for i in range(9)], [])
        for limit in (2, 3, 4):
            timeline = LyricTimeline(document, extended_display_ms=2000, extended_display_limit=limit)
            later = timeline.visible(6500)
            self.assertEqual([item.index for item in later], [5, 6])
            timeline.visible(1500)
            self.assertEqual(timeline.visible(6500), later)
            self.assertEqual(timeline.visible(6500), later)
            self.assertFalse(timeline.visible(10500))
            # The chosen maximum is a cap, not a request to prolong expired lines.
            self.assertLessEqual(len(later), limit)

    def test_disabled_mode_ignores_capacity_and_default_matches_previous_four(self):
        document = parse_lrc("[00:00]一\n[00:01]二\n[00:02]三\n[00:03]四\n[00:04]五")
        default = LyricTimeline(document, extended_display_ms=10000)
        four = LyricTimeline(document, extended_display_ms=10000, extended_display_limit=4)
        normal = LyricTimeline(document)
        for position in (0, 1350, 2900, 3999, 4000, 5000):
            self.assertEqual(default.visible(position), four.visible(position))
            for limit in (2, 3, 4):
                self.assertEqual(LyricTimeline(document, extended_display_limit=limit).visible(position), normal.visible(position))

    def test_overlay_uses_current_capacity_and_retains_only_active_plus_next(self):
        player = Player()
        player.clock = 5500
        prefs = Preferences(extended_display=True, extended_display_seconds=120, extended_display_limit=2)
        overlay = LyricsOverlay(player, prefs)
        overlay.set_document(LyricDocument([LyricLine(i * 1000, str(i)) for i in range(10)], []))
        overlay.show()
        try:
            def empty_prepare(_index, _line):
                yield None
            with patch.object(overlay, "_prepare_line", side_effect=empty_prepare):
                for limit in (2, 3, 4, 2):
                    prefs.extended_display_limit = limit
                    overlay.refresh_preferences()
                    active = overlay.timeline.visible(player.clock)
                    self.assertEqual(len(active), limit)
                    overlay._prepare_lines(active, player.clock)
                    self.assertEqual(len(overlay._warm_jobs), limit + 1)
                    self.assertEqual(set(overlay._warm_jobs), set(range(6 - limit, 7)))
            self.assertEqual(player.clock, 5500)
        finally:
            overlay.hide()
            overlay.deleteLater()


class DisplayLimitControlsTests(unittest.TestCase):
    setUp = fixture.ControlPanelTests.setUp
    tearDown = fixture.ControlPanelTests.tearDown

    def test_selection_persists_and_presets_do_not_reset_or_control_playback(self):
        combo = self.panel.extended_limit_combo
        self.assertEqual(combo.currentData(), 4)
        self.assertFalse(combo.isEnabled())
        self.assertEqual([combo.itemData(i) for i in range(combo.count())], [2, 3, 4])
        self.player.playing, self.player.clock = True, 5500
        self.panel.extended_checkbox.setChecked(True)
        for limit in (2, 3, 4, 2):
            combo.setCurrentIndex(combo.findData(limit))
            self.assertEqual(self.store.load().extended_display_limit, limit)
            self.panel.apply_preset("builtin:lively")
            self.assertEqual(combo.currentData(), limit)
            self.assertEqual(self.store.load().extended_display_limit, limit)
        self.panel.extended_checkbox.setChecked(False)
        self.assertFalse(combo.isEnabled())
        self.panel.extended_checkbox.setChecked(True)
        self.assertEqual(combo.currentData(), 2)
        self.assertEqual((self.player.playing, self.player.clock, self.player.seeks), (True, 5500, []))

    def test_minimum_window_scroll_and_mouse_wheel_keep_the_selected_limit(self):
        self.panel.resize(900, 560)
        self.panel.nav_buttons[1].click()
        self.panel.extended_checkbox.setChecked(True)
        combo = self.panel.extended_limit_combo
        combo.setCurrentIndex(combo.findData(3))
        self.panel.effects_scroll.ensureWidgetVisible(combo, 0, 24)
        APP.processEvents()
        self.assertFalse(combo.visibleRegion().isEmpty())
        event = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        APP.sendEvent(combo, event)
        self.assertEqual(combo.currentData(), 3)
        self.assertFalse(event.isAccepted())
        self.assertTrue(self.panel.player_bar.isVisibleTo(self.panel))
