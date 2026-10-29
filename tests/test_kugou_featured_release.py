"""Published KuGou .2 evidence must retain the failure and actual live scope."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FeaturedReleaseTests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT/'docs/research/kugou-featured-release-20261030.json').read_text(encoding='utf-8'))

    def test_public_zip_matches_runtime_and_preserves_other_players(self):
        record=self.record()
        self.assertTrue(record['passed'])
        self.assertEqual(record['version'],'0.8.0-beta.4-kugou.2')
        package=record['package']
        self.assertTrue(package['crc_verified'] and package['qt_modules_present'] and package['personal_data_excluded'])
        self.assertEqual(package['runtime_source_commit'],record['runtime_source_commit'])
        assets={row['name']:row for row in record['public_downloads']['assets']}
        self.assertEqual(len(assets),2)
        asset=assets[package['archive']]
        self.assertEqual((asset['bytes'],asset['sha256']),(package['bytes'],package['sha256']))
        self.assertTrue(all(row['anonymous_head_status']==200 and row['server_digest_matches'] for row in assets.values()))
        self.assertEqual(record['public_downloads']['tag_commit'],record['runtime_source_commit'])
        self.assertFalse(record['public_downloads']['authenticated_download'])
        self.assertTrue(record['other_player_packages_unchanged'])
        self.assertEqual({row['player'] for row in record['other_player_packages']},{'netease','qqmusic'})
        for row in record['other_player_packages']:
            self.assertTrue(row['unchanged'])

    def test_actual_background_scope_does_not_promote_static_replay_to_same_song_live(self):
        record=self.record()
        self.assertFalse(record['initial_public_probe']['passed'])
        live=record['frozen_live_regression']
        self.assertTrue(live['passed'] and live['packaged'] and live['actual_bat_entry'] and live['developer_path_removed'])
        self.assertTrue(all(live['checks'].values()))
        self.assertFalse(live['simulated_live_data'] or record['synthetic_live_data'])
        self.assertTrue(live['client_window_restored'])
        self.assertGreater(live['max_lines'],0)
        self.assertGreater(live['max_words'],0)
        self.assertEqual([row['phase'] for row in live['window_states']],
                         ['cold_minimized','restored','minimized','tray_hidden'])
        self.assertEqual(record['music_playback_commands'],0)
        self.assertTrue(record['captured_failed_song_metadata_replay']['real_cache_received'])
        if record['failed_song_dynamic_verified']:
            self.assertGreater(record['failed_song_live_samples'],1)
        else:
            self.assertIn('same_failed_featured_song_dynamic_playback',record['not_verified'])
        personal=record['personal_data']
        self.assertTrue(personal['passed'] and personal['fonts_presets_unchanged'] and personal['original_launch_path_preserved'])
        self.assertEqual(personal['changed_old_keys'],[])
        self.assertTrue(record['installed_ui']['passed'] and record['installed_ui']['local_cache_received'])
        self.assertEqual(record['frozen_smoke']['checks'],75)
        self.assertTrue(record['native_entries']['passed'])
        readme=(ROOT/'README.md').read_text(encoding='utf-8')
        self.assertIn('kugou-featured-release-20261030.json',readme)
