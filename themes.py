"""Control-panel themes. Lyric materials and preview backgrounds are independent."""
from string import Template
from PySide6.QtGui import QColor, QPalette
from settings import resource_path

THEMES = {
    "light": dict(background="#f7f8fa", text="#293449", sidebar="#f0f3f6", border="#e0e5ed",
                  surface="#ffffff", muted="#7b8597", hover="#f0f2f6", pressed="#e8ecf2",
                  disabled="#a5acb9", disabled_surface="#f0f2f5", nav="#626d80", nav_hover="#e7ecf2",
                  track="#e4e8ee", scroll="#cfd6e1", selection="#ffe6eb", selection_text="#b7213c",
                  notice="#fff3e8", notice_text="#955224", notice_border="#f2dcc4"),
    "dark": dict(background="#171b24", text="#edf1f7", sidebar="#202632", border="#394354",
                 surface="#252d3a", muted="#acb7c9", hover="#303b4c", pressed="#39465b",
                 disabled="#798599", disabled_surface="#222936", nav="#c2ccdc", nav_hover="#303b4c",
                 track="#414d60", scroll="#58667e", selection="#542c3c", selection_text="#ff94a7",
                 notice="#3c2d22", notice_text="#ffd3a8", notice_border="#755038"),
}

STYLE = Template("""
QWidget { background: $background; color: $text; font-family: 'Microsoft YaHei UI'; font-size: 13px; }
QLabel, QCheckBox { background: transparent; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid $muted; border-radius: 3px; background: $surface; }
QCheckBox::indicator:checked { background: #ff3656; border-color: #ff3656; image: url("$checkmark"); }
QFrame#sidebar { background: $sidebar; border-right: 1px solid $border; }
QLabel#brand { font-size: 20px; font-weight: 700; }
QLabel#heading { font-size: 30px; font-weight: 700; }
QLabel#muted, QLabel#eyebrow, QLabel#creator, QLabel#version, QLabel#motto { color: $muted; }
QLabel#creator, QLabel#version { font-size: 11px; }
QLabel#motto { font-size: 12px; }
QLabel#eyebrow { font-size: 11px; letter-spacing: 2px; }
QLabel#section { font-size: 16px; font-weight: 600; }
QLabel#song { font-size: 18px; font-weight: 600; }
QLabel#footerSong { font-size: 16px; }
QLabel#badge { background: $sidebar; color: $muted; border-radius: 12px; padding: 4px 12px; font-size: 12px; }
QLabel#notice { background: $notice; color: $notice_text; border: 1px solid $notice_border; border-radius: 8px; padding: 10px 14px; }
QFrame#card, QFrame#songRow { background: $surface; border: 1px solid $border; border-radius: 14px; }
QPushButton { background: $surface; border: 1px solid $border; border-radius: 10px; padding: 10px 16px; }
QPushButton:hover { background: $hover; border-color: $muted; }
QPushButton:pressed { background: $pressed; }
QPushButton:focus { border: 1px solid #ff3656; }
QPushButton:disabled { color: $disabled; background: $disabled_surface; border-color: $border; }
QPushButton#primary { background: #ff3656; color: #ffffff; border: 1px solid #ff3656; font-weight: 600; }
QPushButton#primary:hover { background: #f42648; }
QPushButton#primary:pressed { background: #de2342; }
QPushButton#nav { background: transparent; color: $nav; border: 1px solid transparent; text-align: left; padding: 12px 14px; font-size: 15px; }
QPushButton#nav:hover { background: $nav_hover; }
QPushButton#nav:checked { background: #ff3656; color: #ffffff; }
QPushButton#nav:checked:hover { background: #f42648; }
QPushButton#nav:focus { border-color: #c62845; }
QPushButton#quiet { background: transparent; color: $muted; border: 1px solid transparent; text-align: left; }
QPushButton#quiet:hover { background: $nav_hover; }
QPushButton#quiet:focus { border-color: #ff3656; }
QFrame#playerBar { background: $surface; border-top: 1px solid $border; }
QWidget#footerGroup { background: transparent; }
QPushButton#playRound { background: #ff3656; border: 1px solid #ff3656; border-radius: 26px; padding: 0; }
QPushButton#playRound:hover { background: #f42648; }
QPushButton#playRound:pressed { background: #de2342; }
QPushButton#playRound:focus { border: 2px solid #ad1833; }
QPushButton#playRound:disabled { background: $disabled_surface; border-color: $border; }
QPushButton#visibility { background: $surface; border: 1px solid $border; padding: 7px 10px; font-size: 12px; }
QPushButton#visibility:hover { background: $hover; }
QComboBox, QSpinBox { background: $surface; border: 1px solid $border; border-radius: 8px; padding: 7px 10px; min-height: 22px; }
QComboBox:focus, QSpinBox:focus { border-color: #ff3656; }
QComboBox:disabled, QSpinBox:disabled { color: $disabled; background: $disabled_surface; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: $surface; color: $text; selection-background-color: $selection; selection-color: $selection_text; }
QSpinBox::up-button, QSpinBox::down-button { width: 20px; }
QSlider { background: transparent; }
QSlider::groove:horizontal, QSlider::add-page:horizontal { height: 4px; background: $track; border: none; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ff3656; border: none; border-radius: 2px; }
QSlider::handle:horizontal { background: #ff3656; width: 12px; margin: -4px 0; border-radius: 6px; }
QSlider:disabled::sub-page:horizontal { background: $track; }
QSlider#progress::groove:horizontal { height: 3px; }
QSlider#progress::handle:horizontal { width: 8px; margin: -3px 0; border-radius: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: $background; width: 8px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: $surface; color: $text; border: 1px solid $border; padding: 6px; }
QMenu::item { padding: 8px 18px; }
QMenu::item:selected { background: $selection; color: $selection_text; }
QMenu::item:disabled { color: $disabled; }
""")


def theme_colors(name):
    return THEMES.get(name, THEMES["light"])


def theme_stylesheet(name):
    return STYLE.substitute(theme_colors(name), checkmark=resource_path("assets/check-white.svg").as_posix())


def theme_palette(name):
    colors = theme_colors(name)
    palette = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "background"), (QPalette.ColorRole.WindowText, "text"),
                      (QPalette.ColorRole.Base, "surface"), (QPalette.ColorRole.AlternateBase, "sidebar"),
                      (QPalette.ColorRole.Text, "text"), (QPalette.ColorRole.Button, "surface"),
                      (QPalette.ColorRole.ButtonText, "text"), (QPalette.ColorRole.Mid, "track"),
                      (QPalette.ColorRole.ToolTipBase, "surface"), (QPalette.ColorRole.ToolTipText, "text")):
        palette.setColor(role, QColor(colors[key]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#ff3656"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["disabled"]))
    return palette
