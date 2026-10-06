from collections import deque
from pathlib import Path
import time
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioBufferOutput
from audio_energy import EnergyAnalyzer


class MusicPlayer(QObject):
    changed = Signal()
    discontinuity = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.buffers = QAudioBufferOutput(self)
        self.analyzer = EnergyAnalyzer(self)
        self.media.setAudioOutput(self.output)
        self.media.setAudioBufferOutput(self.buffers)
        self.buffers.audioBufferReceived.connect(self.analyzer.process)
        self.analyzer.received.connect(self._receive_energy)
        self.analyzer.failed.connect(self._analysis_failed)
        self.media.positionChanged.connect(self._position_changed)
        self.media.playbackStateChanged.connect(self._state_changed)
        self.media.durationChanged.connect(lambda _: self.changed.emit())
        self.media.mediaStatusChanged.connect(self._status_changed)
        self.media.errorOccurred.connect(lambda _code, text: self.error.emit(f"播放失败：{text}"))
        self.path: Path | None = None
        self._anchor_ms = 0.0
        self._anchor_time = time.monotonic()
        self._energy_samples = deque(maxlen=64)
        self._energy = 0.0
        self._last_energy_clock = 0.0
        self.has_audio_data = False
        self.analysis_error = ""
        self.ended = False

    @property
    def playing(self) -> bool:
        return self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def duration(self) -> int:
        return self.media.duration()

    def position(self) -> float:
        pos = self._anchor_ms
        if self.playing:
            # Bound extrapolation when a backend stalls or is still buffering.
            pos += min(300.0, (time.monotonic() - self._anchor_time) * 1000)
        return max(0.0, min(float(self.duration), pos)) if self.duration else max(0.0, pos)

    def load(self, path: str | Path):
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError("音乐文件不存在，请重新选择。")
        self.media.stop()
        self.path = path
        self.ended = False
        self.has_audio_data = False
        self.analysis_error = ""
        self._reset_energy()
        self._position_changed(0)
        self.media.setSource(QUrl.fromLocalFile(str(path)))
        self.discontinuity.emit()
        self.changed.emit()

    def toggle(self):
        if not self.path:
            return
        if self.playing:
            self.media.pause()
        else:
            if self.ended:
                self.seek(0)
            self.media.play()

    def seek(self, position_ms: int):
        if not self.media.isSeekable():
            return
        position_ms = max(0, min(position_ms, self.duration))
        self.ended = False
        self._reset_energy()
        self._position_changed(position_ms)
        self.media.setPosition(position_ms)
        self.discontinuity.emit()

    def set_volume(self, percent: int):
        self.output.setVolume(percent / 100.0)

    def _position_changed(self, position_ms: int):
        self._anchor_ms = float(position_ms)
        self._anchor_time = time.monotonic()

    def _state_changed(self, _state):
        self._position_changed(self.media.position())
        self.changed.emit()

    def _status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.ended = True
            self._reset_energy()
            self.discontinuity.emit()
        self.changed.emit()

    def _analysis_failed(self, message: str):
        self.analysis_error = message

    def _receive_energy(self, energy: float, timestamp_ms: float):
        # Decoder callbacks from the pre-seek stream must not drive the new position.
        if timestamp_ms >= 0 and abs(timestamp_ms - self.position()) > 1800:
            return
        self.has_audio_data = True
        self.analysis_error = ""
        self._energy_samples.append((timestamp_ms, energy))

    def _reset_energy(self):
        self._energy_samples.clear()
        self._energy = 0.0
        self._last_energy_clock = self._anchor_ms

    def energy_at(self, position_ms: float) -> float:
        if not self.playing:
            return self._energy
        target = 0.0
        for timestamp, value in self._energy_samples:
            if timestamp <= position_ms + 80 and timestamp >= position_ms - 350:
                target = value
        dt = max(0.0, min(0.15, (position_ms - self._last_energy_clock) / 1000))
        self._last_energy_clock = position_ms
        tau = 0.045 if target > self._energy else 0.18
        blend = 1 - pow(2.718281828, -dt / tau)
        self._energy += (target - self._energy) * blend
        return self._energy
