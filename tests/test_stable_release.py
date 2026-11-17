"""Published stable metadata and assets must match the verified local binaries."""
import json
from pathlib import Path
import unittest
from PySide6.QtGui import QImageReader

ROOT=Path(__file__).resolve().parents[1]


class StableReleaseTests(unittest.TestCase):
    def record(self):
        return json.loads((ROOT/'docs/research/stable-release-20261117.json').read_text(encoding='utf-8'))

    def test_stable_latest_release_and_all_six_public_assets_match_runtime(self):
        record=self.record();publication=record['published']
        self.assertTrue(record['passed'] and record['same_engine'] and record['accepted_behavior_unchanged'])
        self.assertEqual((record['version'],record['channel']),('0.8.0','stable'))
        self.assertTrue(record['user_acceptance_confirmed'] and record['user_publication_authorized'])
        self.assertTrue(publication['passed'] and publication['is_latest_stable'])
        self.assertFalse(publication['prerelease'] or publication['draft'])
        self.assertEqual(publication['tag'],'v0.8.0')
        self.assertEqual(publication['runtime_source_commit'],record['runtime_source_commit'])
        assets={row['name']:row for row in record['public_downloads']['assets']}
        self.assertEqual(len(assets),6)
        self.assertEqual({row['player'] for row in record['archives']},{'netease','qqmusic','kugou'})
        self.assertEqual(len({row['exe_sha256'] for row in record['archives']}),1)
        for row in record['archives']:
            self.assertTrue(row['crc'] and row['private_data_excluded'] and row['qt_runtime_complete'])
            self.assertTrue(row['license_bytes_verified'] and row['developer_path_removed'])
            asset=assets[row['name']]
            self.assertEqual((asset['sha256'],asset['bytes']),(row['sha256'],row['bytes']))
            for name in (row['name'],row['name']+'.sha256'):
                self.assertEqual(assets[name]['anonymous_head_status'],200)
                self.assertTrue(assets[name]['server_digest_matches'])
                self.assertEqual(assets[name]['tag_commit'],record['runtime_source_commit'])
            self.assertTrue(assets[row['name']+'.sha256']['downloaded_checksum_verified'])
        self.assertTrue(record['public_release_created'] and record['remote_tag_created'] and record['git_push_performed'])

    def test_formal_native_checks_personal_data_and_scope_are_preserved(self):
        record=self.record()
        for row in record['archives']:
            native=row['native_groups']
            self.assertTrue(native['passed'] and native['packaged'] and all(native['checks'].values()))
            self.assertTrue(native['synthetic_lyric_times'])
            self.assertFalse(native['real_playback'])
            self.assertLessEqual(max(item['warm_render_p95_ms'] for item in native['measurements']),33)
        self.assertEqual(sum(len(row['native_groups']['checks']) for row in record['archives']),171)
        self.assertEqual(sorted(row['smoke_checks'] for row in record['archives'] if row['smoke_checks']),[75,75])
        local=record['installed']
        self.assertTrue(local['passed'] and local['old_setting_values_unchanged'] and local['fonts_presets_and_bridge_unchanged'])
        self.assertEqual((len(local['upgrades']),local['profiles_preserved']),(3,2))
        self.assertTrue(all(row['path_preserved'] and row['backup_available'] for row in local['upgrades']))
        self.assertNotIn('running_before',local)
        self.assertTrue(record['restored']['passed'] and record['installed_ui']['passed'] and record['native_entries']['passed'])
        self.assertEqual(record['music_client_commands'],0)
        self.assertIn('new_real_song_regression_in_formal_packaging_step',record['not_verified'])
        self.assertFalse(QImageReader(str(ROOT/'docs/images/display-limit-080.png')).read().isNull())
        self.assertIn('stable-release-20261117.json',(ROOT/'README.md').read_text(encoding='utf-8'))
