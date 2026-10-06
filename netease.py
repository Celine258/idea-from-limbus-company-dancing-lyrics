"""Authenticated, localhost-only playback data from the BetterNCM plugin."""
import json
import math
from pathlib import Path
import secrets
import time
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QHostAddress
from PySide6.QtWebSockets import QWebSocketServer
from lrc import LyricDocument, LyricLine

PORT = 38473
PROTOCOL = 1
SUPPORTED_CLIENT = "3.1.41"


def read_bridge_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    token = config.get("token", "")
    if not isinstance(token, str) or len(token) != 64:
        raise ValueError("网易云插件连接配置无效，请重新安装联动插件。")
    return config


def _number(value, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("同步时间无效")
    return max(0, min(maximum, value))


def validate_snapshot(data: dict) -> dict:
    if not isinstance(data, dict) or data.get("protocol") != PROTOCOL:
        raise ValueError("插件协议不兼容")
    if data.get("client") != SUPPORTED_CLIENT:
        raise ValueError("网易云版本尚未验证，请更新联动插件。")
    song = data.get("song")
    if not isinstance(song, dict):
        raise ValueError("歌曲信息无效")
    result = dict(data)
    for key in ("id", "title", "artist"):
        if not isinstance(song.get(key), str) or len(song[key]) > 1024:
            raise ValueError("歌曲信息无效")
    result["duration_ms"] = int(_number(data.get("duration_ms"), 24 * 3600 * 1000))
    result["position_ms"] = _number(data.get("position_ms"), result["duration_ms"] or 24 * 3600 * 1000)
    if not isinstance(data.get("playing"), bool) or not isinstance(data.get("enabled"), bool):
        raise ValueError("播放状态无效")
    lines = data.get("lyrics")
    if lines is not None:
        if not isinstance(lines, list) or len(lines) > 5000:
            raise ValueError("歌词数量无效")
        cleaned = []
        for line in lines:
            if not isinstance(line, dict) or not isinstance(line.get("text"), str) or len(line["text"]) > 2048:
                raise ValueError("歌词内容无效")
            cleaned.append(LyricLine(int(_number(line.get("time_ms"), 24 * 3600 * 1000)), line["text"]))
        result["document"] = LyricDocument(sorted(cleaned, key=lambda line: line.start_ms), []) if cleaned else None
    return result


class NeteasePlayer(QObject):
    changed = Signal()
    discontinuity = Signal()
    error = Signal(str)
    document_changed = Signal(object)
    is_external = True
    path = None

    def __init__(self, clock=time.monotonic, parent=None):
        super().__init__(parent)
        self._clock = clock
        self.song_id = self.title = self.artist = ""
        self.duration = 0
        self.playing = self.ended = self.connected = False
        self.enabled = True
        self.status = "等待网易云插件连接"
        self._anchor = 0.0
        self._at = clock()
        self.has_audio_data = False
        self.analysis_error = ""
        self._level = self._energy = 0.0
        self._level_at = self._energy_at = clock()

    def position(self):
        elapsed = min(1500, max(0, (self._clock() - self._at) * 1000)) if self.playing else 0
        return min(self.duration, self._anchor + elapsed) if self.duration else 0

    def apply(self, snapshot):
        now = self._clock()
        song = snapshot["song"]
        switched = song["id"] != self.song_id
        jumped = switched or bool(snapshot.get("seek")) or abs(snapshot["position_ms"] - self.position()) > 750
        if switched:
            self.document_changed.emit(None)
            self._energy = 0
        self.song_id, self.title, self.artist = song["id"], song["title"], song["artist"]
        self.duration = snapshot["duration_ms"]
        self._anchor, self._at = snapshot["position_ms"], now
        self.enabled = snapshot["enabled"]
        self.playing = snapshot["playing"] and self.enabled
        self.ended = self.duration > 0 and self._anchor >= self.duration
        self.connected = True
        self.status = "已连接网易云音乐" if self.enabled else "网易云插件已关闭歌词"
        if jumped:
            self.discontinuity.emit()
        if "document" in snapshot:
            self.document_changed.emit(snapshot["document"])
        self.changed.emit()

    def disconnect(self):
        self._anchor = self.position()
        self.playing = self.connected = False
        self.status = "连接已断开，请在网易云中启用跳动的歌词"
        self.document_changed.emit(None)
        self.changed.emit()

    def set_energy(self, level):
        if math.isfinite(level):
            self._level = max(0, min(1, level))
            self._level_at = self._clock()
            self.has_audio_data = True
            self.analysis_error = ""

    def energy_at(self, _position):
        if not self.playing:
            return self._energy
        now = self._clock()
        target = self._level if now - self._level_at < .5 else 0
        dt = min(.15, max(0, now - self._energy_at))
        self._energy_at = now
        self._energy += (target - self._energy) * (1 - math.exp(-dt / (.045 if target > self._energy else .18)))
        return self._energy

    # Playback and volume remain in NetEase. This adapter never opens an audio file.
    def toggle(self):
        pass

    def seek(self, _value):
        pass

    def set_volume(self, _value):
        pass

    def stop(self):
        self.disconnect()


class NeteaseBridge(QObject):
    show_panel = Signal()
    enabled_changed = Signal(bool)

    def __init__(self, player, token, port=PORT, parent=None):
        super().__init__(parent)
        self.player, self.token = player, token
        self.server = QWebSocketServer("FloatingLyrics", QWebSocketServer.SslMode.NonSecureMode, self)
        self.server.setMaxPendingConnections(4)
        self.server.newConnection.connect(self._accept)
        self.sockets = set()
        self.owner = None
        self._enabled = None
        self.last_packet = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._check_timeout)
        self.port = port

    def start(self):
        if not self.server.listen(QHostAddress.SpecialAddress.LocalHost, self.port):
            raise RuntimeError("网易云联动已运行，或本地连接端口被占用。请检查系统托盘。")
        self.timer.start()

    def _accept(self):
        socket = self.server.nextPendingConnection()
        socket.setMaxAllowedIncomingMessageSize(1024 * 1024)
        self.sockets.add(socket)
        socket.textMessageReceived.connect(lambda text: self._receive(socket, text))
        socket.disconnected.connect(lambda: self._closed(socket))
        QTimer.singleShot(5000, lambda: socket.close() if socket in self.sockets and socket is not self.owner else None)

    def _receive(self, socket, text):
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or not isinstance(data.get("token"), str) or not secrets.compare_digest(data["token"], self.token):
                socket.close()
                return
            if self.owner is not None and self.owner is not socket:
                socket.close()
                return
            if data.get("kind") == "show":
                self.show_panel.emit()
                return
            snapshot = validate_snapshot(data)
            self.owner = socket
            self.last_packet = time.monotonic()
            self.player.apply(snapshot)
            if self._enabled != self.player.enabled:
                self._enabled = self.player.enabled
                self.enabled_changed.emit(self.player.enabled)
            socket.sendTextMessage('{"ok":true}')
        except (ValueError, TypeError, KeyError):
            # Invalid input must not change the active song or leave a broken socket alive.
            socket.close()

    def _closed(self, socket):
        self.sockets.discard(socket)
        if self.owner is socket:
            self.owner = None
            self._enabled = None
            self.player.disconnect()
        socket.deleteLater()

    def _check_timeout(self):
        if self.owner and time.monotonic() - self.last_packet > 4:
            self.owner.close()

    def close(self):
        self.timer.stop()
        if self.owner:
            self.owner.sendTextMessage('{"kind":"shutdown"}')
            self.owner.flush()
        for socket in tuple(self.sockets):
            socket.close()
        self.server.close()
