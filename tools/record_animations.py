"""Capture the actual native Qt preview window at 30 fps, without playing music."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget
from animation import _glyph_layout
from glyph_motion import glyph_states
from lrc import LyricTimeline, parse_lrc
from settings import ANIMATION_STYLES, Preferences
from text_effects import TextEffects


class RecordingWindow(QWidget):
    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.frames = directory / "frames"
        self.frames.mkdir(exist_ok=True)
        self.resize(1180, 560)
        self.setWindowTitle("跳动的歌词 · 四种动画预览")
        self.styles = [style for style in ANIMATION_STYLES if style != "classic"]
        self.position, self.frame = 0., 0
        self.renderer = TextEffects()
        document = parse_lrc("[00:00]给今天一点节奏\n[00:00]Hello music · 123\n[00:03.400]让工作多一点乐趣\n[00:05]")
        self.scenes = []
        for style in self.styles:
            prefs = Preferences(animation_style=style, color="#ff6a9c", font_size=32, jump=16, opacity=100)
            timeline = LyricTimeline(document, animation_style=style)
            surfaces = []
            for line in document.lines[:2]:
                glyphs, _, _ = _glyph_layout(line.text, 32, 530)
                surfaces.append(self.renderer.prepare(glyphs, 32, prefs, self.devicePixelRatioF(), prefs.jump))
            self.scenes.append((prefs, timeline, surfaces))
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.capture)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#18232f"))
        for index, (prefs, timeline, surfaces) in enumerate(self.scenes):
            painter.save()
            painter.translate((index % 2) * 590, (index // 2) * 280)
            painter.setPen(QPen(QColor("#ff6a9c")))
            painter.setFont(QFont("Microsoft YaHei UI", 13))
            painter.drawText(24, 32, ANIMATION_STYLES[prefs.animation_style])
            painter.setPen(QColor("#73869b"))
            painter.drawText(24, 262, "逐字入场 → 律动停留 → 逐字退场")
            for item in timeline.visible(self.position, 5500):
                surface = surfaces[item.index]
                states = glyph_states(surface.glyphs, prefs, item, self.position, .55, 32, 730 + item.index)
                image = self.renderer.render(surface, prefs, states=states)
                painter.save()
                painter.translate(295, 112 if item.index == 0 else 210)
                painter.drawImage(surface.origin, image)
                painter.restore()
            painter.restore()

    def capture(self):
        self.position = self.frame * 1000 / 30
        self.repaint()
        self.grab().save(str(self.frames / f"{self.frame:04d}.png"))
        self.frame += 1
        if self.frame == 165:
            self.timer.stop()
            native_visible = False
            if sys.platform == "win32":
                user = ctypes.windll.user32
                user.IsWindowVisible.argtypes = [wintypes.HWND]
                user.IsWindowVisible.restype = wintypes.BOOL
                native_visible = bool(user.IsWindowVisible(int(self.winId())))
            manifest = {"frames": self.frame, "fps": 30, "durationSeconds": 5.5, "styles": self.styles,
                        "logicalSize": [self.width(), self.height()], "devicePixelRatio": self.devicePixelRatioF(),
                        "nativeWindowVisible": native_visible, "capture": "QWidget.grab", "musicControlled": False}
            (self.directory / "recording.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            QApplication.instance().quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    app = QApplication([])
    window = RecordingWindow(args.directory)
    window.show()
    QTimer.singleShot(300, window.timer.start)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
