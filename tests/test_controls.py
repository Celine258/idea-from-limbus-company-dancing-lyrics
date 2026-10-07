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

    def test_smoke_resets_effect_controls_from_saved_classic_settings(self):
        from validation import SmokeCheck
        self.panel.text_style.setCurrentIndex(self.panel.text_style.findData("solid"))
        self.panel.glow_slider.setValue(0)
        check = object.__new__(SmokeCheck)
        check.app, check.panel, check.player = APP, self.panel, self.player
        check.report_dir, check.results = self.root, {}
        with patch.object(self.panel, "play_demo"), patch("validation.QTimer.singleShot"):
            check.start()
        self.assertEqual(self.panel.text_style.currentData(), "glow")
        self.assertEqual(self.panel.glow_slider.value(), 60)
        self.assertEqual((self.prefs.text_style, self.prefs.glow_strength), ("glow", 60))

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
                       self.panel.text_style, self.panel.preview_background, self.panel.glow_field,
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
