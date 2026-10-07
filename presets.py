"""Visual-only presets. Atomic writes never replace an unreadable preset file."""
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import tempfile
import uuid
from settings import Preferences, normalize_preferences

EFFECT_KEYS = tuple(key for key in asdict(Preferences()) if key not in ("region", "delay_ms", "volume"))


def effect_values(prefs):
    return {key: getattr(prefs, key) for key in EFFECT_KEYS}


@dataclass(frozen=True)
class EffectPreset:
    id: str
    name: str
    values: dict
    builtin: bool = False


BUILTINS = (
    EffectPreset("builtin:quiet", "安静办公", effect_values(replace(Preferences(), font_family="SimSun", font_size=28,
        glow_strength=30, opacity=60, motion="wave", jump=2, angle=3, entry_speed=80, exit_speed=80)), True),
    EffectPreset("builtin:lively", "轻快律动", effect_values(replace(Preferences(), color="#ff4080", opacity=80,
        animation_style="ripple_wave", jump=10, angle=8, entry_speed=140, exit_speed=140)), True),
)


def preset_name(name):
    if not isinstance(name, str):
        raise ValueError("请输入方案名称。")
    name = name.strip()
    if not 1 <= len(name) <= 48 or any(ord(c) < 32 for c in name):
        raise ValueError("方案名称需为 1–48 个字符，不能包含换行。")
    return name


class PresetStore:
    def __init__(self, path):
        self.path = Path(path)
        self.custom = {}
        self.error = ""
        try:
            if self.path.exists():
                document = json.loads(self.path.read_text(encoding="utf-8-sig"))
                if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("presets"), list):
                    raise ValueError("方案文件版本或内容无效")
                for entry in document["presets"]:
                    identifier, name, raw = entry["id"], preset_name(entry["name"]), entry["values"]
                    if not isinstance(identifier, str) or not identifier or identifier.startswith("builtin:") or identifier in self.custom:
                        raise ValueError("方案标识无效")
                    if not isinstance(raw, dict):
                        raise ValueError("方案设置无效")
                    values = effect_values(Preferences())
                    for key in EFFECT_KEYS:
                        if key in raw:
                            if type(raw[key]) is not type(values[key]):
                                raise ValueError("方案设置类型无效")
                            values[key] = raw[key]
                    if any(p.name.casefold() == name.casefold() for p in self.all()):
                        raise ValueError("方案名称重复")
                    self.custom[identifier] = EffectPreset(identifier, name, effect_values(normalize_preferences(Preferences(**values))))
        except (OSError, ValueError, TypeError, KeyError):
            self.custom.clear()
            self.error = "保存的方案无法读取，原文件已保留。请备份并移走方案文件后重试。"

    def all(self):
        return [*BUILTINS, *sorted(self.custom.values(), key=lambda preset: preset.name.casefold())]

    def get(self, identifier):
        return next((preset for preset in self.all() if preset.id == identifier), None)

    def named(self, name):
        return next((preset for preset in self.all() if preset.name.casefold() == name.strip().casefold()), None)

    def _write(self, presets):
        if self.error and self.path.exists():
            raise ValueError(self.error)
        self.error = ""
        document = {"version": 1, "presets": [asdict(preset) for preset in presets.values()]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8"))
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.custom = presets

    def save(self, name, prefs, identifier=None):
        name = preset_name(name)
        previous = self.get(identifier) if identifier else None
        if identifier and (previous is None or previous.builtin):
            raise ValueError("内置方案只读，请另存为自己的方案。")
        duplicate = self.named(name)
        if duplicate and duplicate.id != identifier:
            raise ValueError("已有同名方案，请选择其他名称或确认覆盖。")
        identifier = identifier or "custom:" + uuid.uuid4().hex
        preset = EffectPreset(identifier, name, effect_values(prefs))
        self._write({**self.custom, identifier: preset})
        return preset

    def delete(self, identifier):
        previous = self.get(identifier)
        if previous is None or previous.builtin:
            raise ValueError("只能删除自己的方案。")
        updated = dict(self.custom)
        del updated[identifier]
        self._write(updated)
