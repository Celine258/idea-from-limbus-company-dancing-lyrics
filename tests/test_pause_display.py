"""Pause visibility affects pixels, never transport, manual visibility or presets."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import json
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
from lrc import parse_lrc
from overlay import LyricsOverlay
from presets import EFFECT_KEYS
from settings import Preferences, SettingsStore, ANIMATION_STYLES
from text_effects import pixels_view
from test_prepared_entrance import APP, Player
import test_controls as fixture


class PauseDisplayTests(unittest.TestCase):
    def test_native_evidence_and_all_player_guides_keep_scope_explicit(self):
        root = Path(__file__).resolve().parents[1]
        record = json.loads((root / "docs/research/pause-display-20261031.json").read_text(encoding="utf-8"))
        self.assertTrue(record["passed"] and record["synthetic_source_packets"])
        self.assertFalse(record["real_client_pause_verified"] or record["default_enabled"])
        self.assertEqual([report["dpr"] for report in record["source_reports"]], [1, 1.25, 1.5])
        for report in record["source_reports"]:
            self.assertTrue(all(report["checks"].values()))
            self.assertEqual(report["music_client_commands"], 0)
            for source in ("netease", "qqmusic", "kugou"):
                self.assertTrue(report["checks"][source + "_pause_clears_alpha"])
                self.assertTrue(report["checks"][source + "_resume_current_progress"])
        for name in ("README.md", "NETEASE.md", "QQMUSIC.md", "KUGOU.md", "release/使用说明.txt",
                     "release/netease/使用说明.txt", "release/qqmusic/使用说明.txt", "release/kugou-guide.txt",
                     "release/release-notes.md", "release/kugou-release-notes.md"):
            text = (root / name).read_text(encoding="utf-8")
            for phrase in ("暂停播放时隐藏歌词", "默认关闭", "当前进度", "手动隐藏"):
                self.assertIn(phrase, text, name)

    def test_frozen_diagnostic_dispatch_does_not_launch_a_client(self):
        from tools import validate_pause_display
        arguments = ["main.py", "--pause-display-smoke", "--output", "中文 测试"]
        with patch.object(sys, "argv", arguments), patch.object(validate_pause_display, "main", return_value=0) as run:
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(Path(__file__).resolve().parents[1] / "main.py"), run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        run.assert_called_once_with(arguments[2:])

    def test_old_settings_default_off_and_boolean_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.ini")
            self.assertFalse(store.load().hide_on_pause)
            for value in (True, False):
                prefs = Preferences(hide_on_pause=value, font_size=28)
                store.save(prefs)
                self.assertEqual(store.load().hide_on_pause, value)
                self.assertEqual(store.load().font_size, 28)
        self.assertNotIn("hide_on_pause", EFFECT_KEYS)

    def image(self, overlay):
        return overlay.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

    def has_pixels(self, overlay):
        image = self.image(overlay)  # Keep the owner alive while NumPy views its buffer.
        return bool(pixels_view(image)[:, :, 3].any())

    def ready(self, overlay):
        self.image(overlay)
        for _ in range(400):
            if not overlay._warm_jobs:
                break
            overlay._warm_step()
        self.assertTrue(any(layout.surface is not None for layout in overlay.layouts.values()))

    def test_pause_clears_all_materials_and_resume_reuses_surfaces_every_animation(self):
        for style in ANIMATION_STYLES:
            with self.subTest(style=style):
                player = Player()
                player.playing, player.clock = True, 2500
                prefs = Preferences(hide_on_pause=True, animation_style=style, scramble_exit=True,
                                    extended_display=True, region="full", angle=0, jump=0)
                overlay = LyricsOverlay(player, prefs)
                overlay.set_document(parse_lrc("[00:00]第一句\n[00:01]第二句\n[00:08]下一句"))
                overlay.show()
                try:
                    self.ready(overlay)
                    before = self.image(overlay)
                    self.assertTrue(pixels_view(before)[:, :, 3].any())
                    surfaces = {key: value.surface for key, value in overlay.layouts.items()}
                    player.playing = False
                    player.changed.emit()
                    self.assertFalse(self.has_pixels(overlay))
                    self.assertFalse(overlay.timer.isActive() or overlay._warm_timer.isActive())
                    self.assertTrue(overlay.isVisible())
                    QTest.qWait(20)
                    self.assertEqual(player.clock, 2500)
                    player.playing = True
                    player.changed.emit()
                    self.assertEqual(self.image(overlay), before)
                    for key, surface in surfaces.items():
                        self.assertIs(overlay.layouts[key].surface, surface)
                finally:
                    overlay.hide()
                    overlay.deleteLater()

    def test_toggle_while_paused_restores_frozen_frame_without_rebuilding(self):
        player = Player()
        player.clock = 2000
        prefs = Preferences(region="full", angle=0, jump=0)
        overlay = LyricsOverlay(player, prefs)
        overlay.set_document(parse_lrc("[00:00]暂停仍显示\n[00:05]下一句"))
        overlay.show()
        try:
            self.ready(overlay)
            frame = self.image(overlay)
            self.assertTrue(pixels_view(frame)[:, :, 3].any())
            QTest.qWait(20)
            self.assertEqual(self.image(overlay), frame)
            prefs.hide_on_pause = True
            overlay.update()
            self.assertFalse(self.has_pixels(overlay))
            prefs.hide_on_pause = False
            overlay.update()
            self.assertEqual(self.image(overlay), frame)
        finally:
            overlay.hide()
            overlay.deleteLater()

    def test_paused_seek_late_lyrics_and_manual_hide_do_not_resurrect_old_frame(self):
        player = Player()
        player.clock, player.playing = 2000, True
        prefs = Preferences(hide_on_pause=True)
        overlay = LyricsOverlay(player, prefs)
        overlay.set_document(parse_lrc("[00:00]原来的歌词\n[00:05]新的一句"))
        overlay.show()
        try:
            self.ready(overlay)
            player.playing = False
            player.changed.emit()
            player.clock = 6500
            player.discontinuity.emit()
            overlay.set_document(parse_lrc("[00:00]旧\n[00:05]迟到的新歌词"))
            with patch.object(overlay, "_prepare_line", side_effect=AssertionError("paused work")):
                self.assertFalse(self.has_pixels(overlay))
            overlay.hide()
            player.playing = True
            player.changed.emit()
            APP.processEvents()
            self.assertFalse(overlay.isVisible() or overlay.timer.isActive())
            overlay.show()
            self.ready(overlay)
            self.assertEqual([line.index for line in overlay.timeline.visible(player.clock)], [1])
            self.assertTrue(self.has_pixels(overlay))
        finally:
            overlay.hide()
            overlay.deleteLater()


class PauseControlsTests(unittest.TestCase):
    setUp = fixture.ControlPanelTests.setUp
    tearDown = fixture.ControlPanelTests.tearDown

    def test_immediate_save_preset_independence_and_no_transport(self):
        self.player.clock, self.player.playing = 3500, False
        self.assertFalse(self.panel.pause_checkbox.isChecked())
        self.panel.pause_checkbox.setChecked(True)
        self.assertTrue(self.store.load().hide_on_pause)
        self.panel.apply_preset("builtin:lively")
        self.assertTrue(self.panel.pause_checkbox.isChecked() and self.store.load().hide_on_pause)
        self.panel.pause_checkbox.setChecked(False)
        self.assertFalse(self.store.load().hide_on_pause)
        self.assertEqual((self.player.clock, self.player.playing, self.player.seeks), (3500, False, []))

    def test_option_scrolls_into_view_without_covering_footer(self):
        self.panel.resize(900, 560)
        self.panel.nav_buttons[1].click()
        self.panel.effects_scroll.ensureWidgetVisible(self.panel.pause_checkbox, 0, 20)
        APP.processEvents()
        self.assertFalse(self.panel.pause_checkbox.visibleRegion().isEmpty())
        self.assertTrue(self.panel.player_bar.isVisibleTo(self.panel))
