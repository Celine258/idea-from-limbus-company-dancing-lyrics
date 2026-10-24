import random
import sys
import time
from bisect import bisect_right
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget
from animation import build_layout_steps, display_regions
from lrc import LyricTimeline, LyricDocument, display_document
from settings import Preferences, display_mode
from text_effects import TEXT_EFFECTS
from glyph_motion import glyph_states
from app_info import APP_NAME
from screens import select_screen


class LyricsOverlay(QWidget):
    def __init__(self, player, prefs: Preferences):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if sys.platform == "darwin":
            # Qt's native NSPanel stays visible when another application is active.
            # Keep Tool on Windows: removing it exposes the overlay in the taskbar.
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle(f"{APP_NAME} · 悬浮层")
        self.player = player
        self.prefs = prefs
        self.document = None
        self.display_document = None
        self.timeline = None
        self.layouts = {}
        self._warm_jobs = {}
        self._warm_timer = QTimer(self)
        self._warm_timer.setInterval(10)
        self._warm_timer.timeout.connect(self._warm_step)
        self.seed = random.randrange(1_000_000)
        self._screen = None
        self.refresh_screen()
        app = QApplication.instance()
        app.primaryScreenChanged.connect(self.refresh_screen)
        app.screenAdded.connect(self.refresh_screen)
        app.screenRemoved.connect(self.refresh_screen)
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
            if self.windowHandle():
                self.windowHandle().setScreen(screen)
            screen.availableGeometryChanged.connect(self._screen_changed)
            self._screen_changed()

    def refresh_screen(self, *_):
        screen = select_screen(QApplication.screens(), QApplication.primaryScreen(), self.prefs.display_screen)
        if screen is not self._screen:
            self._bind_screen(screen)

    def _screen_changed(self, *_):
        self.setGeometry(self._screen.availableGeometry())
        self.clear_layouts()

    def set_document(self, document: LyricDocument | None):
        displayed = display_document(document, mode=display_mode(self.prefs), hide_instrumental=self.prefs.hide_instrumental)
        same_text = bool(displayed and self.display_document and [(line.start_ms, line.text) for line in displayed.lines]
                         == [(line.start_ms, line.text) for line in self.display_document.lines])
        self.document = document
        self.display_document = displayed
        self.timeline = self._timeline(displayed) if displayed else None
        if not same_text:
            self.seed = random.randrange(1_000_000)
            self.clear_layouts()
        self._sync_timer()

    def refresh_preferences(self):
        self.refresh_screen()
        self.display_document = display_document(self.document, mode=display_mode(self.prefs), hide_instrumental=self.prefs.hide_instrumental)
        self.timeline = self._timeline(self.display_document) if self.display_document else None
        self.clear_layouts()
        self._sync_timer()

    def _timeline(self, document):
        delay = self.prefs.delay_ms - getattr(self.player, "lyric_offset_ms", 0)
        return LyricTimeline(document, delay, self.prefs.animation_style,
                             self.prefs.entry_speed, self.prefs.exit_speed, self.prefs.scramble_exit,
                             self.prefs.max_display_seconds * 1000)

    def clear_layouts(self):
        self._warm_timer.stop()
        self._warm_jobs.clear()
        self.layouts.clear()
        self.update()

    def _prepare_lines(self, active, position):
        """Retain at most two visible sentences plus one upcoming sentence."""
        candidates = [(item.index, self.timeline.lines[item.index]) for item in active]
        for index in range(bisect_right(self.timeline.starts, position), len(self.timeline.lines)):
            line = self.timeline.lines[index]
            if line.text.strip() and (not self.player.duration or line.start_ms < self.player.duration):
                candidates.append((index, line))
                break
        wanted = {index for index, _ in candidates}
        self.layouts = {key: value for key, value in self.layouts.items() if key in wanted}
        self._warm_jobs = {key: value for key, value in self._warm_jobs.items() if key in wanted}
        for index, line in candidates:
            if index in self.layouts or index in self._warm_jobs:
                continue
            self._warm_jobs[index] = self._prepare_line(index, line)
        if self._warm_jobs and self.isVisible() and not self._warm_timer.isActive():
            self._warm_timer.start()

    def _prepare_line(self, index, line):
        regions = display_regions(self.width(), self.height(), self.prefs.region)
        occupied = [layout.bounds for layout in self.layouts.values()]
        for layout in build_layout_steps(line.text, self.seed + index * 7919, regions, occupied,
                                         self.prefs, line.secondary_start):
            if layout is None:
                yield None
                continue
            self.layouts[index] = layout
            yield None
            yield from TEXT_EFFECTS.prepare_steps(
                layout.glyphs, layout.font_size, self.prefs, self.devicePixelRatioF(), self.prefs.jump, layout.angle)

    def _warm_step(self):
        if not self.isVisible() or not self.timeline or self.player.ended:
            self._warm_timer.stop()
            return
        deadline = time.perf_counter() + .004
        changed = False
        while self._warm_jobs and time.perf_counter() < deadline:
            # Entrance materials first, optional scramble-exit symbols second.
            index = min(self._warm_jobs, key=lambda key: (key in self.layouts and self.layouts[key].surface is not None, key))
            try:
                ready = next(self._warm_jobs[index])
                if ready is not None:
                    self.layouts[index].surface = ready
                    changed = True
            except StopIteration:
                del self._warm_jobs[index]
        if not self._warm_jobs:
            self._warm_timer.stop()
        if changed:
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
        self._warm_timer.stop()
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
        self._prepare_lines(active, position)
        energy = self.player.energy_at(position)
        if self.prefs.motion == "wave":
            energy = 0.32
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        seconds = position / 1000.0
        for item in active:
            layout = self.layouts.get(item.index)
            if not layout or layout.surface is None:
                continue
            # A constrained screen may only have room for the newer sentence.
            if any(layout.bounds.intersects(self.layouts[new.index].bounds)
                   for new in active if new.index > item.index and new.index in self.layouts):
                continue
            age = position - item.start_ms
            remaining = item.end_ms - position
            drift = (8 * (1 - min(1, remaining / (600 * 100 / self.prefs.exit_speed)))
                     - 5 * (1 - min(1, age / (300 * 100 / self.prefs.entry_speed))))
            if self.prefs.animation_style != "classic" or self.prefs.scramble_exit:
                drift = 0
            drift *= self.prefs.motion_strength / 100
            painter.save()
            painter.setOpacity(item.opacity * self.prefs.opacity / 100)
            painter.translate(layout.center)
            painter.rotate(layout.angle)
            painter.translate(0, drift)
            states = (glyph_states(layout.glyphs, self.prefs, item, position, energy, layout.font_size,
                                   self.seed + item.index * 7919, layout.angle)
                      if self.prefs.animation_style != "classic" or self.prefs.singing_sync or item.secondary_start >= 0 or self.prefs.scramble_exit else None)
            image = TEXT_EFFECTS.render(layout.surface, self.prefs, seconds, energy, moving=True, states=states)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(layout.surface.origin, image)
            painter.restore()
