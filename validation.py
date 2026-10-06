"""Bounded GUI/audio smoke check, also available in the packaged executable."""
import ctypes
from ctypes import wintypes
import json
import platform
import sys
from PySide6 import __version__ as qt_version
from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from settings import Preferences


class SmokeCheck:
    def __init__(self, app, panel, report_dir):
        self.app, self.panel, self.player, self.overlay = app, panel, panel.player, panel.overlay
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.results = {}
        self.errors = []
        self.maximum_energy = 0.0
        self.buffer_count = 0
        self.player.error.connect(self.errors.append)
        self.player.analyzer.received.connect(self._energy)

    def _energy(self, energy, _timestamp):
        self.buffer_count += 1
        self.maximum_energy = max(self.maximum_energy, energy)

    def start(self):
        self.results["qt_control_panel_visible"] = self.panel.isVisible()
        self.panel.grab().save(str(self.report_dir / "control-panel-empty.png"))
        if sys.platform == "win32" and self.app.platformName() == "windows":
            user32 = ctypes.windll.user32
            user32.IsWindowVisible.argtypes = [wintypes.HWND]
            user32.IsWindowVisible.restype = wintypes.BOOL
            self.results["native_control_panel_visible"] = bool(user32.IsWindowVisible(int(self.panel.winId())))
        for key, value in vars(Preferences()).items():
            setattr(self.panel.prefs, key, value)
        self.panel.prefs.volume = 0
        self.panel.volume_slider.setValue(0)
        self.player.set_volume(0)
        self.panel.play_demo()
        QTimer.singleShot(2500, self._pause)

    def _pause(self):
        self.results["duration_ms"] = self.player.duration
        self.results["decoded_audio_buffers"] = self.buffer_count
        self.results["maximum_normalized_energy"] = round(self.maximum_energy, 4)
        self.results["real_audio_analysis"] = self.buffer_count > 5 and self.maximum_energy > .05
        self.player.media.pause()
        self.paused_position = self.player.position()
        self.paused_frame = self.overlay.grab().toImage()
        QTimer.singleShot(350, self._seek)

    def _seek(self):
        self.results["pause_freezes_clock"] = abs(self.player.position() - self.paused_position) < 1
        self.results["pause_freezes_frame"] = self.overlay.grab().toImage() == self.paused_frame
        self.player.seek(9700)
        QTimer.singleShot(400, self._capture)

    def _capture(self):
        visible = self.overlay.timeline.visible(self.player.position(), self.player.duration)
        self.results["seek_rebuilds_lyrics"] = [line.text for line in visible] == ["陪你写下一行代码"]
        self.panel.grab().save(str(self.report_dir / "control-panel.png"))
        self._capture_interface()
        image = self.overlay.grab().toImage()
        image.save(str(self.report_dir / "overlay-transparent.png"))
        preview = QImage(image.size(), QImage.Format.Format_ARGB32)
        preview.fill(QColor("#18272c"))
        painter = QPainter(preview)
        painter.drawImage(0, 0, image)
        painter.end()
        preview.save(str(self.report_dir / "overlay-preview.png"))
        self.results["layout_within_display_regions"] = bool(self.overlay.layouts) and all(
            self.overlay.rect().contains(layout.bounds.toAlignedRect()) for layout in self.overlay.layouts.values())
        flags = self.overlay.windowFlags()
        self.results["qt_input_transparent"] = bool(flags & Qt.WindowType.WindowTransparentForInput)
        self.results["qt_no_focus"] = bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus)
        if sys.platform == "win32" and self.app.platformName() == "windows":
            user32 = ctypes.windll.user32
            user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongW.restype = ctypes.c_long
            style = user32.GetWindowLongW(int(self.overlay.winId()), -20) & 0xffffffff
            self.results["native_window_style"] = hex(style)
            self.results["windows_click_through"] = bool(style & 0x20) and bool(style & 0x80000)
            self.results["windows_no_activate"] = bool(style & 0x08000000)
            self.results["windows_topmost"] = bool(style & 0x8)
        self.overlay.hide()
        self.results["hide_stops_render_timer"] = not self.overlay.timer.isActive()
        self.overlay.show()
        self.results["show_while_paused_keeps_timer_stopped"] = not self.overlay.timer.isActive()
        self.player.media.play()
        QTimer.singleShot(500, self._check_resume)

    def _capture_interface(self):
        """Check reachable controls on both pages at normal and minimum sizes."""
        panel = self.panel
        original_size, original_page = panel.size(), panel.pages.currentIndex()
        snapshots = (("default", original_size), ("minimum", panel.minimumSize()))
        footer_ok = True
        effects_ok = True
        unreachable = []
        navigation_ok = True
        for name, size in snapshots:
            panel.resize(size)
            self.app.processEvents()
            panel.nav_buttons[0].click()
            self.app.processEvents()
            panel.music_scroll.verticalScrollBar().setValue(0)
            panel.grab().save(str(self.report_dir / f"music-{name}.png"))
            bar = panel.player_bar.geometry()
            for control in (panel.play_button, panel.visibility_button, panel.volume_slider):
                rectangle = QRect(control.mapTo(panel, QPoint()), control.size())
                footer_ok &= panel.rect().contains(rectangle) and control.isVisibleTo(panel)
            paused_position = self.player.position()
            panel.nav_buttons[1].click()
            self.app.processEvents()
            navigation_ok &= (not self.player.playing and self.player.position() == paused_position
                              and panel.player_bar.geometry() == bar)
            panel.effects_scroll.verticalScrollBar().setValue(0)
            panel.grab().save(str(self.report_dir / f"effects-{name}-top.png"))
            for control in (panel.region, panel.color_button, panel.motion, *panel.spins.values()):
                # Spin boxes expose the edit cursor to ensureWidgetVisible;
                # scroll the entire field into view, including its arrow buttons.
                center = control.mapTo(panel.effects_scroll.widget(), control.rect().center())
                panel.effects_scroll.ensureVisible(center.x(), center.y(), 0, control.height() // 2 + 16)
                self.app.processEvents()
                rectangle = QRect(control.mapTo(panel.effects_scroll.viewport(), QPoint()), control.size())
                reachable = panel.effects_scroll.viewport().rect().contains(rectangle)
                effects_ok &= reachable
                if not reachable:
                    unreachable.append({"size": name, "control": type(control).__name__,
                                        "bounds": [rectangle.x(), rectangle.y(), rectangle.width(), rectangle.height()],
                                        "viewport": [panel.effects_scroll.viewport().width(), panel.effects_scroll.viewport().height()]})
            panel.effects_scroll.verticalScrollBar().setValue(panel.effects_scroll.verticalScrollBar().maximum())
            panel.grab().save(str(self.report_dir / f"effects-{name}-bottom.png"))
        panel.resize(original_size)
        panel.nav_buttons[original_page].click()
        self.app.processEvents()
        self.results["player_controls_within_window"] = bool(footer_ok)
        self.results["effect_controls_reachable_by_scrolling"] = bool(effects_ok)
        self.results["unreachable_effect_controls"] = unreachable
        self.results["navigation_preserves_playback_and_player_bar"] = bool(navigation_ok)
        self.results["control_panel_size"] = [original_size.width(), original_size.height()]
        self.results["device_pixel_ratio"] = panel.devicePixelRatioF()

    def _check_resume(self):
        self.results["resume_advances_clock"] = self.player.position() > 9900
        self.results["resume_restarts_render_timer"] = self.overlay.timer.isActive()
        self.player.seek(23500)
        QTimer.singleShot(1300, self._finish)

    def _finish(self):
        self.results["end_of_song_clears_overlay"] = self.player.ended
        self.results["end_of_song_stops_render_timer"] = not self.overlay.timer.isActive()
        self.results["playback_errors"] = self.errors
        required = [value for key, value in self.results.items() if isinstance(value, bool)]
        passed = all(required) and not self.errors and self.player.duration == 24000
        report = {"passed": passed, "python": platform.python_version(), "pyside6": qt_version,
                  "qt_platform": self.app.platformName(), "checks": self.results,
                  "limitations": ["未完成 30 分钟稳定性测试", "声音检查以静音解码验证为准；未人工听音",
                                  "窗口输入行为通过标志检查，仍需在实际编辑器中体验确认"]}
        (self.report_dir / "smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if sys.stdout:
            print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
        self.app.exit(0 if passed else 1)
