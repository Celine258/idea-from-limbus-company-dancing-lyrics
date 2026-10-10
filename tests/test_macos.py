"""Portable mac adapter tests. Fixtures do not claim live macOS verification."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from concurrent.futures import Future
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import macos_netease as mac
from lrc import LyricDocument, LyricLine, TimedWord, word_timing_status

APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]


def info(title="Hello", position=1000, state="playing", artist="Artist", duration=60000):
    return mac.NowPlaying(state, title, artist, duration, position)


class ManualExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, function, *args):
        future = Future()
        self.jobs.append((function, args, future))
        return future

    def finish(self, index, result=None, error=None):
        if error:
            self.jobs[index][2].set_exception(error)
        else:
            self.jobs[index][2].set_result(result)


class MacParsingTests(unittest.TestCase):
    def snapshot(self, **updates):
        data = {"kMRMediaRemoteNowPlayingInfoTitle": "歌曲", "kMRMediaRemoteNowPlayingInfoArtist": "歌手",
                "kMRMediaRemoteNowPlayingInfoDuration": 120.25,
                "kMRMediaRemoteNowPlayingInfoElapsedTime": 1.75,
                "kMRMediaRemoteNowPlayingInfoPlaybackRate": 1}
        data.update(updates)
        return data

    def test_seconds_convert_to_ms_and_pause_is_explicit(self):
        result = mac.parse_nowplaying(self.snapshot())
        self.assertEqual((result.position_ms, result.duration_ms, result.state), (1750, 120250, "playing"))
        self.assertEqual(mac.parse_nowplaying(self.snapshot(kMRMediaRemoteNowPlayingInfoPlaybackRate=0)).state, "paused")

    def test_malformed_nonfinite_and_other_source_are_not_accepted(self):
        for data in (None, [], {}, self.snapshot(bundleIdentifier="com.apple.Music")):
            self.assertIsNone(mac.parse_nowplaying(data))
        for value in (True, float("nan"), float("inf"), -1, "invalid"):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                mac.parse_nowplaying(self.snapshot(kMRMediaRemoteNowPlayingInfoElapsedTime=value))
        self.assertIsNotNone(mac.parse_nowplaying(self.snapshot(bundleIdentifier="com.netease.163music")))

    def test_cli_discovery_has_no_import_time_process_and_read_is_only_get_raw(self):
        with patch.object(mac, "find_nowplaying_cli", return_value=None), patch.object(mac.subprocess, "run") as run:
            player = mac.MacNeteasePlayer(autostart=False)
            self.assertIn("brew install", player.status)
            run.assert_not_called()
            player.stop()
        with patch.object(mac.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(self.snapshot()))) as run:
            self.assertEqual(mac.query_nowplaying("/a path/中文/nowplaying-cli").position_ms, 1750)
            self.assertEqual(run.call_args.args[0], ["/a path/中文/nowplaying-cli", "get-raw"])
            self.assertEqual(run.call_args.kwargs["timeout"], 2)
        with patch.object(mac.subprocess, "run", side_effect=subprocess.TimeoutExpired("helper", 2)):
            with self.assertRaises(subprocess.TimeoutExpired):
                mac.query_nowplaying("helper")

    def test_search_requires_title_artist_and_duration_and_does_not_swap_instrumental(self):
        songs = [
            {"id": 1, "name": "Another", "artists": [{"name": "Artist"}], "duration": 60000},
            {"id": 2, "name": "Hello", "artists": [{"name": "Other"}], "duration": 60000},
            {"id": 3, "name": "Hello", "artists": [{"name": "Artist"}], "duration": 180000},
            {"id": 4, "name": "Hello", "artists": [{"name": "Artist"}], "duration": 60000},
        ]
        with patch.object(mac, "_api", return_value={"result": {"songs": songs}}):
            self.assertEqual(mac.search_song("Hello", "Artist", 60000), "4")
            self.assertIsNone(mac.search_song("Hello", "Wrong", 60000))
        with patch.object(mac, "search_song", return_value="4"), patch.object(mac, "_api", return_value={"nolyric": True}) as api:
            self.assertIsNone(mac.load_song_lyrics(info()))
            self.assertEqual(api.call_count, 1)

    def test_lrc_blank_boundaries_multiple_stamps_and_real_words_preserved(self):
        data = {"lrc": {"lyric": "[offset:100]\n[00:01.00]你好\n[00:02.00]\n[00:03][00:04]再见"},
                "yrc": {"lyric": "[1000,800](1000,200,0)你(1200,300,0)好"},
                "tlyric": {"lyric": "[00:01.00]中文翻译"}}
        doc = mac.parse_lyrics(data)
        self.assertEqual([line.start_ms for line in doc.lines], [1000, 2000, 3000, 4000])
        self.assertEqual(doc.lines[1].text, "")
        self.assertEqual(doc.lines[0].words, (TimedWord(1000, 1200, 0, 1), TimedWord(1200, 1500, 1, 2)))
        self.assertEqual((doc.offset_ms, doc.lines[0].translation), (100, "中文翻译"))

    def test_yrc_multiword_emoji_and_combining_marks_are_not_split_or_guessed(self):
        original = "Hi é 👩‍💻"
        doc = mac.parse_lyrics({"lrc": {"lyric": f"[00:01]{original}"}, "yrc": {"lyric":
            "[1000,1000](1000,200,0)Hi (1300,200,0)é (1700,200,0)👩‍💻"}})
        self.assertEqual(len(doc.lines[0].words), 3)
        self.assertEqual([original[w.text_start:w.text_end] for w in doc.lines[0].words], ["Hi ", "é ", "👩‍💻"])
        self.assertEqual(word_timing_status(doc), "逐字时间可用")

    def test_unaligned_bad_and_missing_lyrics_fall_back(self):
        for yrc in ("[1000,800](1000,200,0)different", "[1251,800](1251,200,0)Hello", "bad data"):
            doc = mac.parse_lyrics({"lrc": {"lyric": "[00:01]Hello"}, "yrc": {"lyric": yrc}})
            self.assertEqual(doc.lines[0].words, ())
        self.assertIsNone(mac.parse_lyrics({}))
        self.assertIsNone(mac.parse_lyrics({"nolyric": True}))
        self.assertIsNone(mac.parse_lyrics({"lrc": {"lyric": "[00:00]纯音乐，请欣赏"}}))
        doc = mac.parse_lyrics({"yrc": {"lyric": "[1000,500](1000,500,0)Hello"}})
        self.assertEqual(doc.lines[0].text, "Hello")
        self.assertEqual(doc.lines[0].words, (TimedWord(1000, 1500, 0, 5),))


class MacOffsetTests(unittest.TestCase):
    def test_zero_offsets_unicode_paths_and_reload(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "中文 设置" / "offsets.json"
            store = mac.OffsetStore(path)
            store.set("歌|名", "人", 200)
            store.set("歌", "名|人", 0)
            restored = mac.OffsetStore(path)
            self.assertEqual(restored.get("歌|名", "人"), 200)
            self.assertEqual(restored.get("歌", "名|人", 400), 0)
            self.assertEqual(restored.get("新歌", "人", 400), 400)

    def test_corrupt_and_failed_atomic_write_preserve_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "offsets.json"
            path.write_text("broken", encoding="utf-8")
            store = mac.OffsetStore(path)
            with self.assertRaises(ValueError):
                store.set("song", "artist", 100)
            self.assertEqual(path.read_text(), "broken")
            path.write_text('{"song|artist": 200}', encoding="utf-8")
            store = mac.OffsetStore(path)
            with patch.object(mac.Path, "replace", side_effect=PermissionError("save failed")), self.assertRaises(OSError):
                store.set("song", "artist", 400)
            self.assertEqual(store.get("song", "artist"), 200)
            self.assertEqual(mac.OffsetStore(path).get("song", "artist"), 200)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


class MacPlayerTests(unittest.TestCase):
    def setUp(self):
        self.clock = [0.0]
        self.executor = ManualExecutor()
        self.player = mac.MacNeteasePlayer(query=lambda: None, executor=self.executor,
                                         clock=lambda: self.clock[0], autostart=False)
        self.documents = []
        self.player.document_changed.connect(self.documents.append)

    def tearDown(self):
        self.player.stop()

    def test_progress_pause_seek_repeat_snapshot_and_disconnect(self):
        self.player.apply(info())
        self.clock[0] = .5
        self.assertEqual(self.player.position(), 1500)
        self.player.apply(info())  # Identical rounded system snapshot must not reset the clock.
        self.clock[0] = 1
        self.assertEqual(self.player.position(), 2000)
        self.player.apply(info(position=1800, state="paused"))
        self.clock[0] = 20
        self.assertEqual(self.player.position(), 1800)
        self.player.apply(info(position=20000))
        self.assertEqual(self.player.position(), 20000)
        self.player.apply(None)
        self.assertFalse(self.player.playing)
        self.assertIsNone(self.documents[-1])

    def test_late_lyrics_after_switch_and_disconnect_are_discarded(self):
        old = LyricDocument([LyricLine(1000, "old")], [])
        current = LyricDocument([LyricLine(1000, "current")], [])
        self.player.apply(info("old"))
        self.player._tick()
        self.player.apply(info("current"))
        self.executor.finish(1, old)
        self.player._tick()
        self.assertNotIn(old, self.documents)
        self.executor.finish(2, current)
        self.player._tick()
        self.assertIs(self.documents[-1], current)
        self.player.apply(info("third"))
        self.player._tick()
        self.player.apply(None)
        self.executor.finish(3, old)
        self.player._tick()
        self.assertIsNone(self.documents[-1])

    def test_cached_no_lyrics_and_fetched_lyrics_update_status(self):
        self.player.apply(info("instrumental"))
        self.player._tick()
        self.executor.finish(1, None)
        self.player._tick()
        self.assertTrue(self.player.lyrics_received)
        self.assertIn("保持空白", self.player.status)
        self.player.apply(info("other"))
        self.player.apply(info("instrumental"))
        self.assertTrue(self.player.lyrics_received)
        self.assertFalse(self.player._needs_lyrics)

    def test_lookup_failure_retries_and_does_not_change_playback(self):
        self.player.apply(info())
        self.player._tick()
        self.executor.finish(1, error=OSError("offline"))
        with self.assertLogs(mac.logger, level="WARNING"):
            self.player._tick()
        self.assertTrue(self.player.playing)
        self.assertIn("10 秒", self.player.status)
        self.assertEqual(len(self.executor.jobs), 2)
        self.clock[0] = 11
        self.player._tick()
        self.assertEqual(len(self.executor.jobs), 3)

    def test_offsets_and_visual_settings_never_control_music_or_progress(self):
        self.player.apply(info())
        self.player.adjust_offset(200)
        self.assertEqual((self.player.lyric_offset_ms, self.player.position()), (200, 1000))
        with patch.object(mac.subprocess, "run") as run:
            self.player.toggle()
            self.player.seek(40000)
            self.player.set_volume(0)
            self.assertEqual((self.player.position(), self.player.playing), (1000, True))
            run.assert_not_called()
        self.assertFalse(self.player.has_audio_data)
        self.assertEqual(self.player.energy_at(0), 0)

    def test_stop_drops_results_and_cancels_pending_jobs(self):
        self.player.apply(info())
        self.player._tick()
        self.player.stop()
        self.assertTrue(all(future.cancelled() for _, _, future in self.executor.jobs))
        self.player.apply(info("ignored"))
        self.player._tick()
        self.assertEqual(self.player.title, "Hello")
        self.assertEqual(len(self.executor.jobs), 2)

    def test_poll_failure_is_visible_and_does_not_keep_stale_lyrics(self):
        self.player.apply(info())
        self.player._tick()
        self.executor.finish(0, error=ValueError("unsupported helper output"))
        with self.assertLogs(mac.logger, level="WARNING"):
            self.player._tick()
        self.assertFalse(self.player.playing)
        self.assertIn("nowplaying-cli", self.player.status)
        self.assertIsNone(self.documents[-1])
        self.assertGreaterEqual(self.player._next_poll, 2)

    def test_song_offset_zero_is_restored_and_new_song_inherits_without_moving_clock(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = mac.OffsetStore(Path(temporary) / "offsets.json")
            store.set("zero", "Artist", 0)
            self.player.set_offset_store(store)
            self.player.apply(info("first"))
            self.player.adjust_offset(400)
            self.player.apply(info("new"))
            self.assertEqual(self.player.lyric_offset_ms, 400)
            self.player.apply(info("zero"))
            self.assertEqual((self.player.lyric_offset_ms, self.player.position()), (0, 1000))

    def test_blocked_worker_does_not_block_qt_event_loop(self):
        released, entered = threading.Event(), threading.Event()
        def query():
            entered.set()
            released.wait(3)
            return None
        player = mac.MacNeteasePlayer(query=query, autostart=False)
        delivered = []
        try:
            player._tick()
            self.assertTrue(entered.wait(1))
            QTimer.singleShot(0, lambda: delivered.append(True))
            QTest.qWait(30)
            self.assertEqual(delivered, [True])
            self.assertFalse(player._poll_future.done())
        finally:
            released.set()
            player.stop()


class MacPlatformTests(unittest.TestCase):
    def test_platform_defaults_and_theme_font_keep_windows_unchanged(self):
        import fonts
        import settings
        import themes
        self.assertEqual(settings.default_font_family("win32"), "Microsoft YaHei UI")
        self.assertEqual(settings.default_font_family("darwin"), "PingFang SC")
        self.assertEqual([value for _, value in fonts.preset_fonts("darwin")], ["PingFang SC", "Songti SC", "Kaiti SC"])
        self.assertEqual([value for _, value in fonts.preset_fonts("win32")], ["Microsoft YaHei UI", "SimSun", "KaiTi"])
        with patch.object(themes, "DEFAULT_FONT_FAMILY", "PingFang SC"):
            self.assertIn("font-family: 'PingFang SC'", themes.theme_stylesheet("light"))
        with patch.object(themes, "DEFAULT_FONT_FAMILY", "Microsoft YaHei UI"):
            self.assertIn("font-family: 'Microsoft YaHei UI'", themes.theme_stylesheet("light"))

    def test_overlay_retains_tool_input_transparency_and_applies_lyric_only_offset(self):
        from overlay import LyricsOverlay
        from settings import Preferences
        player = mac.MacNeteasePlayer(query=lambda: None, autostart=False)
        player.apply(info())
        player.adjust_offset(200)
        overlay = LyricsOverlay(player, Preferences(delay_ms=300))
        try:
            doc = LyricDocument([LyricLine(1000, "Hello", (TimedWord(1100, 1200, 0, 5),))], [])
            overlay.set_document(doc)
            self.assertEqual(overlay.timeline.lines[0].start_ms, 1100)
            self.assertEqual(overlay.timeline.lines[0].words[0].start_ms, 1200)
            self.assertEqual(player.position(), 1000)
            self.assertEqual(overlay.windowFlags() & Qt.WindowType.WindowType_Mask, Qt.WindowType.Tool)
            self.assertTrue(overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
            overlay.close()
            with patch("overlay.sys", SimpleNamespace(platform="darwin")):
                other = LyricsOverlay(player, Preferences())
            self.assertTrue(other.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow))
            other.close()
            other.deleteLater()
        finally:
            overlay.close()
            overlay.deleteLater()
            player.stop()

    def test_external_control_panel_does_not_move_music_when_changing_effects(self):
        from controls import ControlPanel
        from overlay import LyricsOverlay
        from settings import Preferences, SettingsStore
        with tempfile.TemporaryDirectory() as temporary:
            player = mac.MacNeteasePlayer(query=lambda: None, clock=lambda: 0, autostart=False)
            player.apply(info())
            prefs = Preferences()
            overlay = LyricsOverlay(player, prefs)
            panel = ControlPanel(player, overlay, prefs, SettingsStore(Path(temporary) / "settings.ini"))
            try:
                with patch.object(mac.subprocess, "run") as run:
                    panel.theme_combo.setCurrentIndex(panel.theme_combo.findData("dark"))
                    panel.animation_combo.setCurrentIndex(panel.animation_combo.findData("fall_shake"))
                    panel._refresh_position()
                    self.assertEqual((player.playing, player.position()), (True, 1000))
                    run.assert_not_called()
                self.assertTrue(panel.progress.display_only)
            finally:
                panel.refresh_timer.stop()
                panel.font_preview.timer.stop()
                panel.tray.hide()
                panel.hide()
                panel.deleteLater()
                overlay.close()
                overlay.deleteLater()
                player.stop()

    def test_entry_rejects_windows_and_help_does_not_start_qt(self):
        import main_mac
        with patch.object(main_mac.sys, "platform", "win32"):
            self.assertEqual(main_mac.main([]), 2)
        with patch.object(main_mac.sys, "platform", "darwin"), patch.object(mac, "find_nowplaying_cli", return_value=None):
            self.assertEqual(main_mac.main(["--check"]), 1)

    def test_mac_without_tray_can_restore_panel_from_application_activation(self):
        import controls
        from overlay import LyricsOverlay
        from settings import Preferences, SettingsStore
        with tempfile.TemporaryDirectory() as temporary:
            player = mac.MacNeteasePlayer(query=lambda: None, autostart=False)
            prefs = Preferences()
            overlay = LyricsOverlay(player, prefs)
            with patch.object(controls, "sys", SimpleNamespace(platform="darwin")), \
                    patch.object(controls.QSystemTrayIcon, "isSystemTrayAvailable", return_value=False):
                panel = controls.ControlPanel(player, overlay, prefs, SettingsStore(Path(temporary) / "settings.ini"))
                try:
                    self.assertTrue(panel.tray_button.isEnabled())
                    self.assertEqual(panel.tray_button.text(), "隐藏面板")
                    with patch.object(panel, "show_panel") as show:
                        panel.hide()
                        panel._on_app_state_changed(Qt.ApplicationState.ApplicationActive)
                        show.assert_called_once()
                finally:
                    panel.refresh_timer.stop()
                    panel.font_preview.timer.stop()
                    panel.font_library.close()
                    panel.hide()
                    panel.tray.hide()
                    panel.deleteLater()
                    overlay.close()
                    overlay.deleteLater()
                    player.stop()

    def test_attribution_docs_and_scripts_are_present_without_bundled_helper(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = (ROOT / "MACOS.md").read_text(encoding="utf-8")
        self.assertIn("@qingyin-alice-zhong", readme)
        self.assertIn("5109df2c99ee87ee6ad5370fed70fa5d880336a5", guide)
        self.assertIn("尚未完成 macOS 真机", guide)
        self.assertIn("macOS", (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8"))
        self.assertFalse((ROOT / "assets/nowplaying-cli").exists())
        self.assertNotIn("requests", (ROOT / "requirements.txt").read_text())
        from tests.test_workflow_docs import DOCUMENTS
        self.assertIn(ROOT / "MACOS.md", DOCUMENTS)

    def test_shell_syntax_and_non_mac_guard(self):
        git = shutil.which("git")
        git_bash = Path(git).resolve().parents[1] / "bin/bash.exe" if git else None
        bash = str(git_bash) if git_bash and git_bash.is_file() else ("/bin/bash" if Path("/bin/bash").is_file() else None)
        if not bash:
            self.skipTest("本机没有可用 Bash；macOS CI 验证脚本语法")
        for name in ("start.sh", "安装.sh", "卸载.sh", "启动.command"):
            result = subprocess.run([bash, "-n", str(ROOT / name)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
        if os.name == "nt":
            result = subprocess.run([bash, str(ROOT / "安装.sh")], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
