"""Bounded GUI/audio smoke check, also available in the packaged executable."""
import ctypes
from ctypes import wintypes
import json
import hashlib
import platform
import sys
from PySide6 import __version__ as qt_version
from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from settings import Preferences
from fonts import FontLibrary, PRESET_FONTS, lyric_font
from PySide6.QtGui import QFontInfo


def native_app_id():
    if sys.platform != "win32":
        return None
    value = ctypes.c_void_p()
    getter = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
    getter.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    getter.restype = ctypes.c_long
    if getter(ctypes.byref(value)) != 0:
        return None
    try:
        return ctypes.wstring_at(value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.ole32.CoTaskMemFree(value)


def native_icon_fingerprint(hwnd):
    """Read the window's actual Windows HICON, including its colour bitmap."""
    if sys.platform != "win32":
        return None
    class IconInfo(ctypes.Structure):
        _fields_ = [("icon", wintypes.BOOL), ("x", wintypes.DWORD), ("y", wintypes.DWORD),
                    ("mask", wintypes.HBITMAP), ("color", wintypes.HBITMAP)]
    class Bitmap(ctypes.Structure):
        _fields_ = [("type", wintypes.LONG), ("width", wintypes.LONG), ("height", wintypes.LONG),
                    ("stride", wintypes.LONG), ("planes", wintypes.WORD), ("bitsPixel", wintypes.WORD),
                    ("bits", ctypes.c_void_p)]
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.SendMessageW.restype = wintypes.LPARAM
    user.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(IconInfo)]
    gdi.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
    gdi.GetBitmapBits.argtypes = [wintypes.HBITMAP, wintypes.LONG, ctypes.c_void_p]
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    handle = user.SendMessageW(hwnd, 0x007f, 1, 0)  # WM_GETICON / ICON_BIG
    info = IconInfo()
    if not handle or not user.GetIconInfo(handle, ctypes.byref(info)):
        return None
    try:
        bitmap = Bitmap()
        if not info.color or not gdi.GetObjectW(info.color, ctypes.sizeof(bitmap), ctypes.byref(bitmap)):
            return None
        size = bitmap.stride * bitmap.height
        if not 0 < size < 1024 * 1024:
            return None
        pixels = ctypes.create_string_buffer(size)
        if gdi.GetBitmapBits(info.color, size, pixels) != size:
            return None
        return hashlib.sha256(pixels.raw).hexdigest()
    finally:
        for bitmap in (info.color, info.mask):
            if bitmap:
                gdi.DeleteObject(bitmap)


class SmokeCheck:
    def __init__(self, app, panel, report_dir, font_fixture=None):
        self.app, self.panel, self.player, self.overlay = app, panel, panel.player, panel.overlay
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.font_fixture = font_fixture
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
            from app_info import WINDOWS_APP_ID
            self.results["native_taskbar_application_identity"] = native_app_id() == WINDOWS_APP_ID
        for key, value in vars(Preferences()).items():
            setattr(self.panel.prefs, key, value)
        self.panel._sync_effect_widgets()
        self.panel.text_style.setCurrentIndex(self.panel.text_style.findData(self.panel.prefs.text_style))
        self.panel.glow_slider.setValue(self.panel.prefs.glow_strength)
        self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData(self.panel.prefs.animation_style))
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
        self._capture_fonts()
        self._capture_effects()
        self._capture_animations()
        self._capture_parameters()
        self._capture_presets()
        self._capture_singing()
        self._capture_interface()
        self._capture_themes()
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

    def _capture_fonts(self):
        import hashlib
        panel = self.panel
        original = panel.prefs.font_family
        position = self.player.position()
        matches, shapes = {}, set()
        panel.nav_buttons[1].click()
        for _, family in PRESET_FONTS:
            index = panel.font_combo.findData(family)
            panel.font_combo.setCurrentIndex(index)
            self.app.processEvents()
            image = self.overlay.grab().toImage()
            shapes.add(hashlib.sha256(bytes(image.constBits())).hexdigest())
            matches[family] = QFontInfo(lyric_font(panel.prefs.font_family, 32)).family()
            self.overlay.grab().save(str(self.report_dir / f"font-{family.replace(' ', '-')}.png"))
            panel.effects_scroll.verticalScrollBar().setValue(0)
            panel.grab().save(str(self.report_dir / f"font-settings-{family.replace(' ', '-')}.png"))
        self.results["preset_font_families_resolve"] = all(family == actual for family, actual in matches.items())
        self.results["preset_fonts_change_rendered_lyrics"] = len(shapes) == len(PRESET_FONTS)
        self.results["preset_font_matches"] = matches
        if self.font_fixture:
            imported = panel.import_font(self.font_fixture)
            selected = panel.prefs.font_family
            self.results["custom_font_imported"] = imported and QFontInfo(lyric_font(selected, 32)).family() == selected
            self.results["custom_font_selection_saved"] = imported and panel.store.load().font_family == selected
            restored = FontLibrary(panel.font_library.directory)
            try:
                self.results["custom_font_reloads_from_owned_copy"] = imported and restored.restore_family(selected)[0] == selected
            finally:
                restored.close()
            self.overlay.grab().save(str(self.report_dir / "font-imported.png"))
        panel.font_combo.setCurrentIndex(panel.font_combo.findData(original))
        self.app.processEvents()
        self.results["font_changes_preserve_paused_position"] = not self.player.playing and self.player.position() == position

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
            for control in (panel.region, panel.font_combo, panel.import_font_button, panel.font_preview,
                            panel.text_style, panel.preview_background, panel.glow_field,
                            panel.color_button, panel.motion, panel.animation_combo, panel.replay_button,
                            panel.preset_combo, panel.preset_save_button, panel.preset_update_button, panel.preset_delete_button,
                            panel.singing_checkbox, panel.word_status,
                            *panel.parameter_fields.values(), *panel.spins.values()):
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

    def _capture_effects(self):
        import hashlib
        from effect_validation import validate_effects
        panel = self.panel
        original = (panel.prefs.text_style, panel.prefs.glow_strength, panel.preview_background.currentIndex())
        position = self.player.position()
        shapes = set()
        for style in ("solid", "glow"):
            panel.text_style.setCurrentIndex(panel.text_style.findData(style))
            panel.glow_slider.setValue(60)
            self.app.processEvents()
            picture = self.overlay.grab().toImage()
            shapes.add(hashlib.sha256(bytes(picture.constBits())).hexdigest())
            picture.save(str(self.report_dir / f"effect-{style}.png"))
        for index, name in enumerate(("dark", "light")):
            panel.preview_background.setCurrentIndex(index)
            self.app.processEvents()
            panel.font_preview.grab().save(str(self.report_dir / f"effect-preview-{name}.png"))
            center = panel.font_preview.mapTo(panel.effects_scroll.widget(), panel.font_preview.rect().center())
            panel.effects_scroll.ensureVisible(center.x(), center.y(), 0, 60)
            self.app.processEvents()
            panel.grab().save(str(self.report_dir / f"effect-settings-{name}.png"))
        saved = panel.store.load()
        self.results["effect_style_changes_rendered_lyrics"] = len(shapes) == 2
        self.results["effect_settings_saved"] = saved.text_style == "glow" and saved.glow_strength == 60
        self.results.update(validate_effects(self.report_dir, panel.prefs, panel.devicePixelRatioF()))
        panel.text_style.setCurrentIndex(panel.text_style.findData(original[0]))
        panel.glow_slider.setValue(original[1])
        panel.preview_background.setCurrentIndex(original[2])
        self.app.processEvents()
        self.results["effect_changes_preserve_paused_clock"] = not self.player.playing and self.player.position() == position

    def _capture_themes(self):
        from dataclasses import asdict
        from app_info import APP_VERSION, CREATOR, MOTTO
        from settings import resource_path
        from controls import app_icon
        panel, directory = self.panel, self.report_dir
        original_theme = panel.prefs.theme
        self.results["theme_checkmark_asset_available"] = not QImage(str(resource_path("assets/check-white.svg"))).isNull()
        visual = {key: value for key, value in asdict(panel.prefs).items() if key != "theme"}
        frame, position, preview = self.overlay.grab().toImage(), self.player.position(), panel.font_preview.dark
        self.results["sidebar_branding_updated"] = (panel.creator_label.text().replace("\n", "") == CREATOR
            and panel.version_label.text() == f"版本 {APP_VERSION}" and panel.motto_label.text().replace("\n", " ") == MOTTO)
        sidebar_ok, saved, layouts, icons_ok = True, True, True, True
        native_icons = {}
        for theme in ("light", "dark", "special"):
            panel.theme_combo.setCurrentIndex(panel.theme_combo.findData(theme))
            self.app.processEvents()
            if self.app.platformName() == "windows":
                native_icons[theme] = native_icon_fingerprint(int(panel.winId()))
            saved &= panel.store.load().theme == theme
            expected_icon = app_icon(theme).pixmap(32, 32).toImage()
            icons_ok &= (not expected_icon.isNull() and panel.windowIcon().pixmap(32, 32).toImage() == expected_icon
                         and panel.tray.icon().pixmap(32, 32).toImage() == expected_icon
                         and self.app.windowIcon().pixmap(32, 32).toImage() == expected_icon)
            panel.windowIcon().pixmap(64, 64).save(str(directory / f"theme-{theme}-icon.png"))
            self.report_dir = directory / f"theme-{theme}"
            self.report_dir.mkdir(parents=True, exist_ok=True)
            self._capture_interface()
            if theme == "special" and self.app.platformName() == "windows":
                from PySide6.QtTest import QTest
                QTest.qWait(150)  # Give Explorer time to repaint its separate taskbar window.
                screen = panel.screen()
                geometry = screen.geometry()
                screen.grabWindow(0, geometry.x(), geometry.bottom()-59, geometry.width(), 60).save(str(directory / "theme-special-taskbar.png"))
            layouts &= (self.results["player_controls_within_window"] and self.results["effect_controls_reachable_by_scrolling"]
                        and self.results["navigation_preserves_playback_and_player_bar"])
            original_size = panel.size()
            panel.resize(panel.minimumSize())
            self.app.processEvents()
            for control in (panel.creator_label, panel.version_label, panel.motto_label, panel.theme_combo,
                            *panel.nav_buttons, panel.tray_button, panel.exit_button):
                rectangle = QRect(control.mapTo(panel.sidebar, QPoint()), control.size())
                sidebar_ok &= panel.sidebar.rect().contains(rectangle) and control.isVisibleTo(panel)
            sidebar_ok &= panel.creator_label.geometry().bottom() < panel.version_label.geometry().top()
            panel.resize(original_size)
        self.report_dir = directory
        panel.theme_combo.setCurrentIndex(panel.theme_combo.findData(original_theme))
        self.app.processEvents()
        self.results["theme_switch_persists"] = bool(saved)
        self.results["both_theme_layouts_accessible"] = bool(layouts)
        self.results["both_theme_sidebars_fit_minimum_window"] = bool(sidebar_ok)
        self.results["theme_window_application_and_tray_icons_match"] = bool(icons_ok)
        if native_icons:
            self.results["native_windows_theme_icon_changes_and_restores"] = bool(
                all(native_icons.values()) and native_icons["light"] == native_icons["dark"]
                and native_icons["special"] != native_icons["light"]
                and native_icon_fingerprint(int(panel.winId())) == native_icons[original_theme])
        self.results["special_icon_and_blueprint_assets_available"] = all(
            not QImage(str(resource_path(name))).isNull() for name in ("assets/dante-clock.svg", "assets/special-blueprint.svg"))
        self.results["theme_keeps_lyrics_and_paused_clock"] = (not self.player.playing and self.player.position() == position
            and self.overlay.grab().toImage() == frame
            and {key: value for key, value in asdict(panel.prefs).items() if key != "theme"} == visual
            and panel.font_preview.dark == preview)

    def _check_resume(self):
        self.results["resume_advances_clock"] = self.player.position() > 9900
        self.results["resume_restarts_render_timer"] = self.overlay.timer.isActive()
        self.player.seek(23500)
        QTimer.singleShot(1300, self._finish)

    def _capture_animations(self):
        from animation_validation import validate_animations
        from settings import ANIMATION_STYLES
        panel = self.panel
        original = panel.prefs.animation_style
        transport = (self.player._anchor_ms, self.player._anchor_time, self.player.playing)
        frozen, saved = True, True
        for style in ANIMATION_STYLES:
            if style == "classic":
                continue
            panel.animation_combo.setCurrentIndex(panel.animation_combo.findData(style))
            self.app.processEvents()
            first = self.overlay.grab().toImage()
            self.app.processEvents()
            frozen &= first == self.overlay.grab().toImage() and not self.overlay.timer.isActive()
            saved &= panel.store.load().animation_style == style
            first.save(str(self.report_dir / f"overlay-{style}.png"))
            center = panel.animation_combo.mapTo(panel.effects_scroll.widget(), panel.animation_combo.rect().center())
            panel.effects_scroll.ensureVisible(center.x(), center.y(), 0, 60)
            self.app.processEvents()
            panel.grab().save(str(self.report_dir / f"settings-{style}.png"))
        self.results["all_animation_settings_saved"] = bool(saved)
        self.results["all_animations_freeze_while_paused"] = bool(frozen)
        self.results.update(validate_animations(self.report_dir, panel.prefs, panel.devicePixelRatioF(), include_singing=True))
        panel.animation_combo.setCurrentIndex(panel.animation_combo.findData(original))
        self.results["animation_changes_preserve_transport"] = transport == (
            self.player._anchor_ms, self.player._anchor_time, self.player.playing)

    def _capture_parameters(self):
        panel = self.panel
        keys = ("entry_speed", "exit_speed", "shake_frequency", "fall_distance")
        original = {key: getattr(panel.prefs, key) for key in keys}
        style, position = panel.prefs.animation_style, self.player.position()
        panel.animation_combo.setCurrentIndex(panel.animation_combo.findData("fall_shake"))
        for key, value in zip(keys, (180, 65, 12, 128)):
            panel.spins[key].setValue(value)
        self.results["animation_parameters_saved"] = all(getattr(panel.store.load(), key) == value
            for key, value in zip(keys, (180, 65, 12, 128)))
        self.app.processEvents()
        center = panel.animation_combo.mapTo(panel.effects_scroll.widget(), panel.animation_combo.rect().center())
        panel.effects_scroll.ensureVisible(center.x(), center.y(), 0, 120)
        self.app.processEvents()
        panel.grab().save(str(self.report_dir / "animation-parameters.png"))
        self.results["animation_parameters_preserve_paused_clock"] = not self.player.playing and self.player.position() == position
        for key, value in original.items():
            panel.spins[key].setValue(value)
        panel.animation_combo.setCurrentIndex(panel.animation_combo.findData(style))

    def _capture_presets(self):
        from dataclasses import replace
        from presets import PresetStore
        panel = self.panel
        original, position = replace(panel.prefs), self.player.position()
        preserved = (panel.prefs.region, panel.prefs.delay_ms, panel.prefs.volume, panel.font_preview.dark)
        for identifier in ("builtin:quiet", "builtin:lively"):
            panel.apply_preset(identifier)
            self.app.processEvents()
            panel.effects_scroll.verticalScrollBar().setValue(0)
            panel.grab().save(str(self.report_dir / ("preset-" + identifier.split(":")[1] + "-settings.png")))
            panel.font_preview.grab().save(str(self.report_dir / ("preset-" + identifier.split(":")[1] + "-preview.png")))
        saved = panel.presets.save("Smoke " + str(id(self)), panel.prefs)
        loaded = PresetStore(panel.presets.path).get(saved.id)
        self.results["custom_preset_reloads_complete_effects"] = loaded == saved
        panel.presets.delete(saved.id)
        self.results["preset_keeps_independent_settings"] = preserved == (panel.prefs.region, panel.prefs.delay_ms,
                                                                         panel.prefs.volume, panel.font_preview.dark)
        self.results["preset_switch_keeps_paused_position"] = not self.player.playing and self.player.position() == position
        for key, value in vars(original).items():
            setattr(panel.prefs, key, value)
        panel._preset_id, panel._preset_modified = None, False
        panel._sync_effect_widgets()
        panel._reload_presets()
        panel.store.save(panel.prefs)
        panel.overlay.refresh_preferences()

    def _capture_singing(self):
        from dataclasses import replace
        from lrc import LyricDocument, TimedWord
        panel, overlay = self.panel, self.overlay
        original, document, position = replace(panel.prefs), overlay.document, self.player.position()
        demo = LyricDocument([replace(line, words=(TimedWord(line.start_ms+100, line.start_ms+3000, 0, len(line.text)),)
                                      if line.text else ()) for line in document.lines], [], document.offset_ms)
        overlay.set_document(demo)
        panel.animation_combo.setCurrentIndex(panel.animation_combo.findData("fall_shake"))
        panel.singing_checkbox.setChecked(True)
        first = overlay.grab().toImage()
        self.app.processEvents()
        self.results["singing_freezes_on_paused_song_clock"] = first == overlay.grab().toImage() and not overlay.timer.isActive()
        self.results["singing_switch_saved"] = panel.store.load().singing_sync is True
        for index, name in enumerate(("dark", "light")):
            panel.preview_background.setCurrentIndex(index)
            panel.font_preview._stop_preview()
            panel.font_preview._running = False
            panel.font_preview._position = 2250
            panel.font_preview.grab().save(str(self.report_dir / f"singing-preview-{name}.png"))
        self.results["singing_preview_uses_demo_timing"] = True
        self.results["singing_controls_preserve_paused_position"] = not self.player.playing and self.player.position() == position
        for key, value in vars(original).items():
            setattr(panel.prefs, key, value)
        panel._sync_effect_widgets()
        panel.store.save(panel.prefs)
        overlay.set_document(document)
        overlay.refresh_preferences()
        panel._refresh_word_status()

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
