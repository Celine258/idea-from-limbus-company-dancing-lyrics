"""Document the real installed launch path separately from public-package tests."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LocalUpgradeEvidenceTests(unittest.TestCase):
    def test_installed_runtime_field_and_preservation_match_recorded_upgrade(self):
        record = json.loads((ROOT / 'docs/research/local-netease-upgrade-20261024.json').read_text(encoding='utf-8'))
        public = json.loads((ROOT / 'docs/research/scramble-release-20261024.json').read_text(encoding='utf-8'))
        self.assertTrue(record['passed'])
        self.assertEqual(record['before']['version'], '0.8.0-beta.1')
        self.assertEqual(record['after']['version'], '0.8.0-beta.3')
        self.assertEqual(record['after']['exe_sha256'], next(row['exe_sha256'] for row in public['archives'] if row['player'] == 'netease'))
        self.assertTrue(record['after']['launch_path_unchanged'] and record['after']['real_client_connected'])
        self.assertEqual(record['native_lifetime_control'], dict(present=True, value=6, minimum=0, maximum=120, scrolled_visible=True))
        self.assertEqual(record['preservation']['old_settings_changed'], [])
        self.assertTrue(record['preservation']['fonts_presets_bridge_preserved'])
        self.assertTrue(record['cloudmusic_processes_unchanged'] and record['scramble_restored_to_original'])
        self.assertEqual(record['music_playback_commands'], 0)
        self.assertTrue(record['installed_smoke']['passed'])
        self.assertTrue(all(record['installed_smoke']['boolean_checks'].values()))
        self.assertIn('not displayed frame rate', record['live_responsiveness']['measures'])
        self.assertFalse(record['public_release_engine_changed'])

    def test_readme_explains_installed_launch_path_and_control_location(self):
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
        for phrase in ('核对实际运行版本', '安装时记录的路径', '完整更新原目录',
                       '保留 `.state`', '换目录后重新安装联动', '乱码退场下方'):
            self.assertIn(phrase, text)
