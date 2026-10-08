import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication
from lrc import LyricDocument, LyricLine, LyricTimeline, TimedWord, display_document
from netease import validate_snapshot, NeteasePlayer
from overlay import LyricsOverlay
from presets import EFFECT_KEYS
from settings import Preferences, SettingsStore
from test_netease import packet

APP = QApplication.instance() or QApplication([])


class TranslationTests(unittest.TestCase):
    def test_per_line_fallback_keeps_original_timings_but_never_maps_words_to_translation(self):
        words = (TimedWord(1200, 1800, 0, 2),)
        original = LyricDocument([LyricLine(1000, "Hi é👩‍💻", words, "你好\n朋友"),
                                  LyricLine(3000, "instrumental", words), LyricLine(4000, "", (), "空白")], [], 100)
        self.assertIs(display_document(original), original)
        displayed = display_document(original, True)
        self.assertEqual([line.text for line in displayed.lines], ["你好\n朋友", "instrumental", ""])
        self.assertEqual(displayed.lines[0].words, ())
        self.assertEqual(displayed.lines[1].words, words)
        self.assertEqual(original.lines[0].text, "Hi é👩‍💻")
        timeline = LyricTimeline(displayed, delay_ms=200)
        self.assertEqual(timeline.lines[0].start_ms, 1100)
        self.assertEqual(timeline.lines[1].words[0].start_ms, 1300)

    def test_optional_bad_translation_never_rejects_original_lyrics_or_old_plugin(self):
        for value in (None, {}, [], 123, "English", "\x00坏", "中" * 2049):
            parsed = validate_snapshot(packet(lyrics=[{"time_ms": 1000, "text": "Original", "translation": value}]))
            self.assertEqual(parsed["document"].lines[0].translation, "")
        parsed = validate_snapshot(packet(lyrics=[{"time_ms": 1000, "text": "Original", "translation": "中文译文"}]))
        self.assertEqual(parsed["document"].lines[0].translation, "中文译文")
        self.assertEqual(validate_snapshot(packet())["document"].lines[0].translation, "")

    def test_setting_persistence_legacy_default_and_preset_independence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.ini")
            self.assertFalse(store.load().prefer_translation)
            store.save(Preferences(prefer_translation=True))
            self.assertTrue(store.load().prefer_translation)
        self.assertNotIn("prefer_translation", EFFECT_KEYS)

    def test_overlay_rebuilds_on_language_and_late_translation_without_moving_paused_clock(self):
        player, prefs = NeteasePlayer(), Preferences(prefer_translation=True)
        overlay = LyricsOverlay(player, prefs)
        try:
            player.apply(validate_snapshot(packet(playing=False)))
            first = LyricDocument([LyricLine(1000, "Original")], [])
            overlay.set_document(first)
            overlay.layouts[0] = object()
            overlay.set_document(LyricDocument([LyricLine(1000, "Original", (), "中文译文")], []))
            self.assertFalse(overlay.layouts)
            self.assertEqual(overlay.timeline.visible(player.position(), player.duration)[0].text, "中文译文")
            prefs.prefer_translation = False
            overlay.refresh_preferences()
            self.assertEqual(overlay.timeline.visible(player.position(), player.duration)[0].text, "Original")
            self.assertEqual((player.playing, player.position()), (False, 1200))
            overlay.set_document(None)
            self.assertIsNone(overlay.timeline)
            self.assertIsNone(overlay.display_document)
        finally:
            overlay.hide()
            overlay.deleteLater()
