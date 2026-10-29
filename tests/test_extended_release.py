"""Verify final beta.4 artifacts without promoting paused reads to playback tests."""
import json
from pathlib import Path
import unittest
from app_info import APP_VERSION, KUGOU_VERSION

ROOT = Path(__file__).resolve().parents[1]


class ExtendedReleaseTests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT / 'docs/research/extended-release-20261030.json').read_text(encoding='utf-8'))

    def test_public_assets_tags_and_frozen_engine_match(self):
        record = self.record()
        self.assertTrue(record['passed'] and record['same_engine'] and record['public_packages_updated'])
        self.assertEqual(record['versions'], dict(shared=APP_VERSION, kugou=KUGOU_VERSION))
        assets = {row['name']:row for row in record['public_downloads']['assets']}
        self.assertEqual(len(assets), 6)
        self.assertEqual({row['player'] for row in record['archives']}, {'kugou','netease','qqmusic'})
        self.assertEqual(len({row['exe_sha256'] for row in record['archives']}), 1)
        for row in record['archives']:
            asset = assets[row['name']]
            self.assertEqual(asset['sha256'], row['sha256'])
            self.assertEqual(asset['bytes'], row['bytes'])
            self.assertEqual(asset['tag_commit'], record['runtime_source_commit'])
            self.assertEqual(asset['anonymous_head_status'], 200)
        for key in ('frozen_extended_display','frozen_scramble_transitions'):
            result = record[key]
            self.assertTrue(result['passed'] and result['packaged'] and result['developer_path_removed'])
            self.assertTrue(all(result['checks'].values()))
            self.assertEqual(result['music_client_commands'], 0)
        self.assertLessEqual(max(row['warm_render_p95_ms'] for row in record['frozen_extended_display']['measurements']), 33)

    def test_installed_controls_and_live_scope_are_explicit(self):
        record = self.record()
        installed = record['installed']
        self.assertTrue(installed['versions_verified'] and installed['old_launch_paths_preserved'])
        self.assertEqual(installed['kugou_version'], KUGOU_VERSION)
        controls = installed['kugou_controls']
        self.assertTrue(controls['passed'] and controls['new_controls_present'] and controls['default_mode_off'])
        self.assertEqual((controls['seconds'], controls['minimum'], controls['maximum']), (10,1,120))
        kugou = record['kugou_current_client']
        self.assertTrue(kugou['connected'] and kugou['local_cache_received'])
        self.assertFalse(kugou['playing'] or kugou['playback_continuity_verified'])
        self.assertFalse(kugou['minimized_playback_current_release_verified'])
        self.assertEqual(record['music_playback_commands'], 0)
        self.assertIn('actual_exclusive_fullscreen_game', record['not_verified'])
        personal = record['personal_data']
        self.assertTrue(personal['passed'] and personal['kugou_after_old_exit_settings_unchanged'])
        self.assertFalse(personal['before_old_exit_values_comparison_available'])
        from PySide6.QtGui import QImageReader
        self.assertFalse(QImageReader(str(ROOT/'docs/images/extended-display-beta4.png')).read().isNull())
        text=(ROOT/'README.md').read_text(encoding='utf-8')
        for phrase in ('11.766ms','客户端暂停','延长显示时间','不能保证覆盖独占全屏'):
            self.assertIn(phrase, text)
