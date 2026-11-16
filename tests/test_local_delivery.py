"""Keep local beta.6 evidence separate from user approval and public releases."""
import json
from pathlib import Path
import unittest
from PySide6.QtGui import QImageReader

ROOT=Path(__file__).resolve().parents[1]


class LocalDeliveryTests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT/'docs/research/local-acceptance-20261117.json').read_text(encoding='utf-8'))

    def test_three_complete_local_packages_share_the_tested_runtime_without_publication(self):
        record=self.record()
        self.assertTrue(record['passed'] and record['same_engine'])
        self.assertEqual(record['channel'],'local-acceptance')
        self.assertEqual(record['versions'],dict(shared='0.8.0-beta.6',kugou='0.8.0-beta.6-kugou.1'))
        self.assertEqual({row['player'] for row in record['archives']},{'netease','qqmusic','kugou'})
        self.assertEqual(len({row['exe_sha256'] for row in record['archives']}),1)
        self.assertRegex(record['runtime_source_commit'],r'^[a-f0-9]{40}$')
        for row in record['archives']:
            self.assertTrue(row['crc'] and row['private_data_excluded'] and row['qt_runtime_complete'])
            self.assertTrue(row['license_bytes_verified'] and row['developer_path_removed'])
            self.assertRegex(row['sha256'],r'^[a-f0-9]{64}$')
            native=row['native_groups']
            self.assertTrue(native['passed'] and native['packaged'] and all(native['checks'].values()))
            for limit in (2,3,4):
                self.assertTrue(native['checks'][f'actual_limit_{limit}_active'])
                self.assertTrue(native['checks'][f'actual_limit_{limit}_surfaces_ready'])
                self.assertTrue(native['checks'][f'actual_limit_{limit}_cache_bounded'])
            self.assertLessEqual(max(item['warm_render_p95_ms'] for item in native['measurements']),33)
        self.assertEqual(sum(len(row['native_groups']['checks']) for row in record['archives']),171)
        self.assertEqual(sorted(row['smoke_checks'] for row in record['archives'] if row['smoke_checks']),[75,75])
        self.assertFalse(record['public_release_created'] or record['remote_tag_created'] or record['git_push_performed'])

    def test_original_paths_personal_data_and_pending_manual_acceptance_are_explicit(self):
        record=self.record()
        installed=record['installed']
        self.assertTrue(installed['passed'] and installed['old_setting_values_unchanged'])
        self.assertTrue(installed['fonts_presets_and_bridge_unchanged'])
        self.assertEqual((len(installed['upgrades']),installed['profiles_preserved']),(3,2))
        for row in installed['upgrades']:
            self.assertTrue(row['path_preserved'] and row['backup_available'])
            self.assertEqual(row['exe_sha256'],record['archives'][0]['exe_sha256'])
        self.assertNotIn('running_before',installed)
        ui=record['installed_ui']
        self.assertTrue(ui['passed'] and ui['native_version_present'] and ui['limit_control_present'])
        self.assertTrue(ui['single_instance'] and ui['existing_netease_reused'])
        self.assertTrue(record['restored']['passed'] and record['restored']['old_setting_values_unchanged'])
        self.assertTrue(record['native_entries']['passed'])
        self.assertTrue(all(all(row['checks'].values()) for row in record['native_entries']['reports']))
        self.assertEqual(record['manual_user_acceptance'],'pending')
        self.assertIn('three_real_clients_playback_regression',record['not_verified'])
        self.assertFalse(record['real_client_playback'])
        self.assertEqual(record['music_client_commands'],0)
        self.assertEqual(record['archive_summary']['deleted_files'],0)
        self.assertFalse(QImageReader(str(ROOT/'docs/images/display-limit-beta6.png')).read().isNull())
        self.assertIn('local-acceptance-20261117.json',(ROOT/'README.md').read_text(encoding='utf-8'))
