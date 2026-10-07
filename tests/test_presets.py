"""Preset persistence, compatibility and failure atomicity."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from presets import PresetStore, EFFECT_KEYS
from settings import Preferences


class PresetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "effect-presets.json"
        self.store = PresetStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_builtins_match_design_and_exclude_transport_region_and_offset(self):
        quiet, lively = self.store.all()
        self.assertEqual((quiet.name, quiet.values["font_family"], quiet.values["entry_speed"]), ("安静办公", "SimSun", 80))
        self.assertEqual((lively.name, lively.values["animation_style"], lively.values["color"]), ("轻快律动", "ripple_wave", "#ff4080"))
        self.assertFalse(lively.values["singing_sync"])
        self.assertTrue(set(EFFECT_KEYS).isdisjoint(("region", "delay_ms", "volume", "theme")))
        with self.assertRaises(ValueError):
            self.store.delete(quiet.id)
        with self.assertRaises(ValueError):
            self.store.save(quiet.name, Preferences(), quiet.id)

    def test_save_restart_update_and_delete_retain_the_complete_visual_combination(self):
        prefs = replace(Preferences(), font_family="Imported Custom", color="#ffaa00", animation_style="fall_shake",
                        entry_speed=65, exit_speed=170, shake_frequency=14, fall_distance=96, singing_sync=True)
        saved = self.store.save("我的夜间方案", prefs)
        restored = PresetStore(self.path)
        self.assertEqual(restored.get(saved.id), saved)
        self.assertEqual(saved.values["singing_sync"], True)
        updated = restored.save(saved.name, replace(prefs, color="#ff4080"), saved.id)
        self.assertEqual(PresetStore(self.path).get(saved.id), updated)
        restored.delete(saved.id)
        self.assertIsNone(PresetStore(self.path).get(saved.id))

    def test_duplicate_names_and_invalid_names_cannot_overwrite(self):
        saved = self.store.save("Work", Preferences())
        before = self.path.read_bytes()
        for name in ("work", "", "\n", "x" * 49):
            with self.assertRaises(ValueError):
                self.store.save(name, Preferences())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.get(saved.id), saved)

    def test_unreadable_or_future_version_keeps_original_file_and_builtin_choices(self):
        for raw in (b"broken json", b'{"version":2,"presets":[]}'):
            self.path.write_bytes(raw)
            store = PresetStore(self.path)
            self.assertTrue(store.error)
            self.assertEqual(len(store.all()), 2)
            with self.assertRaises(ValueError):
                store.save("新的", Preferences())
            self.assertEqual(self.path.read_bytes(), raw)
            backup = self.path.with_suffix(".backup")
            self.path.replace(backup)
            self.assertIsNotNone(store.save("恢复保存", Preferences()))
            self.assertEqual(backup.read_bytes(), raw)

    def test_failed_atomic_replace_keeps_file_and_in_memory_presets(self):
        saved = self.store.save("Current", Preferences())
        before = self.path.read_bytes()
        with patch("presets.Path.replace", side_effect=PermissionError("write denied")), self.assertRaises(OSError):
            self.store.save(saved.name, replace(Preferences(), color="#ffaa00"), saved.id)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.get(saved.id), saved)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_old_preset_fields_get_defaults_and_out_of_range_values_are_normalized(self):
        self.path.write_text(json.dumps({"version": 1, "presets": [{"id": "custom:test", "name": "Old",
            "values": {"font_family": "KaiTi", "color": "#ff4080", "entry_speed": 0}}]}), encoding="utf-8")
        loaded = PresetStore(self.path).get("custom:test")
        self.assertEqual(loaded.values["entry_speed"], 25)
        self.assertEqual(loaded.values["fall_distance"], 48)
        self.assertFalse(loaded.values["singing_sync"])


if __name__ == "__main__":
    unittest.main()
