"""Real-time-unit mapping, stateless emphasis and premultiplied material tests."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from animation import _glyph_layout, build_layout, display_regions
from glyph_motion import GlyphState, glyph_states
from lrc import ActiveLine, LyricLine, LyricDocument, LyricTimeline, TimedWord, word_timing_status
from netease import validate_snapshot, NeteasePlayer
from settings import ANIMATION_STYLES, Preferences, SettingsStore
from text_effects import TextEffects, pixels_view
from tests.test_glyph_motion import rectangles
from tests.test_netease import packet

APP = QApplication.instance() or QApplication([])


class SingingSyncTests(unittest.TestCase):
    def test_switch_defaults_off_and_bool_persists_with_old_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.ini")
            self.assertIs(store.load().singing_sync, False)
            store.save(Preferences(singing_sync=True))
            self.assertIs(store.load().singing_sync, True)
            store.store.setValue("singing_sync", "false")
            self.assertIs(store.load().singing_sync, False)

    def test_user_and_document_offset_shift_line_and_words_together(self):
        doc = LyricDocument([LyricLine(1000, "你好", (TimedWord(1100, 1700, 0, 2),))], [], offset_ms=100)
        item = LyricTimeline(doc, delay_ms=300, animation_style="ripple_wave").visible(1600)[0]
        self.assertEqual(item.start_ms, 1200)
        self.assertEqual(item.words[0], TimedWord(1300, 1900, 0, 2))

    def test_multiline_wrapped_graphemes_map_to_original_codepoints(self):
        text = "你\né 👩‍💻 Hello"
        glyphs, _, _ = _glyph_layout(text, 32, 55)
        self.assertEqual([text[g.text_start:g.text_end] for g in glyphs], ["你", "é", " ", "👩‍💻", " ", "H", "e", "l", "l", "o"])
        words = (TimedWord(1000, 1800, text.index("Hello"), len(text)),)
        prefs = Preferences(animation_style="ripple_wave", singing_sync=True, jump=0)
        item = ActiveLine(0, text, 0, 3000, 1, 700, 2500, words)
        states = glyph_states(glyphs, prefs, item, 1400, 0, 32)
        self.assertTrue(all(s.emphasis == 1 for s in states[-5:]))
        self.assertTrue(all(s.emphasis == 0 for s in states[:-5]))

    def test_single_and_multi_character_units_use_provider_intervals_without_estimation(self):
        glyphs, _, _ = _glyph_layout("你好吗", 32, 300)
        words = (TimedWord(1000, 1200, 0, 1), TimedWord(1300, 1700, 1, 3))
        item = ActiveLine(0, "你好吗", 0, 3000, 1, 700, 2500, words)
        for style in ANIMATION_STYLES:
            prefs = Preferences(animation_style=style, singing_sync=True, jump=0)
            first = glyph_states(glyphs, prefs, item, 1100, 0, 32)
            self.assertEqual([s.emphasis for s in first], [1, 0, 0])
            gap = glyph_states(glyphs, prefs, item, 1250, 0, 32)
            self.assertEqual([s.emphasis for s in gap], [0, 0, 0])
            second = glyph_states(glyphs, prefs, item, 1500, 0, 32)
            self.assertEqual([s.emphasis for s in second], [0, 1, 1])
            self.assertAlmostEqual(second[1].scale, 1.08)
            self.assertEqual(glyph_states(glyphs, prefs, item, 1500, 0, 32), second)

    def test_short_unit_envelopes_and_invisible_characters_do_not_flash(self):
        glyphs, _, _ = _glyph_layout("甲", 32, 200)
        item = ActiveLine(0, "甲", 1000, 2000, 1, 1700, 1800, (TimedWord(1000, 1008, 0, 1),))
        prefs = Preferences(animation_style="fall_shake", singing_sync=True, jump=0)
        self.assertEqual(glyph_states(glyphs, prefs, item, 1000, 0, 32)[0].emphasis, 0)
        self.assertEqual(glyph_states(glyphs, prefs, item, 1004, 0, 32)[0].emphasis, 1)
        self.assertEqual(glyph_states(glyphs, prefs, item, 1008, 0, 32)[0].emphasis, 0)

    def test_missing_partial_and_complete_data_status(self):
        line = LyricLine(1000, "甲乙", (TimedWord(1000, 1500, 0, 1),))
        self.assertEqual(word_timing_status(None, True), "等待歌词")
        self.assertEqual(word_timing_status(None), "本曲无逐字时间")
        self.assertEqual(word_timing_status(LyricDocument([line], [])), "部分歌词可用")
        line = replace(line, words=(TimedWord(1000, 1500, 0, 2),))
        self.assertEqual(word_timing_status(LyricDocument([line], [])), "逐字时间可用")

    def test_malformed_optional_words_do_not_reject_plain_lyrics_and_switch_clears_timings(self):
        word = {"start_ms": 1100, "end_ms": 1800, "text_start": 0, "text_end": 2}
        document = validate_snapshot(packet(lyrics=[{"time_ms": 1000, "text": "你好", "words":
            [word, None, {**word,"end_ms":float("nan")}, {**word,"text_end":9}, {**word,"start_ms":1100.2,"end_ms":1100.3}]}]))["document"]
        self.assertEqual(document.lines[0].words, (TimedWord(1100, 1800, 0, 2),))
        player = NeteasePlayer()
        seen = []
        player.document_changed.connect(seen.append)
        player.apply(validate_snapshot(packet(lyrics=[{"time_ms":1000,"text":"你好","words":[word]}])))
        update = packet(position_ms=1300)
        del update["lyrics"]
        count = len(seen)
        player.apply(validate_snapshot(update))
        self.assertEqual(len(seen), count)
        player.apply(validate_snapshot(packet(song={"id":"other","title":"纯音乐","artist":""},lyrics=[])))
        self.assertIsNone(seen[-1])
        self.assertTrue(player.lyrics_received)
        player.disconnect()
        self.assertFalse(player.lyrics_received)

    def test_peak_halo_keeps_white_core_rgba_fade_and_zero_or_solid_modes(self):
        renderer = TextEffects()
        prefs = Preferences(animation_style="ripple_wave", singing_sync=True, color="#ff4080", jump=0)
        glyph = rectangles()[0]
        surface = renderer.prepare([glyph], 32, prefs, 1)
        base = renderer.render(surface, prefs, states=[GlyphState(0, 0)]).copy()
        full = renderer.render(surface, prefs, states=[GlyphState(0, 0, emphasis=1)]).copy()
        half = renderer.render(surface, prefs, states=[GlyphState(0, 0, .5, emphasis=1)]).copy()
        point = (round(8-surface.origin.x()), round(-10-surface.origin.y()))
        color = half.pixelColor(*point)
        self.assertEqual((color.red(), color.green(), color.blue()), (255,255,255))
        self.assertLessEqual(abs(color.alpha()-127), 2)
        self.assertGreater(int(pixels_view(full)[:,:,3].sum()), int(pixels_view(base)[:,:,3].sum()))
        self.assertLessEqual(np.max(np.abs(pixels_view(half).astype(int)-pixels_view(full).astype(int)*.5)), 2)
        misses, buffer = renderer.misses, id(surface.image)
        for level in (0,.2,.8,1):
            renderer.render(surface,prefs,states=[GlyphState(0,0,emphasis=level)])
        self.assertEqual(renderer.misses,misses)
        self.assertEqual(id(surface.image),buffer)
        for changed in (replace(prefs,glow_strength=0),replace(prefs,text_style="solid")):
            surface=renderer.prepare([glyph],32,changed,1)
            before=renderer.render(surface,changed,states=[GlyphState(0,0)]).copy()
            after=renderer.render(surface,changed,states=[GlyphState(0,0,emphasis=1)]).copy()
            self.assertEqual(before,after)

    def test_late_word_data_preserves_layout_and_pause_seek_rebuilds_the_same_frame(self):
        from overlay import LyricsOverlay
        class Player(QObject):
            changed,discontinuity=Signal(),Signal()
            playing,ended,duration,clock=False,False,7000,1800
            def position(self):return self.clock
            def energy_at(self,_):return .5
        player=Player();prefs=Preferences(animation_style="ripple_shake",singing_sync=True)
        overlay=LyricsOverlay(player,prefs)
        plain=LyricDocument([LyricLine(1000,"你好")],[])
        overlay.set_document(plain);overlay.show()
        try:
            overlay.grab();seed,layout=overlay.seed,overlay.layouts[0]
            overlay.set_document(LyricDocument([replace(plain.lines[0],words=(TimedWord(1700,2100,0,2),))],[]))
            first=overlay.grab().toImage()
            self.assertEqual(overlay.seed,seed)
            self.assertIs(overlay.layouts[0],layout)
            QTest.qWait(40);self.assertEqual(overlay.grab().toImage(),first)
            player.clock=2300;player.discontinuity.emit();self.assertNotEqual(overlay.grab().toImage(),first)
            player.clock=1800;player.discontinuity.emit();self.assertEqual(overlay.grab().toImage(),first)
            self.assertFalse(overlay.timer.isActive())
        finally:
            overlay.hide();overlay.deleteLater()

    def test_maximum_emphasis_fall_glow_and_imported_font_reserve_clear_edges(self):
        from fonts import FontLibrary
        with tempfile.TemporaryDirectory() as directory:
            library=FontLibrary(Path(directory))
            try:
                family=library.import_font(Path(__file__).parent/'fixtures/lyrics-test.ttf')[0][0]
                for style in ANIMATION_STYLES:
                    prefs=Preferences(animation_style=style,singing_sync=True,font_family=family,fall_distance=128,
                                      font_size=64,jump=30,angle=25)
                    layout=build_layout("AA中 Hello",730,display_regions(1280,900,"edges"),[],prefs)
                    self.assertIsNotNone(layout)
                    for dpr in (1,1.25,1.5):
                        renderer=TextEffects();surface=renderer.prepare(layout.glyphs,layout.font_size,prefs,dpr,30,layout.angle)
                        item=ActiveLine(0,"",0,3800,1,700,3200,(TimedWord(1000,3800,0,9),))
                        for position in (1200,3450,3799):
                            renderer.render(surface,prefs,states=glyph_states(layout.glyphs,prefs,item,position,1,
                                layout.font_size,730,layout.angle))
                            alpha=pixels_view(surface.image)[:,:,3]
                            self.assertFalse(alpha[0].any() or alpha[-1].any() or alpha[:,0].any() or alpha[:,-1].any())
            finally:library.close()


if __name__ == "__main__":
    unittest.main()
