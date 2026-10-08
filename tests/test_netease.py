import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QApplication
from netease import NeteasePlayer, NeteaseBridge, validate_snapshot, read_bridge_config
from tools.package_netease import package_plugin

APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]


def packet(**changes):
    data = {"protocol": 1, "client": "3.1.41", "song": {"id": "1", "title": "测试歌曲", "artist": "测试歌手"},
            "duration_ms": 60000, "position_ms": 1200, "playing": True, "enabled": True,
            "lyrics": [{"time_ms": 1000, "text": "原创测试歌词"}, {"time_ms": 30000, "text": "跳转后的歌词"}]}
    data.update(changes)
    return data


class NeteasePlayerTests(unittest.TestCase):
    def test_protocol_accepts_both_versions_and_rejects_unverified_clients(self):
        for client in ("3.1.40", "3.1.41"):
            self.assertEqual(validate_snapshot(packet(client=client))["client"], client)
        for client in ("3.1.39", "3.1.42", "3.1.40.205461", None):
            with self.assertRaises(ValueError):
                validate_snapshot(packet(client=client))

    def setUp(self):
        self.now = 10.
        self.player = NeteasePlayer(clock=lambda: self.now)

    def _font_validation(self, mutate_transport=False):
        from netease_validation import NeteaseSmokeCheck
        from settings import Preferences
        self.player.apply(validate_snapshot(packet()))
        prefs = Preferences()
        def select(family):
            prefs.font_family = family
        def import_font(_path):
            select("Test custom family")
            return True
        def capture(_path):
            self.now += .4
            if mutate_transport:
                self.player.apply(validate_snapshot(packet(position_ms=5000, seek=True)))
        check = object.__new__(NeteaseSmokeCheck)
        check.player, check.jumps = self.player, 0
        check.directory, check.font_fixture = Path("unused-report"), Path("unused-font.ttf")
        check.panel = SimpleNamespace(prefs=prefs, font_combo=SimpleNamespace(findData=lambda family: family, setCurrentIndex=select),
                                      grab=lambda: SimpleNamespace(save=capture), import_font=import_font,
                                      store=SimpleNamespace(load=lambda: prefs), font_library=SimpleNamespace(directory=Path("unused-fonts")))
        self.player.discontinuity.connect(check._jump)
        library = Mock()
        library.restore_family.side_effect = lambda family: (family, "")
        with patch("netease_validation.FontLibrary", return_value=library), \
                patch("netease_validation.QFontInfo", side_effect=lambda font: SimpleNamespace(family=lambda: font.families()[0])):
            check._check_fonts()
        return check

    def test_font_validator_accepts_normal_playback_time_advancing(self):
        check = self._font_validation()
        self.assertGreater(check.font_evidence["positionDeltaMs"], 750)
        self.assertTrue(check.font_checks["fontSwitchKeepsPlayback"])
        self.assertTrue(check.font_evidence["transportUnchanged"])

    def test_font_validator_rejects_playback_anchor_changes(self):
        check = self._font_validation(mutate_transport=True)
        self.assertFalse(check.font_checks["fontSwitchKeepsPlayback"])
        self.assertFalse(check.font_evidence["transportUnchanged"])

    def test_progress_pause_resume_and_seek_are_authoritative(self):
        self.player.apply(validate_snapshot(packet()))
        self.now += .2
        self.assertAlmostEqual(self.player.position(), 1400)
        self.player.apply(validate_snapshot(packet(position_ms=1500, playing=False)))
        self.now += 20
        self.assertEqual(self.player.position(), 1500)
        jumps = QSignalSpy(self.player.discontinuity)
        self.player.apply(validate_snapshot(packet(position_ms=32000, seek=True)))
        self.assertEqual(self.player.position(), 32000)
        self.assertEqual(jumps.count(), 1)
        self.now += 10
        self.assertEqual(self.player.position(), 33500, "停滞时不能无限外推")
        self.assertIsNone(self.player.path)
        self.assertFalse(hasattr(self.player, "media"), "联动模式不创建第二个音频播放器")

    def test_song_switch_clears_lyrics_before_the_new_document_and_disconnect(self):
        documents = []
        self.player.document_changed.connect(documents.append)
        self.player.apply(validate_snapshot(packet()))
        self.player.apply(validate_snapshot(packet(song={"id": "2", "title": "纯音乐", "artist": ""}, lyrics=[])))
        self.assertEqual(self.player.title, "纯音乐")
        self.assertIsNone(documents[-1])
        self.player.disconnect()
        self.assertFalse(self.player.playing)
        self.assertFalse(self.player.connected)
        self.assertIsNone(documents[-1])

    def test_progress_only_packet_preserves_lyrics_and_disabled_effects_pause(self):
        documents = []
        self.player.document_changed.connect(documents.append)
        data = packet()
        self.player.apply(validate_snapshot(data))
        count = len(documents)
        data.pop("lyrics")
        data.update(position_ms=1300, enabled=False)
        self.player.apply(validate_snapshot(data))
        self.assertEqual(len(documents), count)
        self.assertFalse(self.player.playing)
        self.assertFalse(self.player.enabled)

    def test_energy_smooths_but_pause_freezes_and_old_levels_decay(self):
        self.player.apply(validate_snapshot(packet()))
        self.player.set_energy(.8)
        self.now += .1
        level = self.player.energy_at(1300)
        self.assertGreater(level, .6)
        self.player.apply(validate_snapshot(packet(playing=False)))
        self.now += .5
        self.assertEqual(self.player.energy_at(1300), level)
        self.player.apply(validate_snapshot(packet()))
        self.now += .1
        self.assertLess(self.player.energy_at(1300), level)

    def test_invalid_packets_are_rejected_before_mutating_state(self):
        for changes in ({"position_ms": float("nan")}, {"duration_ms": True}, {"playing": "false"},
                        {"client": "3.2.0"}, {"protocol": 2}, {"lyrics": [{"time_ms": 0, "text": 8}]},
                        {"lyrics": [None]}, {"song": {"id": 1, "title": "bad", "artist": ""}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_snapshot(packet(**changes))

    def test_packaging_preserves_existing_preferences_and_connection_secret(self):
        import zipfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefs = root / "settings.ini"
            prefs.write_bytes(b"[General]\ncolor=#ffffff\nvolume=24\n")
            before = prefs.read_bytes()
            presets = root / "effect-presets.json"
            preset_bytes = b'{"version":1,"presets":[]}'
            presets.write_bytes(preset_bytes)
            output = root / "FloatingLyrics.plugin"
            package_plugin(root, output, '"C:/app/FloatingLyrics.exe" --netease --background')
            config = read_bridge_config(root / "netease-bridge.json")
            package_plugin(root, output, '"C:/new/FloatingLyrics.exe" --netease --background')
            self.assertEqual(read_bridge_config(root / "netease-bridge.json")["token"], config["token"])
            self.assertEqual(prefs.read_bytes(), before)
            self.assertEqual(presets.read_bytes(), preset_bytes)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {"manifest.json", "adapter.js", "index.js", "bridge-config.json"})
                self.assertEqual(json.loads(archive.read("bridge-config.json"))["token"], config["token"])

    @unittest.skipUnless(shutil.which("node"), "Node.js 用于插件适配器测试")
    def test_javascript_adapter_contract(self):
        result = subprocess.run(["node", str(ROOT / "tests/test_netease_adapter.cjs")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js 用于插件生命周期测试")
    def test_legacy_lyric_cache_isolation(self):
        result = subprocess.run(["node", str(ROOT / "tests/test_legacy_lyrics.cjs")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js 用于插件生命周期测试")
    def test_javascript_plugin_lifecycle_and_non_recursive_dom_updates(self):
        result = subprocess.run(["node", str(ROOT / "tests/test_netease_plugin.cjs")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js 用于宿主播放安全测试")
    def test_javascript_host_progress_seek_and_callback_isolation(self):
        result = subprocess.run(["node", str(ROOT / "tests/test_netease_host.cjs")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js 用于真实客户端验证器测试")
    def test_host_validator_rejects_frozen_progress_and_unrequested_skips(self):
        result = subprocess.run(["node", str(ROOT / "tests/test_netease_host_validation.cjs")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js 用于真实逐字验证器测试")
    def test_word_validator_requires_real_words_audio_and_completed_seek(self):
        result = subprocess.run(["node", str(ROOT / "tests/test_netease_words_validation.cjs")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.player = NeteasePlayer()
        self.token = "a" * 64
        self.bridge = NeteaseBridge(self.player, self.token, port=0)
        self.bridge.start()
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.bridge.close()
        QTest.qWait(20)
        self.bridge.deleteLater()
        self.player.deleteLater()
        APP.processEvents()

    def connect(self):
        client = QWebSocket()
        connected = QSignalSpy(client.connected)
        self.clients.append(client)
        client.open(QUrl(f"ws://127.0.0.1:{self.bridge.server.serverPort()}"))
        for _ in range(100):
            if connected.count():
                return client
            QTest.qWait(10)
        self.fail("本地插件连接超时")

    def send(self, client, data):
        client.sendTextMessage(json.dumps(data))
        QTest.qWait(50)

    def test_real_local_socket_auth_sync_commands_and_disconnect(self):
        client = self.connect()
        shows = QSignalSpy(self.bridge.show_panel)
        visibility = QSignalSpy(self.bridge.enabled_changed)
        self.send(client, dict(packet(), token=self.token))
        self.assertTrue(self.player.connected)
        self.assertEqual(self.player.title, "测试歌曲")
        self.send(client, dict(packet(position_ms=1400), token=self.token))
        self.assertEqual(visibility.count(), 1, "进度刷新不能反复打开用户隐藏的歌词")
        self.send(client, {"kind": "show", "token": self.token})
        self.assertEqual(shows.count(), 1)
        self.assertEqual(self.bridge.server.serverAddress().toString(), "127.0.0.1")
        client.close()
        QTest.qWait(50)
        self.assertFalse(self.player.connected)

    def test_unauthenticated_second_client_cannot_replace_current_song(self):
        owner = self.connect()
        self.send(owner, dict(packet(), token=self.token))
        intruder = self.connect()
        self.send(intruder, dict(packet(song={"id": "bad", "title": "bad", "artist": ""}), token="b" * 64))
        self.assertEqual(self.player.title, "测试歌曲")
        self.assertTrue(self.player.connected)

    def test_invalid_json_and_timeout_do_not_leave_lyrics_running(self):
        owner = self.connect()
        self.send(owner, dict(packet(), token=self.token))
        owner.sendTextMessage("broken json")
        QTest.qWait(50)
        self.assertFalse(self.player.playing)
        owner = self.connect()
        self.send(owner, dict(packet(), token=self.token))
        self.bridge.last_packet -= 5
        self.bridge._check_timeout()
        QTest.qWait(50)
        self.assertFalse(self.player.connected)


if __name__ == "__main__":
    unittest.main()
