import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtMultimedia import QAudioFormat
from PySide6.QtWidgets import QApplication
from animation import build_layout, display_regions, graphemes
from audio_energy import pcm_rms
from lrc import parse_lrc, load_lrc, LyricTimeline
from settings import Preferences, SettingsStore

APP = QApplication.instance() or QApplication([])


class LyricsTests(unittest.TestCase):
    def test_fraction_repeated_tags_and_translation(self):
        doc = parse_lrc("[00:01.2][00:03.045]你好\n[00:01.200]Hello\n[00:02]世界")
        self.assertEqual([(l.start_ms, l.text) for l in doc.lines],
                         [(1200, "你好\nHello"), (2000, "世界"), (3045, "你好")])

    def test_metadata_and_invalid_lines(self):
        doc = parse_lrc("[ti:歌名]\n[00:65.0]错\n无标签\n[00:01]对")
        self.assertEqual(len(doc.warnings), 2)
        self.assertEqual(doc.lines[0].text, "对")

    def test_empty_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_lrc("[ti:没有歌词]\n[00:00]")

    def test_encoding_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "song.lrc"
            path.write_bytes("[00:01]中文歌词".encode("gb18030"))
            self.assertEqual(load_lrc(path).lines[0].text, "中文歌词")
            path.write_bytes("[00:01]中文歌词".encode("utf-8-sig"))
            self.assertEqual(load_lrc(path).lines[0].text, "中文歌词")

    def test_offset_and_user_delay_are_distinct(self):
        doc = parse_lrc("[offset:300]\n[00:01]歌词")
        timeline = LyricTimeline(doc, delay_ms=500)
        self.assertEqual(timeline.lines[0].start_ms, 1200)
        self.assertEqual(timeline.visible(1100), [])
        self.assertEqual(timeline.visible(1500)[0].opacity, 1)

    def test_seek_backward_is_stateless_and_pause_repeats(self):
        timeline = LyricTimeline(parse_lrc("[00:01]一\n[00:04]二\n[00:07]三"))
        self.assertEqual([l.text for l in timeline.visible(7800)], ["三"])
        self.assertEqual([l.text for l in timeline.visible(1800)], ["一"])
        self.assertEqual(timeline.visible(4300), timeline.visible(4300))
        self.assertEqual([l.text for l in timeline.visible(4300)], ["一", "二"])

    def test_silent_marker_clears_previous_sentence(self):
        timeline = LyricTimeline(parse_lrc("[00:01]一句\n[00:03]\n[00:09]下一句"))
        self.assertTrue(timeline.visible(2400))
        self.assertEqual(timeline.visible(3000), [])
        self.assertEqual(timeline.visible(8500), [])

    def test_lifetime_and_end_of_song(self):
        timeline = LyricTimeline(parse_lrc("[00:01]一句"))
        self.assertEqual(timeline.visible(500), [])
        self.assertEqual(timeline.visible(7000), [])
        self.assertAlmostEqual(timeline.visible(6700)[0].opacity, .5)
        self.assertEqual(timeline.visible(3000, duration_ms=3000), [])

    def test_dense_lyrics_have_at_most_two_instances(self):
        timeline = LyricTimeline(parse_lrc("\n".join(f"[00:00.{i:03d}]第{i}句" for i in range(0, 900, 50))))
        self.assertLessEqual(len(timeline.visible(850)), 2)


class EnergyTests(unittest.TestCase):
    def test_silence_and_unsigned_midpoint(self):
        self.assertEqual(pcm_rms(np.zeros(100, dtype=np.int16).tobytes(), QAudioFormat.SampleFormat.Int16), 0)
        self.assertEqual(pcm_rms(bytes([128] * 100), QAudioFormat.SampleFormat.UInt8), 0)

    def test_signed_and_float_pcm(self):
        for dtype, scale, fmt in ((np.int16, 32768, QAudioFormat.SampleFormat.Int16),
                                   (np.int32, 2147483648, QAudioFormat.SampleFormat.Int32),
                                   (np.float32, 1, QAudioFormat.SampleFormat.Float)):
            raw = np.array([.5 * scale, -.5 * scale], dtype=dtype).tobytes()
            self.assertAlmostEqual(pcm_rms(raw, fmt), .5, places=5)


class LayoutTests(unittest.TestCase):
    def test_unicode_clusters(self):
        self.assertEqual(graphemes("你e\u0301👩‍💻好"), ["你", "e\u0301", "👩‍💻", "好"])

    def test_long_rotated_sentences_stay_in_region(self):
        for width, height in ((1920, 1040), (1536, 824), (1280, 680), (1024, 720)):
            for mode in ("edges", "full"):
                regions = display_regions(width, height, mode)
                for seed in range(3):
                    prefs = Preferences(angle=25, jump=30)
                    text = "陪你写下一行代码，让今天的工作有一点节奏" * 2
                    item = build_layout(text, seed, regions, [], prefs)
                    self.assertIsNotNone(item)
                    self.assertTrue(any(r.contains(item.bounds) for r in regions), (width, mode, item.bounds))

    def test_next_sentence_avoids_existing_bounds(self):
        regions = display_regions(1920, 1040, "edges")
        prefs = Preferences()
        first = build_layout("给今天一点节奏", 7, regions, [], prefs)
        second = build_layout("让文字轻轻跳动", 8, regions, [first.bounds], prefs)
        self.assertFalse(first.bounds.intersects(second.bounds))


class SettingsTests(unittest.TestCase):
    def test_persistence_and_bad_values(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.ini")
            prefs = Preferences(jump=15, region="full", color="#ffaaee")
            store.save(prefs)
            self.assertEqual(store.load(), prefs)
            store.store.setValue("font_size", "bad")
            store.store.setValue("opacity", 300)
            store.store.setValue("region", "missing")
            store.store.setValue("color", "invalid")
            repaired = store.load()
            self.assertEqual(repaired.font_size, 32)
            self.assertEqual(repaired.opacity, 100)
            self.assertEqual(repaired.region, "edges")
            self.assertEqual(repaired.color, "#a9f4dc")


if __name__ == "__main__":
    unittest.main()
