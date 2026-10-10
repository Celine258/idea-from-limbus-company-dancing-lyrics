"""QQ protocol fixtures test behavior; native/live evidence is recorded separately."""
import base64
from concurrent.futures import Future
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication
from controls import ControlPanel
from lrc import LyricDocument, LyricLine
from overlay import LyricsOverlay
from settings import Preferences, SettingsStore
from qqmusic import QQMusicPlayer, QQSnapshot, parse_snapshot
import qqmusic_lyrics as lyrics

APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]


def packet(**updates):
    data = dict(source="QQMusic.exe", title="Hello", artist="Artist", album="Album", state="Playing",
                duration_ms=60000, position_ms=1000, updated_ms=100000, observed_ms=100500, rate=1)
    data.update(updates)
    return data


def song(**updates):
    data = dict(mid="004D7rAM2SPnrR", id=1, title="Hello", singer=[{"name": "Artist"}],
                interval=60, album={"title": "Album"})
    data.update(updates)
    return data


def encode(value):
    return base64.b64encode(value.encode()).decode()


class ManualExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, function, *args):
        future = Future()
        self.jobs.append((function, args, future))
        return future


class QQParsingTests(unittest.TestCase):
    def test_authoritative_timeline_age_rate_pause_and_end_clamp(self):
        self.assertEqual(parse_snapshot(packet()).position_ms, 1500)
        self.assertEqual(parse_snapshot(packet(rate=2)).position_ms, 2000)
        self.assertEqual(parse_snapshot(packet(state="Paused", updated_ms=1)).position_ms, 1000)
        self.assertEqual(parse_snapshot(packet(position_ms=59900)).position_ms, 60000)

    def test_other_apps_empty_and_transient_sessions_clear_lyrics(self):
        for data in (None, {}, [], packet(source="cloudmusic.exe"), packet(source="QQ.exe"),
                     packet(source="NotQQMusic.exe"), packet(title=""), packet(state="Changing"),
                     packet(state="Stopped"), packet(state="Closed"), packet(state="Opened")):
            self.assertIsNone(parse_snapshot(data))
        self.assertIsNotNone(parse_snapshot(packet(source=r"D:\中文 空格\QQMusic.exe")))

    def test_bad_timeline_and_metadata_do_not_start_invented_timer(self):
        for key in ("position_ms", "duration_ms", "rate", "updated_ms", "observed_ms"):
            for value in (True, -1, float("nan"), float("inf"), "1", None):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    parse_snapshot(packet(**{key: value}))
        for updates in ({"duration_ms": 0}, {"state": "invalid"}, {"title": "a"*1025},
                        {"artist": None}, {"album": "bad\x00"}, {"observed_ms": 1},
                        {"observed_ms": 1000000000}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                parse_snapshot(packet(**updates))

    def test_matching_rejects_wrong_version_cover_duration_album_and_ambiguity(self):
        wrong = [song(title="Hello (Live)"), song(singer=[{"name":"Cover"}]), song(interval=70),
                 song(album={"title":"Other"}), song(mid="invalid"), song(interval=True), None]
        self.assertIsNone(lyrics.select_song(wrong, "Hello", "Artist", 60000, "Album"))
        self.assertEqual(lyrics.select_song(wrong+[song()], "Hello", "Artist", 60000, "Album")["id"], 1)
        self.assertIsNone(lyrics.select_song([song(), song(mid="000aUmSX0YNqVF")], "Hello", "Artist", 60000))
        self.assertIsNone(lyrics.select_song([song()], "Hello", "", 60000))
        self.assertIsNone(lyrics.select_song([song()], "Hello", "Artist", 0))

    def test_artist_display_alias_unicode_html_and_all_artists_must_match(self):
        candidate = song(title="Let’s go & back", singer=[{"name":"Mili"},{"name":"KIHOW"}])
        self.assertIsNotNone(lyrics.select_song([candidate], "Let’s go &amp; back", "Mili (ミリー)/KIHOW", 60000))
        self.assertIsNone(lyrics.select_song([candidate], "Let’s go & back", "Mili", 60000))

    def test_base64_lrc_translation_blank_boundaries_offsets_and_no_fake_word_times(self):
        doc = lyrics.parse_lyrics({"lyric": encode("[offset:100]\n[00:01]Hi é 👩‍💻\n[00:02]\n[00:03]Goodbye"),
                                  "trans": encode("[offset:100]\n[00:01]你好\n[00:03]再见")})
        self.assertEqual(doc.offset_ms, 100)
        self.assertEqual(doc.lines[0].translation, "你好")
        self.assertEqual(doc.lines[1].text, "")
        self.assertEqual(doc.lines[0].words, ())
        self.assertEqual(doc.lines[0].text, "Hi é 👩‍💻")

    def test_damaged_or_unaligned_translation_preserves_original(self):
        for trans in ("broken!", encode("[00:05]中文"), encode("[00:00.9]甲\n[00:01.1]乙"), ""):
            doc = lyrics.parse_lyrics({"lyric": encode("[00:01]Hello"), "trans": trans})
            self.assertEqual(doc.lines[0].text, "Hello")
            self.assertEqual(doc.lines[0].translation, "")

    def test_empty_instrumental_encrypted_and_oversized_data(self):
        for text in ("", "[00:00]纯音乐，请欣赏", "[00:00]此歌曲为没有填词的纯音乐，请您欣赏"):
            self.assertIsNone(lyrics.parse_lyrics({"lyric": encode(text)}))
        for data in ({"crypt":1}, {"qrc":1}, {"lyric":"invalid!"},
                     {"lyric":encode("[00:01]"+"x"*2049)}, {"lyric":encode("[9999:00]bad")}):
            with self.assertRaises((ValueError, UnicodeError)):
                lyrics.parse_lyrics(data)

    def test_search_and_lyric_requests_are_anonymous_and_bounded(self):
        snapshot = parse_snapshot(packet(state="Paused"))
        search = {lyrics.SEARCH_MODULE:{"code":0,"data":{"body":{"song":{"list":[song()]}}}}}
        result = {"req_0":{"code":0,"data":{"lyric":encode("[00:01]Hello"),"trans":encode("[00:01]你好")}}}
        with patch.object(lyrics,"request_json",side_effect=[search,result]) as request:
            loaded = lyrics.load_song_lyrics(snapshot)
            self.assertEqual(loaded.document.lines[0].translation,"你好")
            self.assertEqual(request.call_count,2)
            self.assertEqual(request.call_args_list[1].args[1]["req_0"]["param"]["crypt"],0)
        actual = QQSnapshot("Between Two Worlds (Let's Lament)", "Mili (ミリー)/KIHOW", "Let's Lament", 362626, 3622, False)
        with patch.object(lyrics,"request_json",return_value={lyrics.SEARCH_MODULE:{"code":0,"data":{"body":{"song":{"list":[]}}}}}) as request:
            lyrics.load_song_lyrics(actual)
            query = request.call_args.args[1][lyrics.SEARCH_MODULE]["param"]["query"]
            self.assertEqual(query, "Between Two Worlds (Let's Lament) Mili KIHOW")
        with patch.object(lyrics,"request_json",side_effect=[search,OSError("offline"),{"lyric":"[00:01]Hello"}]) as request:
            self.assertIsNotNone(lyrics.load_song_lyrics(snapshot).document)
            self.assertTrue(request.call_args.args[0].startswith("https://c.y.qq.com/lyric/"))
        with patch.object(lyrics,"request_json",return_value={lyrics.SEARCH_MODULE:{"code":0,"data":{"body":{"song":{"list":[]}}}}}) as request:
            self.assertIsNone(lyrics.load_song_lyrics(snapshot).document)
            self.assertEqual(request.call_count,1)
        with patch.object(lyrics.urllib.request,"urlopen") as opening:
            opening.return_value.__enter__.return_value.read.return_value=b'{"code":0}'
            lyrics.request_json("https://u.y.qq.com/cgi-bin/musicu.fcg",{"x":1})
            req = opening.call_args.args[0]
            self.assertEqual(opening.call_args.kwargs["timeout"],5)
            self.assertNotIn("cookie", {k.lower() for k in req.headers})
            opening.return_value.__enter__.return_value.read.assert_called_once_with(lyrics.MAX_BYTES+1)


class QQPlayerTests(unittest.TestCase):
    def setUp(self):
        self.clock = [10.0]
        self.executor = ManualExecutor()
        self.player = QQMusicPlayer(clock=lambda:self.clock[0],executor=self.executor,autostart=False)
        self.documents = []
        self.player.document_changed.connect(self.documents.append)

    def tearDown(self):
        self.player.stop()

    def apply(self, **values):
        self.player.apply_snapshot(parse_snapshot(packet(state="Paused", **values)))

    def finish(self, index=0, document=None):
        document = document or LyricDocument([LyricLine(1000,"Hello")],[])
        self.executor.jobs[index][2].set_result(lyrics.LyricResult(document,"已同步"))
        self.player._poll()

    def test_pause_freeze_resume_seek_and_no_host_controls(self):
        self.apply()
        self.clock[0] += 100
        self.assertEqual(self.player.position(),1000)
        self.player.apply_snapshot(parse_snapshot(packet(observed_ms=100000)))
        self.clock[0] += .5
        self.assertAlmostEqual(self.player.position(),1500)
        changed = QSignalSpy(self.player.discontinuity)
        self.apply(position_ms=30000)
        self.assertEqual(changed.count(),1)
        for action in (self.player.toggle,lambda:self.player.seek(50000),lambda:self.player.set_volume(0)):
            action()
        self.assertEqual(self.player.position(),30000)
        self.assertFalse(self.player.playing)

    def test_lyrics_load_once_cache_and_explicit_retry(self):
        self.apply()
        for _ in range(10): self.apply(position_ms=1001)
        self.assertEqual(len(self.executor.jobs),1)
        self.finish()
        self.assertTrue(self.player.lyrics_received)
        self.apply(title="Other")
        self.apply()
        self.assertEqual(self.documents[-1].lines[0].text,"Hello")
        self.player.retry_lyrics()
        self.assertIn("重新",self.player.lyric_status)
        self.finish(1)
        self.assertEqual(len(self.executor.jobs),3)

    def test_switch_disconnect_and_late_result_cannot_reuse_old_lyrics(self):
        self.apply()
        self.apply(title="New")
        self.finish()
        self.assertIsNone(self.documents[-1])
        self.assertEqual(len(self.executor.jobs),2)
        self.player.disconnect()
        self.finish(1)
        self.assertFalse(self.player.connected)
        self.assertEqual(self.player.title,"")
        self.assertIsNone(self.documents[-1])

    def test_return_to_same_song_still_drops_old_request_generation(self):
        self.apply()
        self.apply(title="New")
        self.apply()
        self.finish()
        self.assertIsNone(self.documents[-1])
        self.assertEqual(len(self.executor.jobs),2)
        self.finish(1)
        self.assertEqual(self.documents[-1].lines[0].text,"Hello")

    def test_network_failure_is_visible_does_not_pause_or_retry_every_tick(self):
        self.player.apply_snapshot(parse_snapshot(packet()))
        self.executor.jobs[0][2].set_exception(OSError("offline"))
        with self.assertLogs("qqmusic", level="ERROR"):
            self.player._poll()
        self.assertTrue(self.player.playing)
        self.assertIn("网络",self.player.lyric_status)
        for _ in range(10): self.player._poll()
        self.assertEqual(len(self.executor.jobs),1)
        self.player.retry_lyrics()
        self.assertEqual(len(self.executor.jobs),2)

    def test_close_cancels_pending_and_does_not_launch_helper(self):
        self.apply()
        self.player.stop()
        self.assertTrue(self.executor.jobs[0][2].cancelled())
        self.player._poll()
        self.assertFalse(self.player.timer.isActive())

    def test_qq_panel_labels_retry_and_effect_changes_keep_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefs = Preferences()
            overlay = LyricsOverlay(self.player,prefs)
            panel = ControlPanel(self.player,overlay,prefs,SettingsStore(Path(temporary)/'settings.ini'))
            panel.show()
            self.apply()
            self.finish()
            QTest.qWait(20)
            self.assertEqual(panel.format_label.text(),"QQ 音乐")
            self.assertIn("QQ 音乐",panel.progress.toolTip())
            self.assertFalse(panel.play_button.isVisible())
            self.assertTrue(panel.retry_lyrics_button.isVisible())
            self.assertEqual(panel.lyric_label.text(),"已同步")
            before = (self.player.song_id,self.player.position(),self.player.playing)
            panel.animation_combo.setCurrentIndex(panel.animation_combo.findData("fall_shake"))
            panel.theme_combo.setCurrentIndex(panel.theme_combo.findData("special"))
            panel.translation_checkbox.setChecked(True)
            panel._select_page(1)
            panel.resize(900,560)
            QTest.qWait(20)
            self.assertEqual(before,(self.player.song_id,self.player.position(),self.player.playing))
            self.assertGreater(panel.effects_scroll.verticalScrollBar().maximum(),0)
            self.assertTrue(panel.footer_song.isVisible())
            panel.hide()
            panel.tray.hide()
            overlay.hide()
            panel.deleteLater()
            overlay.deleteLater()
            APP.processEvents()


class QQEntryTests(unittest.TestCase):
    def test_read_only_helper_and_packaged_entry_have_no_injection_or_python_requirement(self):
        script = (ROOT/'native/qqmusic_smtc.ps1').read_text(encoding='utf-8')
        for forbidden in ('TryPlayAsync','TryPauseAsync','TryChangePlaybackPositionAsync','GetCurrentSession'):
            self.assertNotIn(forbidden,script)
        self.assertIn("'QQMusic.exe'",script)
        self.assertIn('LastUpdatedTime.ToUnixTimeMilliseconds()',script)
        build = (ROOT/'build.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('$qqReader;native',build)
        entry = (ROOT/'release/启动QQ音乐联动.bat').read_text(encoding='utf-8')
        self.assertIn('--qqmusic',entry)
        self.assertNotIn('python',entry.lower())
        self.assertIn('_internal\\native\\qqmusic_smtc.ps1',entry)
        self.assertIn('-QQMusic',(ROOT/'启动QQ音乐联动.bat').read_text(encoding='utf-8'))

    def test_qq_guide_distinguishes_versions_dependencies_lyrics_and_launch_modes(self):
        guide = (ROOT/'QQMUSIC.md').read_text(encoding='utf-8')
        for value in ('22.52','Windows 10 1809','启动QQ音乐联动.bat','不需要 BetterNCM','整句 LRC',
                      '逐字演唱强调','严格匹配','重新获取歌词','纯音乐','只读','暂无 QQ 音乐逐字时间'):
            self.assertIn(value,guide)
        self.assertIn('[QQ 音乐使用说明](QQMUSIC.md)',(ROOT/'README.md').read_text(encoding='utf-8'))

    def test_update_build_checks_running_app_before_writes_and_renames_whole_directories(self):
        text = (ROOT/'build.ps1').read_text(encoding='utf-8-sig')
        self.assertLess(text.index("GetProcessesByName('FloatingLyrics')"),text.index('tools\\make_demo.py'))
        self.assertIn('[IO.Directory]::Move($target, $backup)',text)
        self.assertIn('[IO.Directory]::Move($ready, $target)',text)
        self.assertIn('[IO.Directory]::Move($backup, $target)',text)
        self.assertNotIn('Move-Item -LiteralPath',text)


if __name__ == '__main__':
    unittest.main()
