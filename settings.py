from dataclasses import dataclass, asdict
from pathlib import Path
import sys
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor

DEFAULT_FONT_FAMILY = "Microsoft YaHei UI"
ANIMATION_STYLES = {
    "classic": "原有效果 · 整句渐隐",
    "ripple_wave": "波纹·波动", "ripple_shake": "波纹·抖动",
    "fall_wave": "跌落·波动", "fall_shake": "跌落·抖动",
}


def app_directory() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent


def resource_path(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / name


@dataclass
class Preferences:
    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int = 32
    color: str = "#a9f4dc"
    opacity: int = 80
    jump: int = 10
    angle: int = 12
    region: str = "edges"
    delay_ms: int = 0
    volume: int = 45
    motion: str = "audio"
    text_style: str = "glow"
    glow_strength: int = 60
    animation_style: str = "classic"
    entry_speed: int = 100
    exit_speed: int = 100
    shake_frequency: int = 6
    fall_distance: int = 48
    singing_sync: bool = False
    theme: str = "light"


class SettingsStore:
    def __init__(self, path: Path | None = None):
        target = path or app_directory() / ".state" / "settings.ini"
        target.parent.mkdir(parents=True, exist_ok=True)
        self.store = QSettings(str(target), QSettings.Format.IniFormat)

    def load(self) -> Preferences:
        prefs = Preferences()
        for key, default in asdict(prefs).items():
            value = self.store.value(key, default)
            try:
                if isinstance(default, bool):
                    value = value if isinstance(value, bool) else str(value).lower() in ("true", "1")
                else:
                    value = int(value) if isinstance(default, int) else str(value)
                setattr(prefs, key, value)
            except (ValueError, TypeError):
                pass
        return normalize_preferences(prefs)

    def save(self, prefs: Preferences):
        for key, value in asdict(prefs).items():
            self.store.setValue(key, value)
        self.store.sync()


def normalize_preferences(prefs):
    for key, low, high in (("font_size", 18, 64), ("opacity", 10, 100),
                           ("jump", 0, 30), ("angle", 0, 25),
                           ("delay_ms", -10000, 10000), ("volume", 0, 100), ("glow_strength", 0, 100),
                           ("entry_speed", 25, 300), ("exit_speed", 25, 300),
                           ("shake_frequency", 1, 15), ("fall_distance", 0, 128)):
        setattr(prefs, key, max(low, min(high, getattr(prefs, key))))
    if prefs.region not in ("edges", "full"):
        prefs.region = "edges"
    if prefs.motion not in ("audio", "wave"):
        prefs.motion = "audio"
    if prefs.text_style not in ("glow", "solid"):
        prefs.text_style = "glow"
    if prefs.animation_style not in ANIMATION_STYLES:
        prefs.animation_style = "classic"
    if prefs.theme not in ("light", "dark"):
        prefs.theme = "light"
    if not QColor(prefs.color).isValid():
        prefs.color = "#a9f4dc"
    prefs.font_family = prefs.font_family.strip()
    if not prefs.font_family or len(prefs.font_family) > 256 or any(c in prefs.font_family for c in "\n\r\x00"):
        prefs.font_family = DEFAULT_FONT_FAMILY
    return prefs
