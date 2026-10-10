"""Curated lyric families and application-owned imports; no system install."""
from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import tempfile
import sys
from PySide6.QtGui import QFont, QFontDatabase
from settings import DEFAULT_FONT_FAMILY

FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
def preset_fonts(platform=None):
    if (platform or sys.platform) == "darwin":
        return (("苹方（默认）", "PingFang SC"), ("宋体", "Songti SC"), ("楷体", "Kaiti SC"))
    return (("微软雅黑（默认）", "Microsoft YaHei UI"), ("宋体", "SimSun"), ("楷体", "KaiTi"))


PRESET_FONTS = preset_fonts()


@dataclass(frozen=True)
class FontChoice:
    label: str
    family: str
    available: bool = True


def lyric_font(family: str, pixels: int) -> QFont:
    font = QFont()
    font.setFamilies(list(dict.fromkeys((family, DEFAULT_FONT_FAMILY))))
    font.setPixelSize(pixels)
    # Keep the original default; other families retain their regular face.
    font.setWeight(QFont.Weight.DemiBold if family == DEFAULT_FONT_FAMILY else QFont.Weight.Normal)
    return font


class FontLibrary:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._system_families = set(QFontDatabase.families())
        self._loaded = {}
        self.errors = []
        if self.directory.is_dir():
            for path in sorted(self.directory.iterdir()):
                if path.is_file() and path.suffix.lower() in FONT_EXTENSIONS:
                    try:
                        self._loaded[path.name] = self._register(path.read_bytes())
                    except (OSError, ValueError) as error:
                        self.errors.append(path.name)
                        logging.warning("Imported font unavailable: %s (%s)", path.name, error)

    @staticmethod
    def _register(data: bytes):
        identifier = QFontDatabase.addApplicationFontFromData(data)
        families = QFontDatabase.applicationFontFamilies(identifier) if identifier >= 0 else []
        families = [name for name in families if name.strip() and not any(c in name for c in "\n\r\x00")]
        if not families:
            if identifier >= 0:
                QFontDatabase.removeApplicationFont(identifier)
            raise ValueError("无法读取字体，请选择有效的 TTF、OTF 或 TTC 字体文件。")
        return identifier, families

    def choices(self):
        imported = sorted({family for _, families in self._loaded.values() for family in families})
        available = self._system_families | set(imported)
        presets = [FontChoice(label if family in available or family == DEFAULT_FONT_FAMILY else label + "（未安装）",
                              family, family in available or family == DEFAULT_FONT_FAMILY)
                   for label, family in PRESET_FONTS]
        known = {choice.family for choice in presets}
        return presets + [FontChoice(family + " · 已导入", family) for family in imported if family not in known]

    def restore_family(self, requested):
        if any(choice.family == requested and choice.available for choice in self.choices()):
            return requested, ""
        fallback = "苹方" if sys.platform == "darwin" else "微软雅黑"
        return DEFAULT_FONT_FAMILY, f"上次选择的字体不可用，已恢复为{fallback}；可重新导入字体。"

    def import_font(self, source: Path):
        source = Path(source)
        if not source.is_file():
            raise ValueError("字体文件不存在，请重新选择。")
        if source.suffix.lower() not in FONT_EXTENSIONS:
            raise ValueError("请选择 TTF、OTF 或 TTC 字体文件。")
        data = source.read_bytes()
        name = hashlib.sha256(data).hexdigest() + source.suffix.lower()
        target = self.directory / name
        if name in self._loaded and target.is_file() and target.read_bytes() == data:
            return self._loaded[name][1], False
        if target.exists() and target.read_bytes() != data:
            raise ValueError("已保存的字体文件损坏，请移走该文件后重新导入。")
        registered = self._register(data)
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                with tempfile.NamedTemporaryFile(dir=self.directory, suffix=".tmp", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                temporary.replace(target)
                temporary = None
            previous = self._loaded.get(name)
            self._loaded[name] = registered
            if previous:
                QFontDatabase.removeApplicationFont(previous[0])
        except OSError:
            QFontDatabase.removeApplicationFont(registered[0])
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return registered[1], True

    def close(self):
        for identifier, _ in self._loaded.values():
            QFontDatabase.removeApplicationFont(identifier)
        self._loaded.clear()
