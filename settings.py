from dataclasses import dataclass, asdict
from pathlib import Path
import sys
import json
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor

def default_font_family(platform=None):
    return "PingFang SC" if (platform or sys.platform) == "darwin" else "Microsoft YaHei UI"


DEFAULT_FONT_FAMILY = default_font_family()
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
    kugou_cache_directory: str = ""
    kugou_replace_native: bool = True
    font_family: str = DEFAULT_FONT_FAMILY
    font_size: int = 32
    color: str = "#a9f4dc"
    opacity: int = 80
    jump: int = 10
    motion_strength: int = 100
    angle: int = 12
    region: str = "edges"
    display_screen: str = "primary"
    delay_ms: int = 0
    volume: int = 45
    motion: str = "audio"
    text_style: str = "glow"
    glow_strength: int = 60
    glow_variant: str = "standard"
    gradient_colors: str = '["#ff78bb","#68b6f5"]'
    gradient_direction: str = "horizontal"
    animation_style: str = "classic"
    scramble_exit: bool = False
    entry_speed: int = 100
    exit_speed: int = 100
    shake_frequency: int = 6
    fall_distance: int = 48
    singing_sync: bool = False
    prefer_translation: bool = False
    lyric_display_mode: str = "legacy"
    hide_instrumental: bool = False
    hide_on_pause: bool = False
    max_display_seconds: int = 6
    extended_display: bool = False
    extended_display_seconds: int = 10
    extended_display_limit: int = 4
    theme: str = "light"
    qq_cache_directory: str = ""


class SettingsStore:
    def __init__(self, path: Path | None = None):
        target = path or app_directory() / ".state" / "settings.ini"
        target.parent.mkdir(parents=True, exist_ok=True)
        self.store = QSettings(str(target), QSettings.Format.IniFormat)

    def load(self, *, kugou=False) -> Preferences:
        prefs = Preferences()
        if kugou:
            prefs.motion_strength = 30
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
                           ("jump", 0, 30), ("angle", 0, 25), ("motion_strength", 0, 100),
                           ("delay_ms", -10000, 10000), ("volume", 0, 100), ("glow_strength", 0, 100),
                           ("entry_speed", 25, 300), ("exit_speed", 25, 300),
                           ("shake_frequency", 1, 15), ("fall_distance", 0, 128), ("max_display_seconds", 0, 120),
                           ("extended_display_seconds", 1, 120), ("extended_display_limit", 2, 4)):
        setattr(prefs, key, max(low, min(high, getattr(prefs, key))))
    if prefs.region not in ("edges", "full"):
        prefs.region = "edges"
    if not prefs.display_screen or len(prefs.display_screen) > 1024 or any(c in prefs.display_screen for c in "\x00\n\r"):
        prefs.display_screen = "primary"
    if prefs.motion not in ("audio", "wave"):
        prefs.motion = "audio"
    if prefs.text_style not in ("glow", "solid", "gradient_fill"):
        prefs.text_style = "glow"
    if prefs.glow_variant not in ("standard", "carmen", "gradient"):
        prefs.glow_variant = "standard"
    try:
        colors = json.loads(prefs.gradient_colors)
        if not isinstance(colors, list) or len(colors) not in (2, 3) or not all(
                isinstance(color, str) and len(color) == 7 and color.startswith("#") and QColor(color).isValid() for color in colors):
            raise ValueError()
        prefs.gradient_colors = json.dumps([QColor(color).name() for color in colors], separators=(",", ":"))
    except (ValueError, TypeError):
        prefs.gradient_colors = '["#ff78bb","#68b6f5"]'
    if prefs.gradient_direction not in ("horizontal", "vertical", "diagonal"):
        prefs.gradient_direction = "horizontal"
    if prefs.animation_style not in ANIMATION_STYLES:
        prefs.animation_style = "classic"
    if prefs.lyric_display_mode not in ("legacy", "original", "translation", "bilingual_original", "bilingual_translation"):
        prefs.lyric_display_mode = "legacy"
    if prefs.theme not in ("light", "dark", "special"):
        prefs.theme = "light"
    if not QColor(prefs.color).isValid():
        prefs.color = "#a9f4dc"
    prefs.font_family = prefs.font_family.strip()
    prefs.qq_cache_directory = prefs.qq_cache_directory.strip()
    prefs.kugou_cache_directory = prefs.kugou_cache_directory.strip()
    if len(prefs.kugou_cache_directory) > 4096 or any(c in prefs.kugou_cache_directory for c in "\n\r\x00"):
        prefs.kugou_cache_directory = ""
    if len(prefs.qq_cache_directory)>4096 or any(c in prefs.qq_cache_directory for c in "\n\r\x00"):
        prefs.qq_cache_directory = ""
    if not prefs.font_family or len(prefs.font_family) > 256 or any(c in prefs.font_family for c in "\n\r\x00"):
        prefs.font_family = DEFAULT_FONT_FAMILY
    return prefs


def display_mode(prefs):
    return ("translation" if prefs.prefer_translation else "original") if prefs.lyric_display_mode == "legacy" else prefs.lyric_display_mode
