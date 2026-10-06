from pathlib import Path
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPalette, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QColorDialog, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSizePolicy,
    QSlider, QSpinBox, QStackedWidget, QStyle, QStyleOptionSlider, QSystemTrayIcon, QVBoxLayout, QWidget,
)
from lrc import load_lrc
from settings import resource_path


STYLE = """
QWidget { background: #f7f8fa; color: #293449; font-family: 'Microsoft YaHei UI'; font-size: 13px; }
QLabel { background: transparent; }
QFrame#sidebar { background: #f0f3f6; border-right: 1px solid #e9edf2; }
QLabel#brand { font-size: 20px; font-weight: 700; }
QLabel#heading { font-size: 30px; font-weight: 700; }
QLabel#muted, QLabel#eyebrow { color: #7b8597; }
QLabel#eyebrow { font-size: 11px; letter-spacing: 2px; }
QLabel#section { font-size: 16px; font-weight: 600; }
QLabel#song { font-size: 18px; font-weight: 600; }
QLabel#footerSong { font-size: 16px; }
QLabel#badge { background: #eef1f5; color: #788396; border-radius: 12px; padding: 4px 12px; font-size: 12px; }
QLabel#notice { background: #fff3e8; color: #955224; border: 1px solid #f2dcc4; border-radius: 8px; padding: 10px 14px; }
QFrame#card, QFrame#songRow { background: #ffffff; border: 1px solid #edf0f4; border-radius: 14px; }
QPushButton { background: #ffffff; border: 1px solid #e0e5ed; border-radius: 10px; padding: 10px 16px; }
QPushButton:hover { background: #f0f2f6; border-color: #c9d1df; }
QPushButton:pressed { background: #e8ecf2; }
QPushButton:focus { border: 1px solid #ff3656; }
QPushButton:disabled { color: #a5acb9; background: #f0f2f5; border-color: #e7ebf0; }
QPushButton#primary { background: #ff3656; color: #ffffff; border: 1px solid #ff3656; font-weight: 600; }
QPushButton#primary:hover { background: #f42648; }
QPushButton#primary:pressed { background: #de2342; }
QPushButton#nav { background: transparent; color: #626d80; border: 1px solid transparent; text-align: left; padding: 12px 14px; font-size: 15px; }
QPushButton#nav:hover { background: #e7ecf2; }
QPushButton#nav:checked { background: #ff3656; color: #ffffff; }
QPushButton#nav:checked:hover { background: #f42648; }
QPushButton#nav:focus { border-color: #c62845; }
QPushButton#quiet { background: transparent; color: #6b7688; border: 1px solid transparent; text-align: left; }
QPushButton#quiet:hover { background: #e7ecf2; }
QPushButton#quiet:focus { border-color: #ff3656; }
QFrame#playerBar { background: #ffffff; border-top: 1px solid #e5e9ee; }
QWidget#footerGroup { background: transparent; }
QPushButton#playRound { background: #ff3656; border: 1px solid #ff3656; border-radius: 26px; padding: 0; }
QPushButton#playRound:hover { background: #f42648; }
QPushButton#playRound:pressed { background: #de2342; }
QPushButton#playRound:focus { border: 2px solid #ad1833; }
QPushButton#playRound:disabled { background: #f4b7c2; border-color: #f4b7c2; }
QPushButton#visibility { background: #ffffff; border: 1px solid #e2e7ee; padding: 7px 10px; font-size: 12px; }
QPushButton#visibility:hover { background: #f2f4f8; }
QComboBox, QSpinBox { background: #ffffff; border: 1px solid #dce2eb; border-radius: 8px; padding: 7px 10px; min-height: 22px; }
QComboBox:focus, QSpinBox:focus { border-color: #ff3656; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #ffffff; color: #293449; selection-background-color: #ffe6eb; selection-color: #b7213c; }
QSpinBox::up-button, QSpinBox::down-button { width: 20px; }
QSlider { background: transparent; }
QSlider::groove:horizontal { height: 4px; background: #e4e8ee; border: none; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ff3656; border: none; border-radius: 2px; }
QSlider::add-page:horizontal { background: #e4e8ee; border: none; border-radius: 2px; }
QSlider::handle:horizontal { background: #ff3656; width: 12px; margin: -4px 0; border-radius: 6px; }
QSlider:disabled::sub-page:horizontal { background: #d5dae3; }
QSlider#progress::groove:horizontal { height: 3px; }
QSlider#progress::handle:horizontal { width: 8px; margin: -3px 0; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f7f8fa; width: 8px; }
QScrollBar::handle:vertical { background: #cfd6e1; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: #ffffff; border: 1px solid #dce2eb; padding: 6px; }
QMenu::item { padding: 8px 18px; }
QMenu::item:selected { background: #ffe6eb; color: #b7213c; }
"""


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


def app_icon() -> QIcon:
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
        painter.setBrush(QColor("#e4e8ee"))
        painter.drawRoundedRect(groove, height / 2, height / 2)
        if self.isEnabled() and self.maximum() > self.minimum():
            painter.setBrush(QColor("#ff3656"))
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
                painter.setPen(QPen(QColor("#b7213c"), 1))
                painter.drawEllipse(QPointF(center.x(), self.height() / 2), radius + 2, radius + 2)
        painter.end()


def card(title: str):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(24, 20, 24, 22)
    layout.setSpacing(16)
    layout.addWidget(label(title, "section"))
    return frame, layout


class ControlPanel(QWidget):
    def __init__(self, player, overlay, prefs, store):
        super().__init__()
        self.player, self.overlay = player, overlay
        self.prefs, self.store = prefs, store
        self._updating = False
        self._shown_tray_hint = False
        self.setWindowTitle("跳动的歌词")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(STYLE)
        self.resize(1100, 760)
        self.setMinimumSize(900, 560)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._build_sidebar())
        main = QWidget()
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
        self.player.set_volume(prefs.volume)
        player.changed.connect(self._refresh_state)
        player.error.connect(self.show_notice)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(100)
        self.refresh_timer.timeout.connect(self._refresh_position)
        self.refresh_timer.start()
        self._refresh_state()

    def _build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(200)
        body = QVBoxLayout(self.sidebar)
        body.setContentsMargins(16, 30, 16, 20)
        body.setSpacing(10)
        brand = QHBoxLayout()
        brand.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(36, 36))
        icon.setFixedSize(36, 36)
        brand.addWidget(icon)
        brand.addWidget(label("跳动的歌词", "brand"))
        body.addLayout(brand)
        body.addWidget(label("音乐在耳边，歌词在桌面。", "muted"))
        body.addSpacing(32)
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
        body.addWidget(label("让工作，有一点节奏。", "muted"))
        body.addSpacing(10)
        self.tray_button = QPushButton("收起到托盘")
        self.tray_button.setObjectName("quiet")
        self.tray_button.setIcon(symbol_icon("tray"))
        self.tray_button.clicked.connect(self.hide)
        body.addWidget(self.tray_button)
        quit_button = QPushButton("退出")
        quit_button.setObjectName("quiet")
        quit_button.setIcon(symbol_icon("exit"))
        quit_button.clicked.connect(QApplication.instance().quit)
        body.addWidget(quit_button)
        return self.sidebar

    def _select_page(self, index):
        self.pages.setCurrentIndex(index)
        for page, button in enumerate(self.nav_buttons):
            button.setChecked(page == index)
            button.setIcon(symbol_icon("music" if page == 0 else "wave",
                                       "#ffffff" if page == index else "#7b8597"))

    @staticmethod
    def _scroll_page():
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
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
        body.addWidget(label("选一首喜欢的歌，为今天的工作添一点节奏。", "muted"))
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
        self.song_row = QFrame()
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
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self.choose_color)
        self._update_color_button()
        for title, fields in (
            ("显示与文字", (("显示区域", self.region), ("文字大小", self.spins["font_size"]),
                          ("文字颜色", self.color_button), ("歌词透明度", self.spins["opacity"]))),
            ("律动与同步", (("运动方式", self.motion), ("跳动幅度", self.spins["jump"]),
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
            if title == "律动与同步":
                section_body.addWidget(label("偏移为正：歌词晚一点出现；为负：早一点出现。", "muted"))
            body.addWidget(section)
        body.addStretch(1)
        return scroll

    def _build_player_bar(self):
        self.player_bar = QFrame()
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
        self.footer_detail = ElidedLabel("让工作，有一点节奏。", "muted")
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
        self.tray.setToolTip("跳动的歌词")
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

    def closeEvent(self, event):
        if self.tray_available:
            event.ignore()
            self.hide()
            if not self._shown_tray_hint:
                self.tray.showMessage("跳动的歌词", "已收起到托盘。右键托盘图标可以退出。")
                self._shown_tray_hint = True
        else:
            QApplication.instance().quit()

    def show_notice(self, text: str):
        self.notice.setText(text)
        self.notice.setToolTip(text)
        self.notice.setVisible(bool(text))

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
        self.store.save(self.prefs)
        self.overlay.refresh_preferences()

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
        self.play_button.setEnabled(self.player.path is not None)
        action = "暂停音乐" if self.player.playing else "开始播放"
        self.play_button.setIcon(symbol_icon("pause" if self.player.playing else "play", "#ffffff"))
        self.play_button.setToolTip(action)
        self.play_button.setAccessibleName(action)
        self.tray_play.setEnabled(self.player.path is not None)
        self.tray_play.setText(action)
        self.playback_status.setText("播放中" if self.player.playing else "已暂停" if self.player.path else "等待音乐")

    def _refresh_position(self):
        position = self.player.position()
        self._updating = True
        self.progress.setRange(0, self.player.duration)
        self.progress.setEnabled(self.player.media.isSeekable())
        if not self.progress.isSliderDown():
            self.progress.setValue(int(position))
            self.elapsed_label.setText(self._format_time(position))
        self.duration_label.setText(self._format_time(self.player.duration))
        self.track_duration.setText(self._format_time(self.player.duration) if self.player.path else "—")
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
