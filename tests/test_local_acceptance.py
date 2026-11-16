"""Local acceptance packages must not masquerade as published downloads."""
import json
from pathlib import Path
import subprocess
import unittest
from app_info import APP_VERSION, KUGOU_VERSION

ROOT=Path(__file__).resolve().parents[1]


class LocalAcceptanceTests(unittest.TestCase):
    def test_local_versions_and_existing_public_downloads_are_distinct(self):
        published=json.loads((ROOT/'release/published-windows.json').read_text(encoding='utf-8'))
        self.assertEqual((APP_VERSION,KUGOU_VERSION),('0.8.0-beta.6','0.8.0-beta.6-kugou.1'))
        self.assertEqual(published['shared'],'0.8.0-beta.5')
        self.assertEqual(published['kugou'],'0.8.0-beta.5-kugou.1')
        text=(ROOT/'README.md').read_text(encoding='utf-8')
        self.assertIn(f'本地测试包/{APP_VERSION}/',text)
        self.assertNotIn(f'releases/tag/v{APP_VERSION}',text)
        self.assertNotIn(f'releases/download/v{KUGOU_VERSION}',text)
        self.assertIn('项目目录说明.md',text)

    def test_local_binaries_are_ignored_but_source_and_instructions_are_trackable(self):
        paths=['本地测试包/probe.exe','项目目录说明.md','release/published-windows.json','tests/test_local_acceptance.py']
        result=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','check-ignore','--no-index','--stdin','-z'],
            cwd=ROOT,input='\0'.join(paths)+'\0',text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.rstrip('\0').split('\0'),paths[:1])

    def test_archive_record_and_player_instructions_preserve_the_testing_boundary(self):
        record=json.loads((ROOT/'docs/research/workspace-organization-20261117.json').read_text(encoding='utf-8'))
        self.assertTrue(record['passed'] and record['source_structure_unchanged'])
        self.assertEqual(record['deleted_files'],0)
        self.assertGreater(record['moved_items'],0)
        self.assertTrue(record['active_runtime_paths_preserved'] and record['personal_settings_directories_preserved'])
        self.assertFalse(record['public_release_created'] or record['git_push_performed'])
        for name in ('NETEASE.md','QQMUSIC.md','KUGOU.md','release/netease/使用说明.txt',
                     'release/qqmusic/使用说明.txt','release/kugou-guide.txt'):
            text=(ROOT/name).read_text(encoding='utf-8')
            for phrase in ('本地验收版','同时显示上限','2／3／4 组','默认 4 组','公开下载保持原版'):
                self.assertIn(phrase,text,name)
