"""Formal release uses an approved candidate and unambiguous player archives."""
import json
from pathlib import Path
import unittest
from app_info import APP_VERSION,KUGOU_VERSION
from tools.package_release import archive_name
from tools.package_kugou import archive_name as kugou_archive_name

ROOT=Path(__file__).resolve().parents[1]


class StablePreparationTests(unittest.TestCase):
    def test_approved_candidate_and_unified_stable_guides(self):
        approval=json.loads((ROOT/'release/stable-approval.json').read_text(encoding='utf-8'))
        self.assertTrue(approval['user_accepted'] and approval['publication_authorized'])
        self.assertEqual((APP_VERSION,KUGOU_VERSION,approval['version']),('0.8.0','0.8.0','0.8.0'))
        self.assertEqual(approval['channel'],'stable')
        self.assertEqual(approval['accepted_candidate'],'0.8.0-beta.6')
        notes=(ROOT/'release/stable-release-notes.md').read_text(encoding='utf-8')
        self.assertIn('正式版',notes.splitlines()[0])
        for filename in (archive_name('netease'),archive_name('qqmusic'),kugou_archive_name()):
            self.assertIn('/releases/download/v0.8.0/'+filename,notes)
        for name in ('README.md','release/使用说明.txt','release/netease/使用说明.txt',
                     'release/qqmusic/使用说明.txt','release/kugou-guide.txt'):
            text=(ROOT/name).read_text(encoding='utf-8')
            self.assertIn('正式版',text)
            self.assertIn('2／3／4 组',text)
            self.assertNotIn('本地验收版','\n'.join(text.splitlines()[:5]))

    def test_stable_archive_names_are_unique_and_old_kugou_naming_is_preserved(self):
        names={archive_name('netease'),archive_name('qqmusic'),kugou_archive_name()}
        self.assertEqual(names,{'dancing-lyrics-0.8.0-netease-windows-x64.zip',
            'dancing-lyrics-0.8.0-qqmusic-windows-x64.zip','dancing-lyrics-0.8.0-kugou-windows-x64.zip'})
        self.assertEqual(kugou_archive_name('0.8.0-beta.6-kugou.1'),
            'dancing-lyrics-0.8.0-beta.6-kugou.1-windows-x64.zip')
        manifest=json.loads((ROOT/'release/published-windows.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['channel'],'stable')
        self.assertEqual(manifest['kugou_archive'],kugou_archive_name())
