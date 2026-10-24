"""Playback-driven regressions for sub-second lyric boundary flicker."""
from dataclasses import replace
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from kugou import KugouPlayer, KugouSnapshot
from lrc import LyricDocument, LyricLine, LyricTimeline
from test_kugou import Executor


class ContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tick = [10.0]
        self.player = KugouPlayer(clock=lambda: self.tick[0], executor=Executor(), autostart=False)
        self.packet = KugouSnapshot("Song", "Artist", "", 120000, 1000, True, mode="hybrid")
        self.player.apply_snapshot(self.packet)

    def tearDown(self):
        self.player.stop()

    def frames(self, seconds=8):
        values = []
        for frame in range(seconds * 60):
            self.tick[0] = 10 + frame / 60
            if frame % 25 == 0:
                raw = 1000 + int(frame / 60) * 1000
                self.player.apply_snapshot(replace(self.packet, position_ms=raw))
            values.append(self.player.position())
        return values

    def test_second_precision_packets_never_reverse_animation_clock(self):
        values = self.frames()
        changes = [b - a for a, b in zip(values, values[1:])]
        self.assertGreaterEqual(min(changes), -0.0001)
        self.assertLess(max(changes), 25)

    def test_sentence_does_not_reenter_after_crossing_fractional_boundary(self):
        timeline = LyricTimeline(LyricDocument([LyricLine(0, "First"), LyricLine(2350, "Second"),
                                               LyricLine(6400, "Third")], []))
        active = [any(line.index == 1 for line in timeline.visible(value, 120000)) for value in self.frames()]
        entries = sum(current and not previous for previous, current in zip([False] + active, active))
        self.assertEqual(entries, 1)

    def test_single_bad_ocr_time_does_not_relocate_lyrics(self):
        self.tick[0] += .4
        before = self.player.position()
        self.player.apply_snapshot(replace(self.packet, position_ms=45000))
        self.assertLess(abs(self.player.position() - before), 1)
        self.tick[0] += .4
        self.player.apply_snapshot(self.packet)
        self.assertLess(self.player.position(), 4000)

    def test_real_seek_needs_two_consistent_observations_and_clears_once(self):
        jumps = []
        self.player.discontinuity.connect(lambda: jumps.append(True))
        self.tick[0] += .4
        self.player.apply_snapshot(replace(self.packet, position_ms=45000))
        self.assertEqual(len(jumps), 0)
        self.tick[0] += .4
        self.player.apply_snapshot(replace(self.packet, position_ms=45000))
        self.assertEqual(len(jumps), 1)
        self.assertGreater(self.player.position(), 44000)
        self.tick[0] += .4
        self.player.apply_snapshot(replace(self.packet, position_ms=46000))
        self.assertEqual(len(jumps), 1)

    def test_pause_freezes_fractional_time_and_resume_is_continuous(self):
        self.tick[0] += .3
        before = self.player.position()
        self.player.apply_snapshot(replace(self.packet, playing=False))
        self.assertAlmostEqual(self.player.position(), before)
        self.tick[0] += 5
        self.assertAlmostEqual(self.player.position(), before)
        self.player.apply_snapshot(self.packet)
        self.assertAlmostEqual(self.player.position(), before)
        self.tick[0] += .1
        self.assertGreater(self.player.position(), before)

    def test_temporary_ocr_miss_preserves_document_and_layouts(self):
        cleared = []
        self.player.document_changed.connect(cleared.append)
        self.tick[0] += .4
        self.player._handle_missing("temporary OCR miss", True)
        self.assertTrue(self.player.connected)
        self.tick[0] += .4
        self.player.apply_snapshot(self.packet)
        self.assertTrue(self.player.connected)
        self.assertEqual(cleared, [])

    def test_persistent_ocr_loss_disconnects_and_minimize_is_immediate(self):
        self.player._handle_missing("temporary OCR miss", True)
        self.tick[0] += 2.1
        self.player._handle_missing("temporary OCR miss", True)
        self.assertFalse(self.player.connected)
        self.player.apply_snapshot(self.packet)
        self.player._handle_missing("window minimized", False)
        self.assertFalse(self.player.connected)

    def test_single_duration_ocr_error_does_not_reload_song(self):
        cleared = []
        self.player.document_changed.connect(cleared.append)
        self.tick[0] += .4
        self.player.apply_snapshot(replace(self.packet, duration_ms=180000))
        self.tick[0] += .4
        self.player.apply_snapshot(self.packet)
        self.assertEqual(self.player.duration, 120000)
        self.assertEqual(cleared, [])

    def test_stalled_screen_value_does_not_produce_backward_seek(self):
        values = []
        jumps = []
        self.player.discontinuity.connect(lambda: jumps.append(True))
        for frame in range(600):
            self.tick[0] = 10 + frame / 60
            if frame % 25 == 0:
                self.player.apply_snapshot(self.packet)
            values.append(self.player.position())
        self.assertGreaterEqual(min(b - a for a, b in zip(values, values[1:])), -0.001)
        self.assertEqual(jumps, [])
        self.assertLess(values[-1], 4500)

    def test_long_reader_silence_freezes_until_observations_return(self):
        self.tick[0] += 4
        frozen = self.player.position()
        self.tick[0] += 20
        self.assertEqual(self.player.position(), frozen)

    def test_delayed_stale_packet_cannot_rewind_the_coasted_clock(self):
        self.tick[0] += .4
        self.player.apply_snapshot(self.packet)
        self.tick[0] += 3.6
        before = self.player.position()
        self.player.apply_snapshot(self.packet)
        self.assertAlmostEqual(self.player.position(), before)
        self.tick[0] += 2
        self.assertAlmostEqual(self.player.position(), before)

    def test_fractional_sentence_layout_identity_survives_packets(self):
        from overlay import LyricsOverlay
        from settings import Preferences
        overlay = LyricsOverlay(self.player, Preferences())
        overlay.set_document(LyricDocument([LyricLine(0, "First"), LyricLine(2350, "Second"),
                                           LyricLine(6400, "Third")], []))
        identities = set()
        try:
            overlay.show()
            overlay.grab()
            for _ in range(100):
                if 1 in overlay.layouts and overlay.layouts[1].surface is not None:
                    break
                QTest.qWait(10)
            self.assertIn(1, overlay.layouts)
            for frame in range(300):
                self.tick[0] = 10 + frame / 60
                if frame % 25 == 0:
                    self.player.apply_snapshot(replace(self.packet, position_ms=1000 + int(frame / 60) * 1000))
                overlay.grab()
                if 1 in overlay.layouts:
                    identities.add(id(overlay.layouts[1]))
            self.assertEqual(len(identities), 1)
        finally:
            overlay.close()


if __name__ == "__main__":
    unittest.main()
