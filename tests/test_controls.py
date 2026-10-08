import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from controls import ControlPanel
from settings import Preferences, SettingsStore

APP = QApplication.instance() or QApplication([])


class FakePlayer(QObject):
    changed = Signal()
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.path = None
        self.playing = False
        self.duration = 0
        self.clock = 0
        self.seeks = []
        self.has_audio_data = False
        self.analysis_error = ""
        self.media = self

    def load(self, path):
        path = Path(path)
        if not path.is_file():
            raise ValueError("音乐文件不存在，请重新选择。")
        self.path = path
        self.playing = False
        self.clock = 0
        self.duration = 24000
        self.changed.emit()

    def position(self):
        return self.clock

    def isSeekable(self):
        return self.path is not None

    def toggle(self):
        if self.path:
            self.playing = not self.playing
            self.changed.emit()

    def play(self):
        self.playing = True
        self.changed.emit()

    def set_volume(self, value):
        self.volume = value

    def seek(self, value):
        self.seeks.append(value)
        self.clock = value


class FakeOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.document = None
        self.refreshes = 0

    def set_document(self, document):
        self.document = document

    def refresh_preferences(self):
        self.refreshes += 1


class ControlPanelTests(unittest.TestCase):
    def test_city_echoes_name_is_visible_and_tray_identity_is_preserved(self):
        from app_info import APP_NAME, WINDOWS_APP_ID
        from PySide6.QtWidgets import QLabel
        self.assertEqual(APP_NAME, "都市回响")
        self.assertEqual(self.panel.windowTitle(), APP_NAME)
        self.assertEqual(self.panel.tray.toolTip(), APP_NAME)
        self.assertIn(APP_NAME, [item.text() for item in self.panel.findChildren(QLabel)])
        self.assertEqual(WINDOWS_APP_ID, "FloatingLyrics.Desktop")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.player = FakePlayer()
        self.overlay = FakeOverlay()
        self.prefs = Preferences()
        self.store = SettingsStore(self.root / "settings.ini")
        with patch("controls.QSystemTrayIcon.isSystemTrayAvailable", return_value=False), \
                patch("fonts.QFontDatabase.families", return_value=["Microsoft YaHei UI", "SimSun", "KaiTi"]):
            self.panel = ControlPanel(self.player, self.overlay, self.prefs, self.store)
        self.panel.refresh_timer.stop()
        self.overlay.show()
        self.panel.show()
        APP.processEvents()

    def tearDown(self):
        self.panel.font_library.close()
        self.panel.tray.hide()
        self.panel.hide()
        self.overlay.hide()
        self.panel.deleteLater()
        self.overlay.deleteLater()
        self.player.deleteLater()
        APP.processEvents()
        self.store.store.clear()
        self.store.store.sync()
        self.directory.cleanup()

    def music(self, name="我的歌曲.wav", lyrics=True):
        path = self.root / name
        path.write_bytes(b"test audio placeholder")
        if lyrics:
            path.with_suffix(".lrc").write_text("[00:01]第一句\n[00:05]第二句", encoding="utf-8")
        return path

    def click(self, button):
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        APP.processEvents()

    def test_empty_state_and_persistent_player_bar(self):
        self.assertIn("还没有", self.panel.song_label.text())
        self.assertIn("LRC", self.panel.lyric_label.text())

        self.assertFalse(self.panel.play_button.isEnabled())
        self.assertFalse(self.panel.progress.isEnabled())
        self.assertFalse(self.panel.tray_button.isEnabled())
        bar = self.panel.player_bar.geometry()
        self.click(self.panel.nav_buttons[1])
        self.assertEqual(self.panel.pages.currentIndex(), 1)
        self.assertTrue(self.panel.nav_buttons[1].isChecked())
        self.assertFalse(self.panel.nav_buttons[0].isChecked())
        self.assertEqual(self.panel.player_bar.geometry(), bar)
        self.assertTrue(self.panel.play_button.isVisibleTo(self.panel))

    def test_native_singing_check_saves_an_already_enabled_choice(self):
        from netease_validation import NeteaseSmokeCheck
        self.panel.singing_checkbox.setChecked(True)
        self.player._anchor, self.player._at, self.player.song_id = 1, 2, "demo"
        self.player.playing = True
        checker = NeteaseSmokeCheck.__new__(NeteaseSmokeCheck)
        checker.panel, checker.player, checker.jumps = self.panel, self.player, 0
        checker._check_singing()
        self.assertTrue(all(checker.singing_checks.values()))
        self.assertTrue(self.store.load().singing_sync)

    def test_branding_and_version_are_below_creator_with_no_old_slogans(self):
        from app_info import APP_VERSION, CREATOR, MOTTO
        from PySide6.QtWidgets import QLabel
        self.assertEqual(self.panel.creator_label.text().replace("\n", ""), CREATOR)
        self.assertEqual(self.panel.version_label.text(), f"版本 {APP_VERSION}")
        self.assertEqual(self.panel.motto_label.text().replace("\n", " "), MOTTO)
        self.assertEqual([self.panel.theme_combo.itemText(i) for i in range(3)], ["默认主题", "深色主题", "特殊主题"])
        self.assertLess(self.panel.creator_label.geometry().bottom(), self.panel.version_label.geometry().top())
        texts = [widget.text() for widget in self.panel.findChildren(QLabel)]
        self.assertNotIn("音乐在耳边，歌词在桌面。", texts)
        self.assertNotIn("让工作，有一点节奏。", texts)

    def test_themes_persist_and_keep_transport_lyric_preferences_preview_and_preset(self):
        from dataclasses import asdict
        self.panel.open_music(self.music())
        self.panel.apply_preset("builtin:lively")
        self.player.playing, self.player.clock = True, 6500
        self.panel.preview_background.setCurrentIndex(1)
        original = {key: value for key, value in asdict(self.prefs).items() if key != "theme"}
        refreshes = self.overlay.refreshes
        for theme in ("dark", "special", "light", "dark"):
            self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData(theme))
            APP.processEvents()

            self.assertEqual(self.store.load().theme, theme)
            self.assertEqual({key: value for key, value in asdict(self.prefs).items() if key != "theme"}, original)
            self.assertTrue(self.player.playing)
            self.assertEqual(self.player.clock, 6500)
            self.assertEqual(self.player.seeks, [])
            self.assertEqual(self.overlay.refreshes, refreshes)
            self.assertFalse(self.panel.font_preview.dark)
            self.assertEqual(self.panel.pages.currentIndex(), 0)
            self.assertFalse(self.panel._preset_modified)
            color = self.panel.palette().color(QPalette.ColorRole.Window)
            self.assertEqual(color.lightness() < 80, theme != "light")
            self.assertEqual(self.panel.tray_menu.styleSheet(), self.panel.styleSheet())
        self.panel.apply_preset("builtin:quiet")
        self.assertEqual(self.prefs.theme, "dark")
        self.assertEqual(self.panel.theme_combo.currentData(), "dark")
        # Recreate the window from the persisted setting, like an application restart.
        with patch("controls.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            reopened = ControlPanel(FakePlayer(), FakeOverlay(), self.store.load(), self.store)
        try:
            self.assertEqual(reopened.theme_combo.currentData(), "dark")
            self.assertLess(reopened.palette().color(QPalette.ColorRole.Window).lightness(), 80)
        finally:
            reopened.refresh_timer.stop()
            reopened.font_library.close()
            reopened.deleteLater()
            APP.processEvents()

    def test_both_themes_keep_red_slider_fill_and_adapt_empty_tracks(self):
        from themes import theme_colors
        self.panel.volume_slider.setValue(60)
        for theme in ("dark", "light"):
            self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData(theme))
            APP.processEvents()
            image = self.panel.volume_slider.grab().toImage()
            dpr = image.devicePixelRatio()
            self.assertEqual(image.pixelColor(round(12*dpr), image.height()//2).name(), "#ff3656")
            self.assertEqual(image.pixelColor(image.width()-round(12*dpr), image.height()//2).name(), theme_colors(theme)["track"])

    def test_checkbox_indicators_are_visible_and_show_checked_tick_in_both_themes(self):
        from themes import theme_colors, theme_accent
        for theme in ("dark", "light", "special"):
            self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData(theme))
            for checked in (False, True):
                self.panel.singing_checkbox.setChecked(checked)
                APP.processEvents()
                image = self.panel.singing_checkbox.grab().toImage()
                colors = [image.pixelColor(x,y).name() for x in range(round(18*image.devicePixelRatio()))
                          for y in range(image.height())]
                if checked:
                    self.assertGreater(colors.count(theme_accent(theme)), 20)
                    self.assertGreater(colors.count("#ffffff"), 2)
                else:
                    self.assertGreater(colors.count(theme_colors(theme)["muted"]), 10)

    def test_special_theme_changes_window_application_brand_and_tray_icons_then_restores(self):
        from controls import app_icon
        from themes import ThemeFrame
        frame = self.panel.findChild(ThemeFrame, "card")
        original = app_icon().pixmap(32, 32).toImage()
        clock = app_icon("special").pixmap(32, 32).toImage()
        self.assertFalse(clock.isNull())
        self.assertNotEqual(clock, original)
        for size in (16, 32, 64, 128):
            image = app_icon("special").pixmap(size, size).toImage()
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)
            self.assertEqual(image.pixelColor(image.width()//2, round(image.height()*.6)).alpha(), 255)
        for theme in ("light", "dark"):
            self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData(theme))
            APP.processEvents()
            normal_frame = frame.grab().toImage()
            self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData("special"))
            APP.processEvents()
            self.assertNotEqual(frame.grab().toImage(), normal_frame)
            for icon in (self.panel.windowIcon(), self.panel.tray.icon(), APP.windowIcon()):
                self.assertEqual(icon.pixmap(32, 32).toImage(), clock)
            self.assertEqual(self.panel.brand_icon.pixmap().toImage(), app_icon("special").pixmap(36, 36).toImage())
            self.assertEqual(self.store.load().theme, "special")
            self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData(theme))
            APP.processEvents()
            self.assertEqual(frame.grab().toImage(), normal_frame)
            for icon in (self.panel.windowIcon(), self.panel.tray.icon(), APP.windowIcon()):
                self.assertEqual(icon.pixmap(32, 32).toImage(), original)
        self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData("special"))
        with patch("controls.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            reopened = ControlPanel(FakePlayer(), FakeOverlay(), self.store.load(), self.store)
        try:
            self.assertEqual(reopened.theme_combo.currentData(), "special")
            for icon in (reopened.windowIcon(), reopened.tray.icon(), APP.windowIcon()):
                self.assertEqual(icon.pixmap(32, 32).toImage(), clock)
        finally:
            reopened.refresh_timer.stop()
            reopened.font_library.close()
            reopened.deleteLater()
            APP.processEvents()

    def test_special_theme_slider_and_minimum_window_keep_controls_reachable(self):
        self.panel.theme_combo.setCurrentIndex(self.panel.theme_combo.findData("special"))
        self.panel.volume_slider.setValue(60)
        APP.processEvents()
        image = self.panel.volume_slider.grab().toImage()
        self.assertEqual(image.pixelColor(round(12*image.devicePixelRatio()), image.height()//2).name(), "#ffb526")
        self.panel.resize(self.panel.minimumSize())
        self.panel._select_page(1)
        APP.processEvents()
        for control in (self.panel.brand_icon, self.panel.creator_label, self.panel.theme_combo,
                        self.panel.motto_label, self.panel.tray_button, self.panel.exit_button):
            self.assertTrue(self.panel.sidebar.rect().contains(QRect(control.mapTo(self.panel.sidebar, QPoint()), control.size())))
        self.panel.effects_scroll.ensureWidgetVisible(self.panel.singing_checkbox)
        APP.processEvents()
        self.assertTrue(self.panel.singing_checkbox.isVisibleTo(self.panel))
        self.assertTrue(self.panel.rect().contains(QRect(self.panel.player_bar.mapTo(self.panel, QPoint()), self.panel.player_bar.size())))

    def test_effects_entry_restores_hidden_minimized_panel_without_changing_playback(self):
        self.player.playing = True
        self.panel.showMinimized()
        self.panel.hide()
        self.panel.show_effects()
        APP.processEvents()
        self.assertTrue(self.panel.isVisible())
        self.assertFalse(self.panel.isMinimized())
        self.assertEqual(self.panel.pages.currentIndex(), 1)
        self.assertTrue(self.panel.nav_buttons[1].isChecked())
        self.assertTrue(self.player.playing)
        self.assertTrue(self.overlay.isVisible())

    def test_import_updates_song_footer_and_matching_lyrics(self):
        path = self.music()
        with patch("controls.QFileDialog.getOpenFileName", return_value=(str(path), "")):
            self.click(self.panel.import_button)
        self.panel._refresh_position()
        self.assertEqual(self.panel.song_label.text(), path.stem)
        self.assertEqual(self.panel.footer_song.text(), path.stem)
        self.assertEqual(self.panel.footer_song.toolTip(), str(path))
        self.assertEqual(self.panel.format_label.text(), "WAV")
        self.assertEqual(self.panel.track_duration.text(), "00:24")
        self.assertIn("2 句", self.panel.lyric_label.text())
        self.assertIsNotNone(self.overlay.document)
        self.assertTrue(self.panel.play_button.isEnabled())

    def test_switching_music_clears_old_lyric_status(self):
        self.panel.open_music(self.music())
        self.panel.open_music(self.music("另一首.wav", lyrics=False))
        self.assertIsNone(self.overlay.document)
        self.assertIn("未找到", self.panel.lyric_label.text())
        self.assertEqual(self.panel.lyric_label.toolTip(), "")
        self.assertEqual(self.panel.footer_song.text(), "另一首")

    def test_invalid_music_keeps_previous_song_and_lyrics(self):
        path = self.music()
        self.panel.open_music(path)
        original = self.overlay.document
        self.panel.open_music(self.root / "missing.wav")
        self.assertEqual(self.player.path, path)
        self.assertEqual(self.panel.song_label.text(), path.stem)
        self.assertIs(self.overlay.document, original)
        self.assertTrue(self.panel.notice.isVisibleTo(self.panel))
        self.assertIn("不存在", self.panel.notice.text())

    def test_navigation_preserves_playback_and_pause_position(self):
        self.panel.open_music(self.music())
        self.click(self.panel.play_button)
        self.player.clock = 6500
        self.click(self.panel.nav_buttons[1])
        self.assertTrue(self.player.playing)
        self.assertEqual(self.player.clock, 6500)
        self.assertEqual(self.player.seeks, [])
        self.click(self.panel.play_button)
        self.assertFalse(self.player.playing)
        self.assertEqual(self.panel.play_button.accessibleName(), "开始播放")
        self.click(self.panel.nav_buttons[0])
        self.click(self.panel.play_button)
        self.assertTrue(self.player.playing)
        self.assertEqual(self.player.clock, 6500)
        self.assertEqual(self.panel.play_button.accessibleName(), "暂停音乐")

    def test_settings_save_across_navigation_and_color_is_independent(self):
        self.click(self.panel.nav_buttons[1])
        self.panel.region.setCurrentIndex(self.panel.region.findData("full"))
        self.panel.motion.setCurrentIndex(self.panel.motion.findData("wave"))
        self.panel.spins["jump"].setValue(18)
        self.panel.spins["delay_ms"].setValue(-500)
        self.panel.volume_slider.setValue(28)
        with patch("controls.QColorDialog.getColor", return_value=QColor("#ffffff")):
            self.click(self.panel.color_button)
        self.click(self.panel.nav_buttons[0])
        self.click(self.panel.nav_buttons[1])
        saved = self.store.load()
        self.assertEqual((saved.region, saved.motion, saved.jump, saved.delay_ms, saved.volume, saved.color),
                         ("full", "wave", 18, -500, 28, "#ffffff"))
        self.assertEqual(self.panel.spins["jump"].value(), 18)
        self.assertEqual(self.player.volume, 28)
        self.assertGreater(self.overlay.refreshes, 0)
        self.assertIn("#FFFFFF", self.panel.color_button.text())
        self.assertLess(self.panel.color_button.palette().color(QPalette.ColorRole.ButtonText).lightness(), 180)

    def test_font_presets_save_without_changing_playback_or_ui_theme(self):
        self.panel.open_music(self.music())
        self.player.playing = True
        self.player.clock = 6500
        style = self.panel.styleSheet()
        self.click(self.panel.nav_buttons[1])
        self.assertEqual([self.panel.font_combo.itemText(i) for i in range(3)], ["微软雅黑（默认）", "宋体", "楷体"])
        for family in ("SimSun", "KaiTi", "Microsoft YaHei UI"):
            self.panel.font_combo.setCurrentIndex(self.panel.font_combo.findData(family))
            self.assertEqual(self.store.load().font_family, family)
            self.assertEqual(self.prefs.font_family, family)
            self.assertTrue(self.player.playing)
            self.assertEqual(self.player.clock, 6500)
            self.assertEqual(self.player.seeks, [])
        self.assertEqual(self.panel.styleSheet(), style)
        self.assertGreater(self.overlay.refreshes, 0)

    def test_effect_controls_save_and_keep_transport_and_color(self):
        self.click(self.panel.nav_buttons[1])
        self.player.playing, self.player.clock = True, 6500
        original_color = self.prefs.color
        self.assertEqual(self.panel.text_style.currentData(), "glow")
        self.assertEqual(self.panel.color_label.text(), "描边颜色")
        self.assertTrue(self.panel.glow_slider.isEnabled())
        self.panel.glow_slider.setValue(95)
        self.panel.text_style.setCurrentIndex(self.panel.text_style.findData("solid"))
        self.assertEqual(self.panel.color_label.text(), "文字颜色")
        self.assertFalse(self.panel.glow_slider.isEnabled())
        self.assertFalse(self.panel.white_hint.isVisibleTo(self.panel))
        self.assertEqual((self.store.load().text_style, self.store.load().glow_strength), ("solid", 95))
        self.panel.text_style.setCurrentIndex(self.panel.text_style.findData("glow"))
        self.assertTrue(self.panel.white_hint.isVisibleTo(self.panel))
        self.assertEqual(self.prefs.color, original_color)
        self.assertEqual((self.player.playing, self.player.clock, self.player.seeks), (True, 6500, []))

    def test_preview_background_does_not_modify_preferences_or_desktop(self):
        self.click(self.panel.nav_buttons[1])
        self.panel.glow_slider.setValue(61)
        saved = self.store.load()
        refreshes = self.overlay.refreshes
        dark = self.panel.font_preview.grab().toImage()
        self.panel.preview_background.setCurrentIndex(1)
        light = self.panel.font_preview.grab().toImage()
        self.assertFalse(self.panel.font_preview.dark)
        self.assertNotEqual(bytes(dark.constBits()), bytes(light.constBits()))
        self.assertEqual(self.store.load(), saved)
        self.assertEqual(self.overlay.refreshes, refreshes)

    def test_carmen_variant_is_nested_in_glow_and_does_not_change_transport(self):
        self.click(self.panel.nav_buttons[1])
        self.player.playing, self.player.clock = True, 6500
        original_color = self.prefs.color
        self.panel.glow_variant.setCurrentIndex(self.panel.glow_variant.findData("carmen"))
        self.assertEqual(self.store.load().glow_variant, "carmen")
        self.assertIn("固定暖白", self.panel.white_hint.text())
        self.assertFalse(self.panel.color_button.isEnabled())
        self.assertTrue(self.panel.glow_slider.isEnabled())
        self.panel.text_style.setCurrentIndex(self.panel.text_style.findData("solid"))
        self.assertFalse(self.panel.glow_variant.isEnabled())
        self.assertTrue(self.panel.color_button.isEnabled())
        self.panel.text_style.setCurrentIndex(self.panel.text_style.findData("glow"))
        self.assertEqual(self.panel.glow_variant.currentData(), "carmen")
        self.panel.glow_variant.setCurrentIndex(self.panel.glow_variant.findData("standard"))
        self.assertTrue(self.panel.color_button.isEnabled())
        self.assertEqual(self.prefs.color, original_color)
        self.assertEqual((self.player.playing, self.player.clock, self.player.seeks), (True, 6500, []))

    def test_translation_checkbox_saves_and_presets_do_not_override_language(self):
        from lrc import LyricDocument, LyricLine, TimedWord
        self.player.clock, self.player.playing = 6500, False
        self.overlay.set_document(LyricDocument([LyricLine(1000, "Original", (TimedWord(1000, 2000, 0, 8),), "中文译文")], []))
        self.panel.translation_checkbox.setChecked(True)
        self.assertTrue(self.store.load().prefer_translation)
        self.assertIn("中文译文按整句同步", self.panel.word_status.text())
        self.panel.apply_preset("builtin:quiet")
        self.assertTrue(self.panel.translation_checkbox.isChecked())
        self.assertTrue(self.prefs.prefer_translation)
        self.assertEqual((self.player.playing, self.player.clock, self.player.seeks), (False, 6500, []))

    def test_smoke_resets_effect_controls_from_saved_classic_settings(self):
        from validation import SmokeCheck
        self.panel.text_style.setCurrentIndex(self.panel.text_style.findData("solid"))
        self.panel.glow_slider.setValue(0)
        self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData("fall_shake"))
        check = object.__new__(SmokeCheck)
        check.app, check.panel, check.player = APP, self.panel, self.player
        check.report_dir, check.results = self.root, {}
        with patch.object(self.panel, "play_demo"), patch("validation.QTimer.singleShot"):
            check.start()
        self.assertEqual(self.panel.text_style.currentData(), "glow")
        self.assertEqual(self.panel.glow_slider.value(), 60)
        self.assertEqual((self.prefs.text_style, self.prefs.glow_strength), ("glow", 60))
        self.assertEqual(self.panel.animation_combo.currentData(), "classic")

    def test_font_import_button_copies_selects_and_restores_after_restart(self):
        fixture = Path(__file__).parent / "fixtures/lyrics-test.ttf"
        source = self.root / "自定义 字体.TTF"
        source.write_bytes(fixture.read_bytes())
        self.click(self.panel.nav_buttons[1])
        with patch("controls.QFileDialog.getOpenFileName", return_value=(str(source), "")):
            self.click(self.panel.import_font_button)
        self.assertEqual(self.store.load().font_family, "Floating Lyrics Test")
        self.assertEqual(self.panel.font_combo.currentData(), "Floating Lyrics Test")
        self.assertIn("已导入", self.panel.font_status.text())
        self.assertEqual(len(list((self.root / "fonts").glob("*.ttf"))), 1)
        source.unlink()
        self.panel.font_library.close()
        self.panel.hide()
        self.panel.deleteLater()
        with patch("controls.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            self.panel = ControlPanel(self.player, self.overlay, self.store.load(), self.store)
        self.assertEqual(self.panel.font_combo.currentData(), "Floating Lyrics Test")
        self.assertEqual(self.panel.prefs.font_family, "Floating Lyrics Test")

    def test_preset_applies_once_and_preserves_region_offset_volume_and_preview_background(self):
        self.panel.region.setCurrentIndex(1)
        self.panel.spins["delay_ms"].setValue(700)
        self.panel.preview_background.setCurrentIndex(1)
        before = self.overlay.refreshes
        with patch.object(self.store, "save", wraps=self.store.save) as save:
            self.panel.preset_combo.setCurrentIndex(self.panel.preset_combo.findData("builtin:quiet"))
            self.assertEqual(save.call_count, 1)
        self.assertEqual(self.overlay.refreshes, before + 1)
        self.assertEqual((self.prefs.font_family, self.prefs.font_size, self.prefs.entry_speed), ("SimSun", 28, 80))
        self.assertEqual((self.prefs.region, self.prefs.delay_ms, self.prefs.volume, self.panel.font_preview.dark),
                         ("full", 700, 45, False))
        self.panel.spins["font_size"].setValue(30)
        self.assertIn("已修改", self.panel.preset_combo.currentText())
        self.assertEqual(self.panel.presets.get("builtin:quiet").values["font_size"], 28)
        self.assertFalse(self.panel.preset_update_button.isEnabled())
        self.assertEqual(self.player.seeks, [])

    def test_custom_preset_confirmation_cancel_update_delete_and_font_fallback(self):
        from PySide6.QtWidgets import QMessageBox
        self.assertTrue(self.panel.save_preset("自己的方案"))
        identifier = self.panel._preset_id
        self.panel.spins["entry_speed"].setValue(200)
        with patch("controls.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.assertFalse(self.panel.update_preset())
            self.assertFalse(self.panel.delete_preset())
        self.assertEqual(self.panel.presets.get(identifier).values["entry_speed"], 100)
        with patch("controls.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(self.panel.update_preset())
        self.prefs.font_family = "Unavailable Imported Font"
        saved = self.panel.presets.save("字体缺失方案", self.prefs)
        self.panel.apply_preset(saved.id)
        self.assertEqual(self.prefs.font_family, "Microsoft YaHei UI")
        self.assertIn("不可用", self.panel.font_status.text())
        with patch("controls.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(self.panel.delete_preset())
        self.assertEqual(self.prefs.entry_speed, 200)

    def test_singing_switch_status_and_presets_keep_transport(self):
        from lrc import LyricDocument, LyricLine, TimedWord
        self.panel.open_music(self.music())
        self.player.clock, self.player.playing = 1800, True
        self.overlay.set_document(LyricDocument([LyricLine(1000, "你好", (TimedWord(1200, 2200, 0, 2),))], []))
        self.panel.singing_checkbox.setChecked(True)
        self.assertIs(self.store.load().singing_sync, True)
        self.assertEqual(self.panel.word_status.text(), "逐字时间可用")
        self.panel.apply_preset("builtin:quiet")
        self.assertFalse(self.panel.singing_checkbox.isChecked())
        self.assertEqual((self.player.clock, self.player.playing, self.player.seeks), (1800, True, []))
        self.overlay.set_document(None)
        self.panel._refresh_word_status()
        self.assertEqual(self.panel.word_status.text(), "本曲无逐字时间")

    def test_animation_parameter_pairs_save_and_enable_only_relevant_controls(self):
        self.panel.spins["entry_speed"].setValue(180)
        self.panel.parameter_sliders["exit_speed"].setValue(65)
        self.assertEqual(self.store.load().entry_speed, 180)
        self.assertEqual(self.panel.spins["exit_speed"].value(), 65)
        self.assertFalse(self.panel.parameter_fields["shake_frequency"].isEnabled())
        self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData("fall_shake"))
        self.assertTrue(self.panel.parameter_fields["shake_frequency"].isEnabled())
        self.assertTrue(self.panel.parameter_fields["fall_distance"].isEnabled())
        self.panel.spins["shake_frequency"].setValue(12)
        self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData("ripple_wave"))
        self.assertEqual(self.store.load().shake_frequency, 12)
        self.assertFalse(self.panel.parameter_fields["fall_distance"].isEnabled())
        self.assertEqual(self.player.seeks, [])

    def test_four_animation_options_save_without_mutating_transport(self):
        from settings import ANIMATION_STYLES
        self.player.playing, self.player.clock = True, 6500
        self.click(self.panel.nav_buttons[1])
        self.assertEqual(self.panel.animation_combo.currentData(), "classic")
        self.assertEqual(self.panel.animation_combo.count(), 5)
        for style in ANIMATION_STYLES:
            self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData(style))
            self.assertEqual(self.store.load().animation_style, style)
            self.assertTrue(self.player.playing)
            self.assertEqual(self.player.clock, 6500)
            self.assertFalse(self.player.seeks)

    def test_preview_replay_is_independent_and_stops_when_hidden(self):
        self.click(self.panel.nav_buttons[1])
        self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData("fall_shake"))
        scroll = self.panel.effects_scroll
        scroll.ensureWidgetVisible(self.panel.font_preview)
        APP.processEvents()
        self.click(self.panel.replay_button)
        QTest.qWait(180)
        self.assertTrue(self.panel.font_preview.timer.isActive())
        self.assertGreater(self.panel.font_preview._preview_position(), 100)
        self.assertFalse(self.player.playing)
        self.assertEqual(self.player.clock, 0)
        self.click(self.panel.nav_buttons[0])
        self.assertFalse(self.panel.font_preview.timer.isActive())

    def test_preview_timer_stops_when_scrolled_out_and_restarts_on_reveal(self):
        self.click(self.panel.nav_buttons[1])
        self.panel.resize(900, 560)
        self.panel.animation_combo.setCurrentIndex(self.panel.animation_combo.findData("ripple_wave"))
        scroll = self.panel.effects_scroll
        scroll.ensureWidgetVisible(self.panel.font_preview)
        APP.processEvents()
        self.panel.font_preview.replay()
        self.assertTrue(self.panel.font_preview.timer.isActive())
        scroll.verticalScrollBar().setValue(0)
        QTest.qWait(70)
        self.assertFalse(self.panel.font_preview.timer.isActive())
        scroll.ensureWidgetVisible(self.panel.font_preview)
        APP.processEvents()
        self.assertTrue(self.panel.font_preview.timer.isActive())

    def test_font_import_cancel_and_invalid_data_leave_existing_choice_unchanged(self):
        self.panel.font_combo.setCurrentIndex(self.panel.font_combo.findData("KaiTi"))
        before = self.store.load()
        with patch("controls.QFileDialog.getOpenFileName", return_value=("", "")):
            self.click(self.panel.import_font_button)
        invalid = self.root / "损坏.ttf"
        invalid.write_bytes(b"this is not a font")
        with patch("controls.QFileDialog.getOpenFileName", return_value=(str(invalid), "")):
            self.click(self.panel.import_font_button)
        self.assertEqual(self.store.load(), before)
        self.assertEqual(self.panel.font_combo.currentData(), "KaiTi")
        self.assertIn("无法读取", self.panel.font_status.text())
        self.assertFalse((self.root / "fonts").exists())

    def test_missing_selected_font_falls_back_with_visible_explanation(self):
        self.panel.font_library.close()
        self.panel.hide()
        self.panel.deleteLater()
        self.prefs.font_family = "Removed custom family"
        with patch("controls.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            self.panel = ControlPanel(self.player, self.overlay, self.prefs, self.store)
        self.assertEqual(self.prefs.font_family, "Microsoft YaHei UI")
        self.assertEqual(self.panel.font_combo.currentIndex(), 0)
        self.assertIn("不可用", self.panel.font_status.text())

    def test_errors_remain_visible_on_effects_page(self):
        self.click(self.panel.nav_buttons[1])
        self.player.error.emit("播放失败：音频不可用")
        self.assertEqual(self.panel.pages.currentIndex(), 1)
        self.assertTrue(self.panel.notice.isVisibleTo(self.panel))
        self.assertIn("播放失败", self.panel.notice.text())
        self.panel.open_lyrics(self.root / "missing.lrc")
        self.assertIn("歌词读取失败", self.panel.notice.text())
        self.click(self.panel.nav_buttons[0])
        self.assertTrue(self.panel.notice.isVisibleTo(self.panel))

    def test_refresh_never_seeks_and_drag_seeks_only_on_release(self):
        self.panel.open_music(self.music())
        self.player.clock = 9100
        self.panel._refresh_position()
        self.assertEqual(self.player.seeks, [])
        self.assertEqual(self.panel.progress.value(), 9100)
        self.panel.progress.setSliderDown(True)
        self.panel.progress.setValue(16000)
        self.panel._refresh_position()
        self.assertEqual(self.player.seeks, [])
        self.assertEqual(self.panel.progress.value(), 16000)
        self.panel.progress.setSliderDown(False)
        self.assertEqual(self.player.seeks, [16000])
        self.panel.progress.setFocus()
        QTest.keyClick(self.panel.progress, Qt.Key.Key_Right)
        self.assertEqual(len(self.player.seeks), 2)
        self.assertGreater(self.player.seeks[-1], 16000)

    def test_lyric_visibility_control_works_on_both_pages(self):
        self.click(self.panel.nav_buttons[1])
        self.click(self.panel.visibility_button)
        self.assertFalse(self.overlay.isVisible())
        self.assertEqual(self.panel.tray_visibility.text(), "显示歌词")
        self.click(self.panel.nav_buttons[0])
        self.click(self.panel.visibility_button)
        self.assertTrue(self.overlay.isVisible())
        self.assertEqual(self.panel.visibility_button.text(), "隐藏歌词")

    def test_long_title_and_minimum_window_keep_controls_accessible(self):
        title = "很长的中文歌曲名" * 16
        self.panel.open_music(self.music(title + ".wav"))
        self.panel.resize(900, 560)
        APP.processEvents()
        self.assertEqual(self.panel.footer_song.text(), title)
        for button in (self.panel.play_button, self.panel.visibility_button, self.panel.volume_slider):
            rectangle = QRect(button.mapTo(self.panel, QPoint()), button.size())
            self.assertTrue(self.panel.rect().contains(rectangle))
        self.click(self.panel.nav_buttons[1])
        scroll = self.panel.effects_scroll
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        for widget in (self.panel.region, self.panel.font_combo, self.panel.import_font_button, self.panel.font_preview,
                       self.panel.text_style, self.panel.glow_variant, self.panel.translation_checkbox, self.panel.preview_background, self.panel.glow_field, self.panel.animation_combo, self.panel.replay_button,
                       self.panel.color_button, self.panel.motion, *self.panel.spins.values()):
            center = widget.mapTo(scroll.widget(), widget.rect().center())
            scroll.ensureVisible(center.x(), center.y(), 0, widget.height() // 2 + 16)
            APP.processEvents()
            rectangle = QRect(widget.mapTo(scroll.viewport(), QPoint()), widget.size())
            self.assertTrue(scroll.viewport().rect().contains(rectangle))

    def test_screen_fit_uses_available_geometry_including_offset(self):
        available = QRect(1920, 80, 1024, 640)
        self.panel.fit_to_screen(available)
        APP.processEvents()
        self.assertTrue(available.contains(QRect(self.panel.pos(), self.panel.size())))
        self.assertLessEqual(self.panel.width(), available.width() - 48)
        self.assertLessEqual(self.panel.height(), available.height() - 64)
        self.assertEqual(self.panel.minimumWidth(), 900)
        smaller = QRect(1920, 80, 800, 520)
        self.panel.fit_to_screen(smaller)
        APP.processEvents()
        self.assertTrue(smaller.contains(QRect(self.panel.pos(), self.panel.size())))
        self.assertLess(self.panel.minimumHeight(), 560)

    def test_netease_mode_updates_song_lyrics_without_local_audio_controls(self):
        from netease import NeteasePlayer, validate_snapshot
        from test_netease import packet
        self.panel.tray.hide()
        self.panel.hide()
        self.panel.deleteLater()
        self.player = NeteasePlayer()
        with patch("controls.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            self.panel = ControlPanel(self.player, self.overlay, self.prefs, self.store)
        self.panel.refresh_timer.stop()
        self.panel.show()
        self.player.apply(validate_snapshot(packet()))
        self.panel._refresh_position()
        APP.processEvents()
        self.assertEqual(self.panel.song_label.text(), "测试歌曲")
        self.assertEqual(self.panel.footer_song.text(), "测试歌曲")
        self.assertEqual(self.panel.footer_detail.text(), "测试歌手")
        self.assertIn("2 句", self.panel.lyric_label.text())
        self.assertIsNotNone(self.overlay.document)
        for widget in (self.panel.import_button, self.panel.lyrics_button, self.panel.demo_button, self.panel.volume_slider):
            self.assertFalse(widget.isVisibleTo(self.panel))
        self.assertFalse(self.panel.play_button.isEnabled())
        self.assertTrue(self.panel.progress.isEnabled())
        self.assertTrue(self.panel.progress.display_only)
        before = self.player.position()
        QTest.keyClick(self.panel.progress, Qt.Key.Key_Right)
        self.assertLess(abs(self.player.position()-before), 100)
        self.click(self.panel.nav_buttons[1])
        self.assertTrue(self.player.playing)
        self.panel.spins["jump"].setValue(19)
        self.assertEqual(self.store.load().jump, 19)
        self.player.apply(validate_snapshot(packet(lyrics=[])))
        self.panel.font_combo.setCurrentIndex(self.panel.font_combo.findData("KaiTi"))
        self.assertIsNone(self.overlay.document)
        self.assertIn("保持空白", self.panel.lyric_label.text())
        self.player.disconnect()
        self.assertIsNone(self.overlay.document)
        self.assertIn("断开", self.panel.notice.text())


if __name__ == "__main__":
    unittest.main()
