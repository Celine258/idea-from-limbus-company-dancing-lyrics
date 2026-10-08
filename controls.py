from pathlib import Path
import ctypes
from ctypes import wintypes
import logging
import sys
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, QElapsedTimer, QSignalBlocker
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPalette, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QColorDialog, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSizePolicy, QInputDialog, QMessageBox, QCheckBox,
    QSlider, QSpinBox, QStackedWidget, QStyle, QStyleOptionSlider, QSystemTrayIcon, QVBoxLayout, QWidget,
)
from lrc import load_lrc, ActiveLine, TimedWord, word_timing_status
from fonts import FontLibrary
from animation import _glyph_layout
from text_effects import TEXT_EFFECTS
from settings import resource_path, ANIMATION_STYLES
from glyph_motion import glyph_states
from presets import PresetStore, EFFECT_KEYS
from app_info import APP_NAME, APP_VERSION, CREATOR, MOTTO
from themes import theme_colors, theme_stylesheet, theme_palette, theme_accent, accent_text, ThemeFrame, ThemeCanvas


def symbol_icon(kind: str, color: str = "#7b8597") -> QIcon:
    """Draw scalable, local icons without platform-dependent symbol fonts."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(64 / 24, 64 / 24)
    painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == "play":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF([QPointF(8, 5), QPointF(19, 12), QPointF(8, 19)]))
    elif kind == "pause":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRectF(7, 5, 3, 14), 1, 1)
        painter.drawRoundedRect(QRectF(14, 5, 3, 14), 1, 1)
    elif kind == "music":
        painter.drawLine(10, 16, 10, 5)
        painter.drawLine(10, 5, 19, 3)
        painter.drawLine(19, 3, 19, 14)
        painter.drawEllipse(QRectF(4, 15, 6, 5))
        painter.drawEllipse(QRectF(13, 13, 6, 5))
    elif kind == "wave":
        for x, top, bottom in ((4, 9, 15), (8, 5, 19), (12, 3, 21), (16, 7, 17), (20, 10, 14)):
            painter.drawLine(x, top, x, bottom)
    elif kind == "import":
        painter.drawLine(12, 3, 12, 15)
        painter.drawLine(8, 11, 12, 15)
        painter.drawLine(16, 11, 12, 15)
        painter.drawPolyline(QPolygonF([QPointF(4, 15), QPointF(4, 20), QPointF(20, 20), QPointF(20, 15)]))
    elif kind == "lyrics":
        painter.drawRoundedRect(QRectF(4, 3, 16, 18), 3, 3)
        for y, end in ((8, 16), (12, 16), (16, 13)):
            painter.drawLine(8, y, end, y)
    elif kind == "volume":
        painter.drawPolygon(QPolygonF([QPointF(3, 9), QPointF(7, 9), QPointF(12, 5),
                                      QPointF(12, 19), QPointF(7, 15), QPointF(3, 15)]))
        painter.drawArc(QRectF(11, 7, 8, 10), -70 * 16, 140 * 16)
        painter.drawArc(QRectF(10, 3, 13, 18), -60 * 16, 120 * 16)
    elif kind == "tray":
        painter.drawLine(12, 3, 12, 14)
        painter.drawLine(8, 10, 12, 14)
        painter.drawLine(16, 10, 12, 14)
        painter.drawRoundedRect(QRectF(3, 17, 18, 4), 1, 1)
    elif kind == "exit":
        painter.drawArc(QRectF(4, 4, 16, 16), 135 * 16, 270 * 16)
        painter.drawLine(12, 2, 12, 11)
    painter.end()
    return QIcon(pixmap)


def app_icon(theme="light") -> QIcon:
    if theme == "special":
        return QIcon(str(resource_path("assets/dante-clock.svg")))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ff3656"))
    painter.drawEllipse(2, 2, 60, 60)
    painter.drawPixmap(12, 12, 40, 40, symbol_icon("wave", "#ffffff").pixmap(64, 64))
    painter.end()
    return QIcon(pixmap)


def record_pixmap() -> QPixmap:
    pixmap = QPixmap(112, 112)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#293449"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, 108, 108)
    painter.setPen(QPen(QColor("#465166"), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for inset in (12, 19, 26):
        painter.drawEllipse(inset, inset, 112 - inset * 2, 112 - inset * 2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#ff3656"))
    painter.drawEllipse(36, 36, 40, 40)
    painter.setBrush(QColor("#ffffff"))
    painter.drawEllipse(51, 51, 10, 10)
    painter.end()
    return pixmap


def label(text: str, name: str = "") -> QLabel:
    item = QLabel(text)
    item.setObjectName(name)
    item.setWordWrap(True)
    return item


class ElidedLabel(QLabel):
    """Keep the full title and tooltip while a narrow window elides its painting."""
    def __init__(self, text: str, name: str = ""):
        super().__init__(text)
        self.setObjectName(name)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        painter.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignVCenter,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight,
                                                       self.contentsRect().width()))


class ThinSlider(QSlider):
    """Flat tracks with QSlider's native input, keyboard and accessibility behavior."""
    display_only = False

    def mousePressEvent(self, event):
        if self.display_only:
            event.ignore()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.display_only:
            event.ignore()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if self.display_only:
            event.ignore()
        else:
            super().wheelEvent(event)

    def paintEvent(self, event):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                            QStyle.SubControl.SC_SliderHandle, self)
        center = handle.center()
        height = 3 if self.objectName() == "progress" else 4
        groove = QRectF(handle.width() / 2, self.height() / 2 - height / 2,
                        self.width() - handle.width(), height)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme_colors(self.window().property("interfaceTheme"))["track"]))
        painter.drawRoundedRect(groove, height / 2, height / 2)
        if self.isEnabled() and self.maximum() > self.minimum():
            painter.setBrush(QColor(theme_accent(self.window().property("interfaceTheme"))))
            filled = QRectF(groove)
            if option.upsideDown:
                filled.setLeft(center.x())
            else:
                filled.setRight(center.x())
            painter.drawRoundedRect(filled, height / 2, height / 2)
            radius = 4 if self.objectName() == "progress" else 6
            painter.drawEllipse(QPointF(center.x(), self.height() / 2), radius, radius)
            if self.hasFocus():
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#b98731" if self.window().property("interfaceTheme") == "special" else "#b7213c"), 1))
                painter.drawEllipse(QPointF(center.x(), self.height() / 2), radius + 2, radius + 2)
        painter.end()


def card(title: str):
    frame = ThemeFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 20, 24, 22)
    layout.setSpacing(16)
    layout.addWidget(label(title, "section"))
    return frame, layout


class FontPreview(QWidget):
    def __init__(self, prefs):
        super().__init__()
        self.prefs = prefs
        self.dark = True
        self._key = None
        self._surface = None
        self._running = prefs.animation_style != "classic" or prefs.singing_sync
        self._position = 0
        self._elapsed = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.setFixedHeight(150)
        self.setAccessibleName("中英文字体效果预览")

    def replay(self):
        self._position = 0
        self._running = True
        self._elapsed.restart()
        if self.isVisible() and not self.visibleRegion().isEmpty():
            self.timer.start()
        self.update()

    def _preview_position(self):
        return (self._position + (self._elapsed.elapsed() if self.timer.isActive() else 0)) % (self._preview_item().end_ms + 400)

    def _preview_item(self):
        end = 3800 if self.prefs.animation_style == "classic" else 3200 + min(600 * 100 / self.prefs.exit_speed, 4400 * .45)
        words = tuple(TimedWord(800+i*160, 960+i*160, i, i+1) for i in range(7)) + (
            TimedWord(2000, 2400, 8, 13), TimedWord(2500, 2900, 14, 19), TimedWord(2950, 3200, 22, 25))
        return ActiveLine(0, "", 0, end, 1, min(700 * 100 / self.prefs.entry_speed, 3200 * .35), 3200, words)

    def _stop_preview(self):
        self._position = self._preview_position()
        self.timer.stop()

    def _tick(self):
        if not self.isVisible() or self.visibleRegion().isEmpty():
            self._stop_preview()
        else:
            self.update()

    def hideEvent(self, event):
        self._stop_preview()
        super().hideEvent(event)

    def set_background(self, dark):
        self.dark = dark
        self.update()

    def paintEvent(self, _event):
        if self._running and not self.timer.isActive() and not self.visibleRegion().isEmpty():
            self._elapsed.restart()
            self.timer.start()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#e0e5ed"), 1))
        painter.setBrush(QColor("#18232f" if self.dark else "#f7f8fa"))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 8, 8)
        pixels = min(28, self.prefs.font_size)
        key = (self.width(), pixels, self.prefs.font_family, self.prefs.color, self.prefs.text_style,
               self.devicePixelRatioF(), self.prefs.animation_style, self.prefs.jump, self.prefs.fall_distance, self.prefs.singing_sync)
        if key != self._key:
            glyphs, _, _ = _glyph_layout("给今天一点节奏\nHello music · 123", pixels,
                                         max(1, self.width() - 48), self.prefs.font_family)
            self._surface = TEXT_EFFECTS.prepare(glyphs, pixels, self.prefs, self.devicePixelRatioF(), self.prefs.jump)
            self._key = key
        position = self._preview_position()
        states = (glyph_states(self._surface.glyphs, self.prefs,
                              self._preview_item(), position, .5, pixels, 730)
                  if self.prefs.animation_style != "classic" or self.prefs.singing_sync else None)
        image = TEXT_EFFECTS.render(self._surface, self.prefs, states=states)
        width = 2 * max(abs(self._surface.origin.x()), abs(self._surface.origin.x() + image.width() / image.devicePixelRatio()))
        height = 2 * max(abs(self._surface.origin.y()), abs(self._surface.origin.y() + image.height() / image.devicePixelRatio()))
        painter.translate(self.rect().center())
        scale = min(1, max(1, self.width() - 24) / max(1, width), (self.height() - 16) / max(1, height))
        painter.scale(scale, scale)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        opacity = self.prefs.opacity / 100
        if self._running and self.prefs.animation_style == "classic":
            opacity *= max(0, min(1, position / min(300 * 100 / self.prefs.entry_speed, 1900),
                                 (3800 - position) / min(600 * 100 / self.prefs.exit_speed, 1900)))
        painter.setOpacity(opacity)
        painter.drawImage(self._surface.origin, image)

    def invalidate(self):
        self._key = None
        self.update()


class ControlPanel(QWidget):
    def __init__(self, player, overlay, prefs, store, font_library=None):
        super().__init__()
        self.player, self.overlay = player, overlay
        self.external = getattr(player, "is_external", False)
        self.prefs, self.store = prefs, store
        state = Path(store.store.fileName())
        self.presets = PresetStore(state.parent / ("smoke-effect-presets.json" if state.name.startswith("smoke-") else "effect-presets.json"))
        self._preset_id = None
        self._preset_modified = False
        self.font_library = font_library or FontLibrary(Path(store.store.fileName()).parent / "fonts")
        self.prefs.font_family, self._font_message = self.font_library.restore_family(prefs.font_family)
        self._updating = False
        self._shown_tray_hint = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon(prefs.theme))
        self.setStyleSheet(theme_stylesheet(prefs.theme))
        self.setPalette(theme_palette(prefs.theme))
        self.resize(1100, 760)
        self.setMinimumSize(900, 560)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._build_sidebar())
        main = ThemeCanvas()
        main_body = QVBoxLayout(main)
        main_body.setContentsMargins(32, 28, 32, 22)
        main_body.setSpacing(14)
        self.notice = label("", "notice")
        self.notice.setMaximumHeight(96)
        self.notice.hide()
        main_body.addWidget(self.notice)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_music_page())
        self.pages.addWidget(self._build_effects_page())
        main_body.addWidget(self.pages, 1)
        shell.addWidget(main, 1)
        root.addLayout(shell, 1)
        root.addWidget(self._build_player_bar())
        self._select_page(0)
        self._setup_tray()
        self._apply_theme()
        if self.external:
            for widget in (self.import_button, self.lyrics_button, self.demo_button,
                           self.volume_slider, self.volume_label, self.volume_icon, self.play_button):
                widget.hide()
            self.external_transport.show()
            self.progress.display_only = True
            self.music_hint.setText("在网易云中选择歌曲，这里负责桌面歌词效果。")
            self.player.document_changed.connect(self._external_document)
            self.lyric_label.setText("网易云播放歌曲后，自动同步歌词，无需选择本地文件。")
            self.progress.setToolTip("当前网易云进度；请在网易云中拖动进度。")
        self.player.set_volume(prefs.volume)
        player.changed.connect(self._refresh_state)
        player.error.connect(self.show_notice)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(100)
        self.refresh_timer.timeout.connect(self._refresh_position)
        self.refresh_timer.start()
        self._refresh_state()
        if self.presets.error:
            self.show_notice(self.presets.error)

    def _build_sidebar(self):
        self.sidebar = ThemeFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)
        body = QVBoxLayout(self.sidebar)
        body.setContentsMargins(16, 20, 16, 14)
        body.setSpacing(6)
        brand = QHBoxLayout()
        brand.setSpacing(8)
        icon = self.brand_icon = QLabel()
        icon.setPixmap(app_icon(self.prefs.theme).pixmap(36, 36))
        icon.setFixedSize(36, 36)
        brand.addWidget(icon)
        brand.addWidget(label(APP_NAME, "brand"))
        body.addLayout(brand)
        self.creator_label = label(CREATOR.replace("：", "：\n", 1), "creator")
        self.version_label = label(f"版本 {APP_VERSION}", "version")
        body.addWidget(self.creator_label)
        body.addWidget(self.version_label)
        body.addSpacing(20)
        self.navigation = QButtonGroup(self)
        self.navigation.setExclusive(True)
        self.nav_buttons = []
        for index, text in enumerate(("当前音乐", "歌词效果")):
            button = QPushButton(text)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setIconSize(QSize(20, 20))
            button.clicked.connect(lambda _checked=False, page=index: self._select_page(page))
            self.navigation.addButton(button, index)
            self.nav_buttons.append(button)
            body.addWidget(button)
        body.addStretch(1)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("默认主题", "light")
        self.theme_combo.addItem("深色主题", "dark")
        self.theme_combo.addItem("特殊主题", "special")
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.prefs.theme))
        self.theme_combo.setAccessibleName("界面主题")
        self.theme_combo.setToolTip("切换控制面板主题，自动保存。")
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        body.addWidget(self.theme_combo)
        self.motto_label = label(MOTTO.replace(". SAVE", ".\nSAVE"), "motto")
        body.addWidget(self.motto_label)
        body.addSpacing(10)
        self.tray_button = QPushButton("收起到托盘")
        self.tray_button.setObjectName("quiet")
        self.tray_button.setIcon(symbol_icon("tray"))
        self.tray_button.clicked.connect(self.hide)
        body.addWidget(self.tray_button)
        self.exit_button = QPushButton("退出")
        self.exit_button.setObjectName("quiet")
        self.exit_button.setIcon(symbol_icon("exit"))
        self.exit_button.clicked.connect(QApplication.instance().quit)
        body.addWidget(self.exit_button)
        return self.sidebar

    def _select_page(self, index):
        self.pages.setCurrentIndex(index)
        for page, button in enumerate(self.nav_buttons):
            button.setChecked(page == index)
            button.setIcon(symbol_icon("music" if page == 0 else "wave",
                                       ("#ffcd64" if self.prefs.theme == "special" else "#ffffff")
                                       if page == index else theme_colors(self.prefs.theme)["muted"]))

    def _theme_changed(self):
        self.prefs.theme = self.theme_combo.currentData()
        self._apply_theme()
        self.store.save(self.prefs)

    def _apply_theme(self):
        style, palette = theme_stylesheet(self.prefs.theme), theme_palette(self.prefs.theme)
        self.setProperty("interfaceTheme", self.prefs.theme)
        self.setPalette(palette)
        self.setStyleSheet(style)
        icon = app_icon(self.prefs.theme)
        self.setWindowIcon(icon)
        QApplication.instance().setWindowIcon(icon)
        self.tray.setIcon(icon)
        self.brand_icon.setPixmap(icon.pixmap(36, 36))
        self.tray_menu.setPalette(palette)
        self.tray_menu.setStyleSheet(style)
        color = theme_colors(self.prefs.theme)["muted"]
        for button, kind in ((self.tray_button, "tray"), (self.exit_button, "exit"),
                             (self.lyrics_button, "lyrics"), (self.demo_button, "play"),
                             (self.visibility_button, "lyrics")):
            button.setIcon(symbol_icon(kind, color))
        self.volume_icon.setPixmap(symbol_icon("volume", color).pixmap(20, 20))
        self.import_button.setIcon(symbol_icon("import", accent_text(self.prefs.theme)))
        self.play_button.setIcon(symbol_icon("pause" if self.player.playing else "play", accent_text(self.prefs.theme)))
        self._select_page(self.pages.currentIndex())

    @staticmethod
    def _scroll_page():
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = ThemeCanvas()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 8, 0)
        body.setSpacing(20)
        scroll.setWidget(content)
        return scroll, body

    def _build_music_page(self):
        scroll, body = self._scroll_page()
        self.music_scroll = scroll
        body.addWidget(label("DESKTOP LYRICS", "eyebrow"))
        heading = QHBoxLayout()
        heading.addWidget(label("当前音乐", "heading"), 1)
        self.playback_status = label("等待音乐", "badge")
        heading.addWidget(self.playback_status)
        body.addLayout(heading)
        self.music_hint = label("选一首喜欢的歌，为今天的工作添一点节奏。", "muted")
        body.addWidget(self.music_hint)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        self.import_button = QPushButton("导入音乐")
        self.import_button.setObjectName("primary")
        self.import_button.setIcon(symbol_icon("import", "#ffffff"))
        self.import_button.clicked.connect(self.choose_music)
        self.lyrics_button = QPushButton("选择歌词")
        self.lyrics_button.setIcon(symbol_icon("lyrics"))
        self.lyrics_button.clicked.connect(self.choose_lyrics)
        self.demo_button = QPushButton("试听内置演示")
        self.demo_button.setIcon(symbol_icon("play"))
        self.demo_button.clicked.connect(self.play_demo)
        toolbar.addWidget(self.import_button)
        toolbar.addWidget(self.lyrics_button)
        toolbar.addWidget(self.demo_button)
        toolbar.addStretch(1)
        body.addLayout(toolbar)
        columns = QHBoxLayout()
        columns.setContentsMargins(20, 8, 20, 0)
        number = label("#", "muted")
        number.setFixedWidth(30)
        columns.addWidget(number)
        columns.addWidget(label("标题", "muted"), 1)
        for text, width in (("格式", 64), ("时长", 58)):
            heading_label = label(text, "muted")
            heading_label.setFixedWidth(width)
            columns.addWidget(heading_label)
        body.addLayout(columns)
        self.song_row = ThemeFrame()
        self.song_row.setObjectName("songRow")
        song_body = QHBoxLayout(self.song_row)
        song_body.setContentsMargins(20, 22, 20, 22)
        song_body.setSpacing(12)
        self.track_number = label("—", "muted")
        self.track_number.setFixedWidth(30)
        song_body.addWidget(self.track_number)
        title_body = QVBoxLayout()
        title_body.setSpacing(6)
        self.song_label = ElidedLabel("还没有选择歌曲", "song")
        self.source_label = ElidedLabel("导入本地音乐，或试听内置演示。", "muted")
        title_body.addWidget(self.song_label)
        title_body.addWidget(self.source_label)
        song_body.addLayout(title_body, 1)
        self.format_label = label("—", "muted")
        self.format_label.setFixedWidth(64)
        self.track_duration = label("—", "muted")
        self.track_duration.setFixedWidth(58)
        song_body.addWidget(self.format_label)
        song_body.addWidget(self.track_duration)
        body.addWidget(self.song_row)
        lyrics, lyrics_body = card("桌面歌词")
        self.lyric_label = label("导入音乐后，自动查找同目录的同名 LRC 歌词。", "muted")
        lyrics_body.addWidget(self.lyric_label)
        self.analysis_label = label("音乐律动将在播放后开启。", "muted")
        lyrics_body.addWidget(self.analysis_label)
        body.addWidget(lyrics)
        body.addWidget(label("歌词层透明、鼠标穿透，继续点击与输入就好。", "muted"))
        body.addStretch(1)
        return scroll

    def _build_effects_page(self):
        scroll, body = self._scroll_page()
        self.effects_scroll = scroll
        body.addWidget(label("LYRIC EFFECTS", "eyebrow"))
        body.addWidget(label("歌词效果", "heading"))
        body.addWidget(label("调整文字与律动，让歌词融入你的桌面。设置会自动保存。", "muted"))
        preset_card, preset_body = card("效果预设")
        self.preset_combo = QComboBox()
        self.preset_combo.setAccessibleName("效果预设")
        self.preset_combo.currentIndexChanged.connect(lambda _: self.apply_preset(self.preset_combo.currentData()))
        preset_body.addWidget(self.preset_combo)
        preset_actions = QHBoxLayout()
        self.preset_save_button = QPushButton("另存为预设")
        self.preset_update_button = QPushButton("更新当前预设")
        self.preset_delete_button = QPushButton("删除")
        self.preset_save_button.clicked.connect(lambda: self.save_preset())
        self.preset_update_button.clicked.connect(self.update_preset)
        self.preset_delete_button.clicked.connect(self.delete_preset)
        for button in (self.preset_save_button, self.preset_update_button, self.preset_delete_button):
            preset_actions.addWidget(button)
        preset_body.addLayout(preset_actions)
        self.preset_status = label("内置方案只读；可另存为自己的方案。", "muted")
        self.preset_status.setWordWrap(True)
        preset_body.addWidget(self.preset_status)
        body.addWidget(preset_card)
        self._reload_presets()
        self.region = QComboBox()
        self.region.addItem("屏幕两侧 · 避开中央工作区", "edges")
        self.region.addItem("屏幕内自由出现", "full")
        self.region.setCurrentIndex(self.region.findData(self.prefs.region))
        self.region.currentIndexChanged.connect(lambda _: self._set_preference("region", self.region.currentData()))
        self.motion = QComboBox()
        self.motion.addItem("跟随音乐强弱", "audio")
        self.motion.addItem("轻波浪", "wave")
        self.motion.setCurrentIndex(self.motion.findData(self.prefs.motion))
        self.motion.currentIndexChanged.connect(lambda _: self._set_preference("motion", self.motion.currentData()))
        self.animation_combo = QComboBox()
        for value, text in ANIMATION_STYLES.items():
            self.animation_combo.addItem(text, value)
        self.animation_combo.setCurrentIndex(self.animation_combo.findData(self.prefs.animation_style))
        self.animation_combo.setAccessibleName("歌词动画")
        self.animation_combo.currentIndexChanged.connect(lambda _: self._set_preference("animation_style", self.animation_combo.currentData()))
        self.singing_checkbox = QCheckBox("开启逐字演唱强调")
        self.singing_checkbox.setChecked(self.prefs.singing_sync)
        self.singing_checkbox.setAccessibleName("逐字演唱同步")
        self.singing_checkbox.toggled.connect(lambda value: self._set_preference("singing_sync", value))
        self.word_status = label("等待歌词", "muted")
        self.word_status.setWordWrap(True)
        self.spins = {}
        for name, minimum, maximum, suffix in (
            ("font_size", 18, 64, " px"), ("jump", 0, 30, " px"),
            ("angle", 0, 25, " °"), ("opacity", 10, 100, " %"),
            ("delay_ms", -10000, 10000, " ms"),
        ):
            spin = QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setValue(getattr(self.prefs, name))
            spin.setSuffix(suffix)
            spin.setSingleStep(100 if name == "delay_ms" else 1)
            spin.valueChanged.connect(lambda value, key=name: self._set_preference(key, value))
            self.spins[name] = spin
        self.parameter_fields = {}
        self.parameter_sliders = {}
        for name, low, high, suffix in (("entry_speed", 25, 300, " %"), ("exit_speed", 25, 300, " %"),
                                        ("shake_frequency", 1, 15, " 次/秒"), ("fall_distance", 0, 128, " px")):
            spin = QSpinBox()
            spin.setRange(low, high)
            spin.setSuffix(suffix)
            spin.setValue(getattr(self.prefs, name))
            spin.setSingleStep(5 if name.endswith("speed") else 1)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(low, high)
            slider.setValue(spin.value())
            field = QWidget()
            row = QHBoxLayout(field)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(slider, 1)
            row.addWidget(spin)
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            spin.valueChanged.connect(lambda value, key=name: self._set_preference(key, value))
            self.spins[name] = spin
            self.parameter_fields[name], self.parameter_sliders[name] = field, slider
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self.choose_color)
        self._update_color_button()
        self.text_style = QComboBox()
        self.text_style.addItem("白芯发光", "glow")
        self.text_style.addItem("经典纯色", "solid")
        self.text_style.setCurrentIndex(self.text_style.findData(self.prefs.text_style))
        self.text_style.currentIndexChanged.connect(lambda _: self._set_preference("text_style", self.text_style.currentData()))
        self.glow_slider = QSlider(Qt.Orientation.Horizontal)
        self.glow_slider.setRange(0, 100)
        self.glow_slider.setValue(self.prefs.glow_strength)
        self.glow_slider.setAccessibleName("发光强度")
        self.glow_value = label(f"{self.prefs.glow_strength}%", "muted")
        self.glow_field = QWidget()
        glow_row = QHBoxLayout(self.glow_field)
        glow_row.setContentsMargins(0, 0, 0, 0)
        glow_row.addWidget(self.glow_slider, 1)
        glow_row.addWidget(self.glow_value)
        self.glow_slider.valueChanged.connect(lambda value: self._set_preference("glow_strength", value))
        self.color_label = label("描边颜色")
        self.white_hint = label("字芯固定白色，描边与光晕使用所选颜色。", "muted")
        self.white_hint.setWordWrap(True)
        font_field = QWidget()
        font_row = QHBoxLayout(font_field)
        font_row.setContentsMargins(0, 0, 0, 0)
        font_row.setSpacing(8)
        self.font_combo = QComboBox()
        self.font_combo.setMinimumWidth(100)
        self.font_combo.setAccessibleName("歌词字体")
        self.import_font_button = QPushButton("导入字体")
        self.import_font_button.setToolTip("导入 TTF、OTF 或 TTC 字体；字体会保存到程序设置目录。")
        self.import_font_button.clicked.connect(lambda: self.import_font())
        font_row.addWidget(self.font_combo, 1)
        font_row.addWidget(self.import_font_button)
        self.font_preview = FontPreview(self.prefs)
        self.replay_button = QPushButton("重播动画")
        self.replay_button.setToolTip("循环预览入场、停留和退场，不改变音乐播放。")
        self.replay_button.clicked.connect(self.font_preview.replay)
        self.preview_background = QComboBox()
        self.preview_background.addItem("深色背景", True)
        self.preview_background.addItem("浅色背景", False)
        self.preview_background.currentIndexChanged.connect(lambda _: self.font_preview.set_background(self.preview_background.currentData()))
        self.font_status = label(self._font_message or ("部分导入字体无法加载，可重新导入。" if self.font_library.errors else
                                 "支持 TTF、OTF、TTC；选择后立即生效并自动保存。"), "muted")
        self.font_status.setWordWrap(True)
        self._reload_fonts()
        self.font_combo.currentIndexChanged.connect(self._font_selected)
        for title, fields in (
            ("显示与文字", (("显示区域", self.region), ("歌词字体", font_field), ("文字样式", self.text_style),
                          ("文字大小", self.spins["font_size"]),
                          (self.color_label, self.color_button), ("发光强度", self.glow_field),
                          ("歌词透明度", self.spins["opacity"]))),
            ("律动与同步", (("歌词动画", self.animation_combo),
                          ("入场速度", self.parameter_fields["entry_speed"]), ("退场速度", self.parameter_fields["exit_speed"]),
                          ("抖动频率", self.parameter_fields["shake_frequency"]), ("跌落距离（32px 字号）", self.parameter_fields["fall_distance"]),
                          ("预览背景", self.preview_background), ("效果预览", self.font_preview), ("动画预览", self.replay_button),
                          ("逐字演唱同步", self.singing_checkbox), ("歌曲逐字时间", self.word_status),
                          ("运动方式", self.motion), ("律动幅度", self.spins["jump"]),
                          ("倾斜范围", self.spins["angle"]), ("同步偏移", self.spins["delay_ms"]))),
        ):
            section, section_body = card(title)
            form = QFormLayout()
            form.setHorizontalSpacing(24)
            form.setVerticalSpacing(16)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for text, widget in fields:
                widget.setMaximumWidth(460)
                form.addRow(text, widget)
            section_body.addLayout(form)
            if title == "显示与文字":
                section_body.addWidget(self.white_hint)
                section_body.addWidget(self.font_status)
            if title == "律动与同步":
                singing_hint = label("预览使用中英文演示时间；歌曲需提供真实逐字时间，无数据时保留原动画。", "muted")
                singing_hint.setWordWrap(True)
                section_body.addWidget(singing_hint)
                hint = label("速度 100% 为原有效果；数值越高越快。短句会自动压缩动画时长。", "muted")
                hint.setWordWrap(True)
                section_body.addWidget(hint)
                section_body.addWidget(label("偏移为正：歌词晚一点出现；为负：早一点出现。", "muted"))
            body.addWidget(section)
        body.addStretch(1)
        self._update_effect_controls()
        return scroll

    def _build_player_bar(self):
        self.player_bar = ThemeFrame()
        self.player_bar.setObjectName("playerBar")
        body = QVBoxLayout(self.player_bar)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.progress = ThinSlider(Qt.Orientation.Horizontal)
        self.progress.setObjectName("progress")
        self.progress.setFixedHeight(12)
        self.progress.setRange(0, 0)
        self.progress.setEnabled(False)
        self.progress.setAccessibleName("播放进度")
        self.progress.sliderReleased.connect(lambda: self.player.seek(self.progress.value()))
        self.progress.valueChanged.connect(self._progress_changed)
        body.addWidget(self.progress)
        row = QHBoxLayout()
        row.setContentsMargins(24, 10, 24, 16)
        row.setSpacing(20)
        track = QWidget()
        track.setObjectName("footerGroup")
        track_body = QHBoxLayout(track)
        track_body.setContentsMargins(0, 0, 0, 0)
        track_body.setSpacing(12)
        cover = QLabel()
        cover.setPixmap(record_pixmap().scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
        cover.setFixedSize(56, 56)
        track_body.addWidget(cover)
        titles = QVBoxLayout()
        titles.setSpacing(5)
        self.footer_song = ElidedLabel("等待音乐", "footerSong")
        self.footer_detail = ElidedLabel(MOTTO, "muted")
        titles.addWidget(self.footer_song)
        titles.addWidget(self.footer_detail)
        track_body.addLayout(titles, 1)
        row.addWidget(track, 1)
        transport = QVBoxLayout()
        transport.setSpacing(4)
        self.play_button = QPushButton()
        self.play_button.setObjectName("playRound")
        self.play_button.setFixedSize(52, 52)
        self.play_button.setIconSize(QSize(26, 26))
        self.play_button.clicked.connect(self.player.toggle)
        transport.addWidget(self.play_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.external_transport = label("网易云播放", "muted")
        self.external_transport.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.external_transport.hide()
        transport.addWidget(self.external_transport)
        time_row = QHBoxLayout()
        time_row.setSpacing(4)
        self.elapsed_label = label("00:00", "muted")
        self.duration_label = label("00:00", "muted")
        for item in (self.elapsed_label, self.duration_label):
            item.setWordWrap(False)
        time_row.addWidget(self.elapsed_label)
        time_row.addWidget(label("/", "muted"))
        time_row.addWidget(self.duration_label)
        transport.addLayout(time_row)
        row.addLayout(transport)
        controls = QWidget()
        controls.setObjectName("footerGroup")
        control_body = QHBoxLayout(controls)
        control_body.setContentsMargins(0, 0, 0, 0)
        control_body.setSpacing(12)
        control_body.addStretch(1)
        self.visibility_button = QPushButton("隐藏歌词")
        self.visibility_button.setObjectName("visibility")
        self.visibility_button.setIcon(symbol_icon("lyrics"))
        self.visibility_button.clicked.connect(self.toggle_overlay)
        control_body.addWidget(self.visibility_button)
        volume_icon = QLabel()
        self.volume_icon = volume_icon
        volume_icon.setPixmap(symbol_icon("volume").pixmap(20, 20))
        volume_icon.setFixedSize(20, 20)
        control_body.addWidget(volume_icon)
        self.volume_slider = ThinSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.prefs.volume)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setAccessibleName("音量")
        self.volume_slider.valueChanged.connect(self._volume_changed)
        control_body.addWidget(self.volume_slider)
        self.volume_label = label(f"{self.prefs.volume}%", "muted")
        self.volume_label.setFixedWidth(36)
        self.volume_label.setWordWrap(False)
        control_body.addWidget(self.volume_label)
        row.addWidget(controls, 1)
        body.addLayout(row)
        self.player_bar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return self.player_bar

    def fit_to_screen(self, available: QRect):
        # Reserve room for native borders/title bar in Qt logical coordinates.
        width, height = max(1, available.width() - 48), max(1, available.height() - 64)
        self.setMinimumSize(min(900, width), min(560, height))
        self.resize(min(1100, width), min(760, height))
        self.move(available.x() + (available.width() - self.width()) // 2, available.y() + 24)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()
        open_action = QAction("打开控制面板", self)
        open_action.triggered.connect(self.show_panel)
        self.tray_play = QAction("播放 / 暂停", self)
        self.tray_play.triggered.connect(self.player.toggle)
        self.tray_visibility = QAction("隐藏歌词", self)
        self.tray_visibility.triggered.connect(self.toggle_overlay)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(open_action)
        menu.addAction(self.tray_play)
        menu.addAction(self.tray_visibility)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_button.setEnabled(self.tray_available)
        if self.tray_available:
            self.tray.show()
        else:
            self.tray_button.setToolTip("当前系统没有可用托盘，请保留控制面板。")

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_panel()

    def show_panel(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if sys.platform == "win32" and QApplication.instance().platformName() == "windows":
            # A background launcher can supply SW_HIDE in STARTUPINFO. Qt may
            # consider the first show successful while Windows keeps it hidden.
            user = ctypes.windll.user32
            user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user.BringWindowToTop.argtypes = [wintypes.HWND]
            user.SetForegroundWindow.argtypes = [wintypes.HWND]
            user.IsWindowVisible.argtypes = [wintypes.HWND]
            hwnd = int(self.winId())
            user.ShowWindow(hwnd, 9)  # SW_RESTORE also handles a minimized panel.
            user.BringWindowToTop(hwnd)
            user.SetForegroundWindow(hwnd)
            logging.info("Control panel opened; native visible=%s; page=%s",
                         bool(user.IsWindowVisible(hwnd)), self.pages.currentIndex())

    def show_effects(self):
        self._select_page(1)
        self.show_panel()

    def closeEvent(self, event):
        if self.tray_available:
            event.ignore()
            self.hide()
            if not self._shown_tray_hint:
                self.tray.showMessage("都市回响", "已收起到托盘。右键托盘图标可以退出。")
                self._shown_tray_hint = True
        else:
            QApplication.instance().quit()

    def show_notice(self, text: str):
        self.notice.setText(text)
        self.notice.setToolTip(text)
        self.notice.setVisible(bool(text))

    def _external_document(self, document):
        self.overlay.set_document(document)
        self._refresh_word_status()
        self.lyric_label.setText(f"网易云歌词已同步 · {len(document.lines)} 句" if document else
                                "等待网易云歌词；纯音乐或暂无歌词时保持空白。")

    def set_overlay_visible(self, visible):
        # Do not repeat show() every progress packet; preserve native focus behavior.
        if self.overlay.isVisible() != visible:
            self.toggle_overlay()

    def choose_music(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择本地音乐", "", "音乐文件 (*.mp3 *.wav *.flac *.m4a *.ogg);;所有文件 (*)")
        if path:
            self.open_music(path)

    def _set_song_title(self, title, path):
        for item in (self.song_label, self.footer_song):
            item.setText(title)
            item.setToolTip(str(path))

    def open_music(self, path: str | Path):
        self.show_notice("")
        try:
            self.player.load(path)
        except (OSError, ValueError) as error:
            self.show_notice(str(error))
            return
        self.overlay.set_document(None)
        path = Path(path)
        self._set_song_title(path.stem, path)
        self.track_number.setText("01")
        self.source_label.setText(path.name)
        self.source_label.setToolTip(str(path))
        self.format_label.setText(path.suffix.lstrip(".").upper() or "音频")
        self.footer_detail.setText(f"{self.format_label.text()} · 桌面音乐伴侣")
        self.lyric_label.setToolTip("")
        self.lyric_label.setText("未找到同名 LRC。点击“选择歌词”手动导入。")
        matching = path.with_suffix(".lrc")
        if matching.is_file():
            self.open_lyrics(matching)
        self._refresh_state()

    def choose_lyrics(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 LRC 歌词", "", "LRC 歌词 (*.lrc);;所有文件 (*)")
        if path:
            self.open_lyrics(path)

    def open_lyrics(self, path: str | Path):
        try:
            document = load_lrc(path)
        except (OSError, ValueError) as error:
            self.show_notice(f"歌词读取失败：{error}")
            return
        self.overlay.set_document(document)
        count = sum(bool(line.text) for line in document.lines)
        self._refresh_word_status()
        self.lyric_label.setText(f"{Path(path).name}  ·  {count} 句歌词已就绪")
        self.lyric_label.setToolTip(str(path))
        self.show_notice(f"已跳过 {len(document.warnings)} 个错误标签或行。" if document.warnings else "")
        if document.warnings:
            self.notice.setToolTip("\n".join(document.warnings))

    def play_demo(self):
        self.open_music(resource_path("assets/demo.wav"))
        if self.player.path:
            self._set_song_title("轻松节奏 · 合成演示", self.player.path)
            self.player.media.play()

    def toggle_overlay(self):
        self.overlay.setVisible(not self.overlay.isVisible())
        text = "隐藏歌词" if self.overlay.isVisible() else "显示歌词"
        self.visibility_button.setText(text)
        self.tray_visibility.setText(text)

    def _volume_changed(self, value):
        self.prefs.volume = value
        self.player.set_volume(value)
        self.volume_label.setText(f"{value}%")
        self.store.save(self.prefs)

    def _set_preference(self, key, value):
        setattr(self.prefs, key, value)
        if key in EFFECT_KEYS and self._preset_id:
            self._preset_modified = True
            self._reload_presets()
        self.store.save(self.prefs)
        self.overlay.refresh_preferences()
        self._update_effect_controls()
        self.font_preview.update()
        if key in ("animation_style", "entry_speed", "exit_speed", "shake_frequency", "fall_distance", "singing_sync"):
            self.font_preview.replay()

    def _update_effect_controls(self):
        glowing = self.prefs.text_style == "glow"
        self.color_label.setText("描边颜色" if glowing else "文字颜色")
        self.color_button.setToolTip("选择描边和光晕颜色" if glowing else "选择文字填充颜色")
        self.white_hint.setVisible(glowing)
        self.glow_slider.setEnabled(glowing)
        self.glow_value.setText(f"{self.prefs.glow_strength}%")
        self.parameter_fields["shake_frequency"].setEnabled(self.prefs.animation_style.endswith("_shake"))
        self.parameter_fields["fall_distance"].setEnabled(self.prefs.animation_style.startswith("fall_"))
        self._refresh_word_status()

    def _refresh_word_status(self):
        waiting = not getattr(self.player, "lyrics_received", False) if self.external else self.player.path is None
        self.word_status.setText(word_timing_status(self.overlay.document, waiting))

    def _reload_presets(self):
        blocker = QSignalBlocker(self.preset_combo)
        self.preset_combo.clear()
        self.preset_combo.addItem("当前自定义", None)
        for preset in self.presets.all():
            suffix = " · 已修改" if preset.id == self._preset_id and self._preset_modified else ""
            self.preset_combo.addItem(preset.name + suffix, preset.id)
        self.preset_combo.setCurrentIndex(max(0, self.preset_combo.findData(self._preset_id)))
        selected = self.presets.get(self._preset_id)
        editable = selected is not None and not selected.builtin
        self.preset_update_button.setEnabled(editable)
        self.preset_delete_button.setEnabled(editable)
        self.preset_status.setText("已修改，方案未被覆盖；可更新当前预设或另存。" if self._preset_modified and editable else
            "已修改，内置方案保持原样；可另存为自己的方案。" if self._preset_modified else
            "内置方案只读；可另存为自己的方案。" if selected is None or selected.builtin else "自己的方案，可更新或删除。")

    def _sync_effect_widgets(self):
        widgets = [self.animation_combo, self.text_style, self.motion, self.font_combo, self.glow_slider,
                   self.singing_checkbox, self.theme_combo,
                   *self.spins.values(), *self.parameter_sliders.values()]
        blockers = [QSignalBlocker(widget) for widget in widgets]
        for widget, key in ((self.animation_combo, "animation_style"), (self.text_style, "text_style"), (self.motion, "motion")):
            widget.setCurrentIndex(widget.findData(getattr(self.prefs, key)))
        for key, spin in self.spins.items():
            spin.setValue(getattr(self.prefs, key))
        for key, slider in self.parameter_sliders.items():
            slider.setValue(getattr(self.prefs, key))
        self.glow_slider.setValue(self.prefs.glow_strength)
        self.singing_checkbox.setChecked(self.prefs.singing_sync)
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.prefs.theme))
        if self.styleSheet() != theme_stylesheet(self.prefs.theme):
            self._apply_theme()
        self._reload_fonts()
        self._update_color_button()
        self._update_effect_controls()
        self.font_preview.invalidate()

    def apply_preset(self, identifier):
        preset = self.presets.get(identifier)
        if preset is None:
            self._preset_id, self._preset_modified = None, False
            self._reload_presets()
            return
        for key, value in preset.values.items():
            setattr(self.prefs, key, value)
        requested = self.prefs.font_family
        self.prefs.font_family, message = self.font_library.restore_family(requested)
        self._preset_id, self._preset_modified = identifier, bool(message)
        self._sync_effect_widgets()
        self._reload_presets()
        self.font_status.setText(message or "已切换效果预设，设置已自动保存。")
        self.store.save(self.prefs)
        self.overlay.refresh_preferences()
        self.font_preview.replay()

    def save_preset(self, name=None):
        if name is None:
            name, accepted = QInputDialog.getText(self, "保存效果预设", "方案名称（1–48 个字符）")
            if not accepted:
                return False
        duplicate = self.presets.named(name)
        identifier = None
        if duplicate:
            if duplicate.builtin:
                self.show_notice("内置方案只读，请使用自己的方案名称。")
                return False
            if QMessageBox.question(self, "覆盖方案", f"覆盖“{duplicate.name}”的效果设置？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return False
            identifier = duplicate.id
        try:
            saved = self.presets.save(name, self.prefs, identifier)
        except (OSError, ValueError) as error:
            self.show_notice(str(error))
            return False
        self._preset_id, self._preset_modified = saved.id, False
        self._reload_presets()
        return True

    def update_preset(self):
        selected = self.presets.get(self._preset_id)
        if selected and not selected.builtin:
            return self.save_preset(selected.name)
        return False

    def delete_preset(self):
        selected = self.presets.get(self._preset_id)
        if selected is None or selected.builtin:
            return False
        if QMessageBox.question(self, "删除方案", f"删除“{selected.name}”？当前效果会保留。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        try:
            self.presets.delete(selected.id)
        except (OSError, ValueError) as error:
            self.show_notice(str(error))
            return False
        self._preset_id, self._preset_modified = None, False
        self._reload_presets()
        return True

    def _reload_fonts(self):
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        for choice in self.font_library.choices():
            self.font_combo.addItem(choice.label, choice.family)
            if not choice.available:
                self.font_combo.model().item(self.font_combo.count() - 1).setEnabled(False)
        self.font_combo.setCurrentIndex(self.font_combo.findData(self.prefs.font_family))
        self.font_combo.blockSignals(False)
        self.font_combo.setToolTip(self.prefs.font_family)

    def _font_selected(self, _index):
        family = self.font_combo.currentData()
        if family is not None:
            self._set_preference("font_family", family)
            self.font_combo.setToolTip(family)
            self.font_status.setText("已选择" + self.font_combo.currentText() + "，设置已自动保存。")

    def import_font(self, path=None):
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "导入歌词字体", "", "字体文件 (*.ttf *.otf *.ttc);;所有文件 (*)")
        if not path:
            return False
        try:
            families, added = self.font_library.import_font(Path(path))
        except (OSError, ValueError) as error:
            self.font_status.setText(str(error))
            return False
        self._set_preference("font_family", families[0])
        self.font_preview.invalidate()
        self._reload_fonts()
        self.font_status.setText(("已导入" if added else "该字体已导入") + "，已切换到 " + families[0] + "。")
        return True

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.prefs.color), self, "选择歌词颜色")
        if color.isValid():
            self._set_preference("color", color.name())
            self._update_color_button()

    def _update_color_button(self):
        self.color_button.setText(self.prefs.color.upper() + "  ·  选择颜色")
        swatch = QPixmap(24, 24)
        swatch.fill(Qt.GlobalColor.transparent)
        painter = QPainter(swatch)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.prefs.color))
        painter.setPen(QPen(QColor("#b8c0ce"), 1))
        painter.drawEllipse(2, 2, 20, 20)
        painter.end()
        self.color_button.setIcon(QIcon(swatch))

    def _progress_changed(self, value):
        if not self._updating:
            self.elapsed_label.setText(self._format_time(value))
            if not self.progress.isSliderDown():
                self.player.seek(value)

    @staticmethod
    def _format_time(ms):
        seconds = max(0, int(ms) // 1000)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _refresh_state(self):
        self._refresh_word_status()
        if self.external:
            self.play_button.setEnabled(False)
            self.play_button.setIcon(symbol_icon("pause" if self.player.playing else "play", accent_text(self.prefs.theme)))
            self.play_button.setToolTip("播放、暂停和音量请在网易云中操作。")
            self.play_button.setAccessibleName("由网易云控制播放")
            self.tray_play.setEnabled(False)
            self.tray_play.setText("由网易云控制播放")
            title = self.player.title or "等待网易云播放音乐"
            self._set_song_title(title, "网易云音乐 · " + self.player.artist)
            self.source_label.setText(self.player.artist or "请在网易云中点击“都市回响”启用效果。")
            self.footer_detail.setText(self.player.artist or self.player.status)
            self.format_label.setText("网易云")
            self.track_number.setText("01" if self.player.song_id else "—")
            self.playback_status.setText("播放中" if self.player.playing else "已暂停" if self.player.connected else "未连接")
            self.notice.setText(self.player.status)
            self.notice.show()
            return
        self.play_button.setEnabled(self.player.path is not None)
        action = "暂停音乐" if self.player.playing else "开始播放"
        self.play_button.setIcon(symbol_icon("pause" if self.player.playing else "play", accent_text(self.prefs.theme)))
        self.play_button.setToolTip(action)
        self.play_button.setAccessibleName(action)
        self.tray_play.setEnabled(self.player.path is not None)
        self.tray_play.setText(action)
        self.playback_status.setText("播放中" if self.player.playing else "已暂停" if self.player.path else "等待音乐")

    def _refresh_position(self):
        position = self.player.position()
        self._updating = True
        self.progress.setRange(0, self.player.duration)
        self.progress.setEnabled(self.player.duration > 0 if self.external else self.player.media.isSeekable())
        if not self.progress.isSliderDown():
            self.progress.setValue(int(position))
            self.elapsed_label.setText(self._format_time(position))
        self.duration_label.setText(self._format_time(self.player.duration))
        has_song = bool(self.player.song_id) if self.external else self.player.path is not None
        self.track_duration.setText(self._format_time(self.player.duration) if has_song else "—")
        self._updating = False
        if self.prefs.motion == "wave":
            text = "轻波浪模式 · 暂停音乐时也会停止运动。"
        elif self.player.analysis_error:
            text = "音乐律动暂不可用，可在运动方式中选择“轻波浪”。"
        elif self.player.has_audio_data:
            text = "音乐律动已连接 · 每个字随声音强弱轻轻起伏。"
        elif self.player.playing and position > 1500:
            text = "未检测到音乐律动，可在运动方式中选择“轻波浪”。"
        else:
            text = "音乐律动将在播放后开启。"
        self.analysis_label.setText(text)
