import random
import sys
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget
from animation import build_layout, display_regions
from lrc import LyricTimeline, LyricDocument
from settings import Preferences
from text_effects import TEXT_EFFECTS
from glyph_motion import glyph_states


class LyricsOverlay(QWidget):
    def __init__(self, player, prefs: Preferences):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle("跳动的歌词 · 悬浮层")
        self.player = player
        self.prefs = prefs
        self.document = None
        self.timeline = None
        self.layouts = {}
        self.seed = random.randrange(1_000_000)
        self._screen = None
        self._bind_screen(QApplication.primaryScreen())
        QApplication.instance().primaryScreenChanged.connect(self._bind_screen)
        player.discontinuity.connect(self.clear_layouts)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update)
        player.changed.connect(self._sync_timer)

    def _bind_screen(self, screen):
        if self._screen:
            try:
                self._screen.availableGeometryChanged.disconnect(self._screen_changed)
            except (RuntimeError, TypeError):
                pass
        self._screen = screen
        if screen:
            screen.availableGeometryChanged.connect(self._screen_changed)
            self._screen_changed()

    def _screen_changed(self, *_):
        self.setGeometry(self._screen.availableGeometry())
        self.clear_layouts()

    def set_document(self, document: LyricDocument | None):
        same_text = bool(document and self.document and [(line.start_ms, line.text) for line in document.lines]
                         == [(line.start_ms, line.text) for line in self.document.lines])
        self.document = document
        self.timeline = self._timeline(document) if document else None
        if not same_text:
            self.seed = random.randrange(1_000_000)
            self.clear_layouts()
        self._sync_timer()

    def refresh_preferences(self):
        if self.document:
            self.timeline = self._timeline(self.document)
        self.clear_layouts()

    def _timeline(self, document):
        return LyricTimeline(document, self.prefs.delay_ms, self.prefs.animation_style,
                             self.prefs.entry_speed, self.prefs.exit_speed)

    def clear_layouts(self):
        self.layouts.clear()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._protect_native_focus()
        self._sync_timer()

    def _sync_timer(self):
        if self.isVisible() and self.timeline and self.player.playing and not self.player.ended:
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def _protect_native_focus(self):
        # Qt handles focus messages, but 6.8 does not add WS_EX_NOACTIVATE itself.
        # Only alter our own HWND, including after it is shown again from the tray.
        if sys.platform != "win32" or QApplication.instance().platformName() != "windows":
            return
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, -20)
        user32.SetWindowLongW(hwnd, -20, style | 0x08000000)
        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x37)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.DevicePixelRatioChange and hasattr(self, "layouts"):
            TEXT_EFFECTS.clear()
            self.clear_layouts()
        return super().event(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        # Explicitly erase the previous frame in the alpha surface.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if not self.timeline or self.player.ended:
            return
        position = self.player.position()
        active = self.timeline.visible(position, self.player.duration)
        wanted = {item.index for item in active}
        self.layouts = {key: value for key, value in self.layouts.items() if key in wanted}
        regions = display_regions(self.width(), self.height(), self.prefs.region)
        for item in active:
            if item.index in self.layouts:
                continue
            occupied = [layout.bounds for layout in self.layouts.values()]
            layout = build_layout(item.text, self.seed + item.index * 7919, regions, occupied, self.prefs)
            if layout:
                self.layouts[item.index] = layout
        energy = self.player.energy_at(position)
        if self.prefs.motion == "wave":
            energy = 0.32
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        seconds = position / 1000.0
        for item in active:
            layout = self.layouts.get(item.index)
            if not layout:
                continue
            # A constrained screen may only have room for the newer sentence.
            if any(layout.bounds.intersects(self.layouts[new.index].bounds)
                   for new in active if new.index > item.index and new.index in self.layouts):
                continue
            age = position - item.start_ms
            remaining = item.end_ms - position
            drift = (8 * (1 - min(1, remaining / (600 * 100 / self.prefs.exit_speed)))
                     - 5 * (1 - min(1, age / (300 * 100 / self.prefs.entry_speed))))
            if self.prefs.animation_style != "classic":
                drift = 0
            painter.save()
            painter.setOpacity(item.opacity * self.prefs.opacity / 100)
            painter.translate(layout.center)
            painter.rotate(layout.angle)
            painter.translate(0, drift)
            if layout.surface is None:
                layout.surface = TEXT_EFFECTS.prepare(layout.glyphs, layout.font_size, self.prefs,
                                                      self.devicePixelRatioF(), self.prefs.jump, layout.angle)
            states = (glyph_states(layout.glyphs, self.prefs, item, position, energy, layout.font_size,
                                   self.seed + item.index * 7919, layout.angle)
                      if self.prefs.animation_style != "classic" or self.prefs.singing_sync else None)
            image = TEXT_EFFECTS.render(layout.surface, self.prefs, seconds, energy, moving=True, states=states)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(layout.surface.origin, image)
            painter.restore()
