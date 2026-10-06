from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSlider,
    QSpinBox, QSystemTrayIcon, QVBoxLayout, QWidget,
)
from lrc import load_lrc
from settings import resource_path


STYLE = """
QWidget { background: #101c20; color: #e5eceb; font-family: 'Microsoft YaHei UI'; font-size: 13px; }
QScrollArea { border: none; }
QFrame#card { background: #17272c; border: 1px solid #2c4147; border-radius: 14px; }
QFrame#card QLabel { background: transparent; }
QLabel#eyebrow { color: #8ad9bd; font-size: 11px; font-weight: 700; }
QLabel#heading { font-size: 29px; font-weight: 700; color: #f1f5ed; }
QLabel#muted { color: #96aeb4; }
QLabel#section { font-size: 15px; font-weight: 700; color: #d2ebe4; }
QLabel#song { font-size: 18px; font-weight: 600; }
QLabel#notice { color: #e1be84; }
QPushButton { background: #24383f; border: 1px solid #354e56; border-radius: 8px; padding: 9px 14px; }
QPushButton:hover { background: #304950; border-color: #71bda5; }
QPushButton:pressed { background: #1b3035; }
QPushButton:disabled { color: #62777d; border-color: #293b40; }
QPushButton#primary { background: #a9edcf; color: #143b31; border: none; font-weight: 700; }
QPushButton#primary:hover { background: #c1f4df; }
QPushButton#primary:disabled { background: #33584d; color: #83a196; }
QPushButton#quiet { background: transparent; border: 1px solid #354e56; }
QComboBox, QSpinBox { background: #1f3339; border: 1px solid #38525a; border-radius: 6px; padding: 6px 10px; min-height: 20px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #1f3339; selection-background-color: #386052; }
QSpinBox::up-button, QSpinBox::down-button { width: 18px; }
QSlider::groove:horizontal { height: 5px; background: #30494f; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #90dabb; border-radius: 2px; }
QSlider::handle:horizontal { background: #c2f5df; width: 13px; margin: -4px 0; border-radius: 6px; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; }
QScrollBar:vertical { background: #101c20; width: 8px; }
QScrollBar::handle:vertical { background: #38525a; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: #17272c; border: 1px solid #38525a; padding: 6px; }
QMenu::item { padding: 8px 18px; }
QMenu::item:selected { background: #304950; }
"""


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#172f34"))
    painter.drawRoundedRect(2, 2, 60, 60, 16, 16)
    painter.setPen(QPen(QColor("#a9edcf"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for x, top, bottom in ((18, 28, 39), (28, 17, 47), (38, 23, 42), (48, 30, 36)):
        painter.drawLine(x, top, x, bottom)
    painter.end()
    return QIcon(pixmap)


def label(text: str, name: str = "") -> QLabel:
    item = QLabel(text)
    item.setObjectName(name)
    item.setWordWrap(True)
    return item


def card(title: str):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 16, 20, 18)
    layout.setSpacing(12)
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
        self.resize(560, 830)
        self.setMinimumSize(490, 540)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(28, 26, 28, 24)
        body.setSpacing(18)
        body.addWidget(label("DESKTOP LYRICS  /  桌面音乐伴侣", "eyebrow"))
        body.addWidget(label("让工作，有一点节奏。", "heading"))
        body.addWidget(label("音乐在耳边，歌词在桌面。", "muted"))

        music, music_body = card("01  选择你的音乐")
        self.song_label = label("还没有选择歌曲", "song")
        self.lyric_label = label("导入本地音乐后，自动查找同名 LRC 歌词。", "muted")
        music_body.addWidget(self.song_label)
        music_body.addWidget(self.lyric_label)
        row = QHBoxLayout()
        import_song = QPushButton("导入音乐")
        import_song.clicked.connect(self.choose_music)
        import_lyric = QPushButton("选择歌词")
        import_lyric.clicked.connect(self.choose_lyrics)
        row.addWidget(import_song)
        row.addWidget(import_lyric)
        music_body.addLayout(row)
        demo = QPushButton("试听内置演示  ·  合成音乐 + 示例歌词")
        demo.setObjectName("quiet")
        demo.clicked.connect(self.play_demo)
        music_body.addWidget(demo)
        self.notice = label("", "notice")
        self.notice.hide()
        music_body.addWidget(self.notice)
        body.addWidget(music)

        playback, playback_body = card("02  跟着音乐，轻轻跳动")
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.setEnabled(False)
        self.progress.sliderReleased.connect(lambda: self.player.seek(self.progress.value()))
        self.progress.valueChanged.connect(self._progress_changed)
        playback_body.addWidget(self.progress)
        time_row = QHBoxLayout()
        self.elapsed_label, self.duration_label = label("00:00", "muted"), label("00:00", "muted")
        self.duration_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_row.addWidget(self.elapsed_label)
        time_row.addWidget(self.duration_label)
        playback_body.addLayout(time_row)
        row = QHBoxLayout()
        self.play_button = QPushButton("开始播放")
        self.play_button.setObjectName("primary")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.player.toggle)
        self.visibility_button = QPushButton("隐藏歌词")
        self.visibility_button.clicked.connect(self.toggle_overlay)
        row.addWidget(self.play_button, 1)
        row.addWidget(self.visibility_button, 1)
        playback_body.addLayout(row)
        volume_row = QHBoxLayout()
        volume_row.addWidget(label("音量", "muted"))
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(prefs.volume)
        self.volume_slider = volume
        self.volume_label = label(f"{prefs.volume}%", "muted")
        self.volume_label.setMinimumWidth(38)
        volume.valueChanged.connect(self._volume_changed)
        volume_row.addWidget(volume, 1)
        volume_row.addWidget(self.volume_label)
        playback_body.addLayout(volume_row)
        self.analysis_label = label("音乐律动将在播放后开启。", "muted")
        playback_body.addWidget(self.analysis_label)
        body.addWidget(playback)

        appearance, appearance_body = card("03  留一点空间给灵感")
        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.region = QComboBox()
        self.region.addItem("屏幕两侧 · 避开中央工作区", "edges")
        self.region.addItem("屏幕内自由出现", "full")
        self.region.setCurrentIndex(self.region.findData(prefs.region))
        self.region.currentIndexChanged.connect(lambda _: self._set_preference("region", self.region.currentData()))
        form.addRow("显示区域", self.region)
        self.motion = QComboBox()
        self.motion.addItem("跟随音乐强弱", "audio")
        self.motion.addItem("轻波浪", "wave")
        self.motion.setCurrentIndex(self.motion.findData(prefs.motion))
        self.motion.currentIndexChanged.connect(lambda _: self._set_preference("motion", self.motion.currentData()))
        form.addRow("运动方式", self.motion)
        self.spins = {}
        for name, title, minimum, maximum, suffix in (
            ("font_size", "文字大小", 18, 64, " px"),
            ("jump", "跳动幅度", 0, 30, " px"),
            ("angle", "倾斜范围", 0, 25, " °"),
            ("opacity", "歌词透明度", 10, 100, " %"),
            ("delay_ms", "同步偏移", -10000, 10000, " ms"),
        ):
            spin = QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setValue(getattr(prefs, name))
            spin.setSuffix(suffix)
            spin.setSingleStep(100 if name == "delay_ms" else 1)
            spin.valueChanged.connect(lambda value, key=name: self._set_preference(key, value))
            self.spins[name] = spin
            form.addRow(title, spin)
        self.color_button = QPushButton("选择颜色")
        self.color_button.clicked.connect(self.choose_color)
        self._update_color_button()
        form.addRow("文字颜色", self.color_button)
        appearance_body.addLayout(form)
        appearance_body.addWidget(label("偏移为正：歌词晚一点出现；为负：早一点出现。", "muted"))
        body.addWidget(appearance)

        footer = QHBoxLayout()
        self.tray_button = QPushButton("收起到托盘")
        self.tray_button.setObjectName("quiet")
        self.tray_button.clicked.connect(self.hide)
        quit_button = QPushButton("退出")
        quit_button.setObjectName("quiet")
        quit_button.clicked.connect(QApplication.instance().quit)
        footer.addWidget(self.tray_button, 1)
        footer.addWidget(quit_button)
        body.addLayout(footer)
        body.addWidget(label("歌词层透明、鼠标穿透，继续点击与输入就好。", "muted"))
        scroll.setWidget(content)
        root.addWidget(scroll)
        self._setup_tray()
        self.player.set_volume(prefs.volume)
        player.changed.connect(self._refresh_state)
        player.error.connect(self.show_notice)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(100)
        self.refresh_timer.timeout.connect(self._refresh_position)
        self.refresh_timer.start()
        self._refresh_state()

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
        self.notice.setVisible(bool(text))

    def choose_music(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择本地音乐", "", "音乐文件 (*.mp3 *.wav *.flac *.m4a *.ogg);;所有文件 (*)")
        if path:
            self.open_music(path)

    def open_music(self, path: str | Path):
        self.overlay.set_document(None)
        self.show_notice("")
        try:
            self.player.load(path)
        except (OSError, ValueError) as error:
            self.show_notice(str(error))
            return
        path = Path(path)
        self.song_label.setText(path.stem)
        self.song_label.setToolTip(str(path))
        matching = path.with_suffix(".lrc")
        if matching.is_file():
            self.open_lyrics(matching)
        else:
            self.lyric_label.setText("未找到同名 LRC。点击“选择歌词”手动导入。")
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
        self.notice.setToolTip("\n".join(document.warnings))

    def play_demo(self):
        self.open_music(resource_path("assets/demo.wav"))
        if self.player.path:
            self.song_label.setText("轻松节奏 · 合成演示")
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
        self.color_button.setStyleSheet(f"color: {self.prefs.color};")

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
        self.play_button.setText("暂停音乐" if self.player.playing else "开始播放")
        self.tray_play.setEnabled(self.player.path is not None)
        self.tray_play.setText("暂停音乐" if self.player.playing else "开始播放")

    def _refresh_position(self):
        position = self.player.position()
        self._updating = True
        self.progress.setRange(0, self.player.duration)
        self.progress.setEnabled(self.player.media.isSeekable())
        if not self.progress.isSliderDown():
            self.progress.setValue(int(position))
            self.elapsed_label.setText(self._format_time(position))
        self.duration_label.setText(self._format_time(self.player.duration))
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
