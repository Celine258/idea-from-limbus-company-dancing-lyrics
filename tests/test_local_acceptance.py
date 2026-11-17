"""Local acceptance packages must not masquerade as published downloads."""
import json
from pathlib import Path
import subprocess
import unittest
from app_info import APP_VERSION, KUGOU_VERSION

ROOT=Path(__file__).resolve().parents[1]


class LocalAcceptanceTests(unittest.TestCase):
    def test_accepted_candidate_is_historical_and_formal_target_has_user_approval(self):
        published=json.loads((ROOT/'release/published-windows.json').read_text(encoding='utf-8'))
        candidate=json.loads((ROOT/'docs/research/local-acceptance-20261117.json').read_text(encoding='utf-8'))
        approval=json.loads((ROOT/'release/stable-approval.json').read_text(encoding='utf-8'))
        self.assertEqual(candidate['versions'],dict(shared='0.8.0-beta.6',kugou='0.8.0-beta.6-kugou.1'))
        self.assertTrue(approval['user_accepted'] and approval['publication_authorized'])
        self.assertEqual(approval['candidate_runtime_commit'],candidate['runtime_source_commit'])
        self.assertEqual((APP_VERSION,KUGOU_VERSION),(published['shared'],published['kugou']))
        self.assertEqual(approval['version'],APP_VERSION)
        text=(ROOT/'README.md').read_text(encoding='utf-8')
        self.assertIn(f'releases/tag/v{APP_VERSION}',text)
        self.assertIn('正式版',text)
        self.assertIn('项目目录说明.md',text)

    def test_local_binaries_are_ignored_but_source_and_instructions_are_trackable(self):
        paths=['本地测试包/probe.exe','项目目录说明.md','release/published-windows.json','tests/test_local_acceptance.py']
        result=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','check-ignore','--no-index','--stdin','-z'],
            cwd=ROOT,input='\0'.join(paths)+'\0',text=True,encoding='utf-8',capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.rstrip('\0').split('\0'),paths[:1])

    def test_archive_history_is_retained_and_player_guides_describe_formal_release(self):
        record=json.loads((ROOT/'docs/research/workspace-organization-20261117.json').read_text(encoding='utf-8'))
        self.assertTrue(record['passed'] and record['source_structure_unchanged'])
        self.assertEqual(record['deleted_files'],0)
        self.assertGreater(record['moved_items'],0)
        self.assertTrue(record['active_runtime_paths_preserved'] and record['personal_settings_directories_preserved'])
        self.assertFalse(record['public_release_created'] or record['git_push_performed'])
        for name in ('NETEASE.md','QQMUSIC.md','KUGOU.md','release/netease/使用说明.txt',
                     'release/qqmusic/使用说明.txt','release/kugou-guide.txt'):
            text=(ROOT/name).read_text(encoding='utf-8')
            for phrase in ('正式版','同时显示上限','2／3／4 组','默认 4 组'):
                self.assertIn(phrase,text,name)
