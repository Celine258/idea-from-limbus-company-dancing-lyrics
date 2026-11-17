import json
from pathlib import Path
import tempfile
import unittest
from app_info import APP_VERSION, KUGOU_VERSION, kugou_default_mode
from tools.package_kugou import VERSION, validate_runtime, public_files, archive_name as kugou_archive_name


class KugouReleaseTests(unittest.TestCase):
    def test_final_evidence_uses_real_packaged_background_data_and_keeps_limits(self):
        root=Path(__file__).resolve().parents[1]
        record=json.loads((root/'docs/research/kugou-release-20261024.json').read_text(encoding='utf-8'))
        self.assertEqual(record['app_version'],'0.8.0-beta.1-kugou.6')  # Historical release.
        self.assertTrue(record['passed'])
        self.assertTrue(record['public_gui']['actual_bat_entry'])
        self.assertFalse(record['public_gui']['simulated_live_data'])
        for key in ('coldStartMinimized','backgroundConnected','backgroundLyricsReceived','backgroundProgressAdvances'):
            self.assertTrue(record['public_gui']['checks'][key])
        self.assertTrue(record['public_native']['checks']['gracefulExitRestoresNative'])
        self.assertTrue(record['local_install']['personal_file_hashes_unchanged'])
        self.assertEqual(record['playback_commands'],0)
        self.assertFalse(record['existing_netease_and_qq_downloads_replaced'])
        self.assertIn('second_clean_machine',record['not_verified'])
        self.assertIn('client_x86',record['not_verified'])
        self.assertRegex(record['archive']['sha256'],r'^[0-9a-f]{64}$')

    def test_current_kugou_guides_and_download_link_match_dedicated_version(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('KUGOU.md','release/kugou-guide.txt','release/kugou-release-notes.md'):
            text=(root/name).read_text(encoding='utf-8')
            for phrase in (KUGOU_VERSION,'最小化','LOCALAPPDATA','完整解压'):
                self.assertIn(phrase,text)
        readme=(root/'README.md').read_text(encoding='utf-8')
        published=json.loads((root/'release/published-windows.json').read_text(encoding='utf-8'))['kugou']
        self.assertIn(f'releases/download/v{published}/{kugou_archive_name(published)}',readme)
        self.assertIn('CAR0TT0',readme)

    def test_double_click_defaults_are_scoped_to_dedicated_package(self):
        self.assertTrue(kugou_default_mode(r'D:\中文 目录\DancingLyrics-Kugou.exe', True, []))
        for exe, frozen, args in (('FloatingLyrics.exe',True,[]), ('python.exe',False,[]),
                                  ('DancingLyrics-Kugou.exe',True,['--demo']),
                                  ('DancingLyrics-Kugou.exe',True,['--netease'])):
            self.assertFalse(kugou_default_mode(exe, frozen, args))
        self.assertEqual(VERSION, KUGOU_VERSION)
        self.assertEqual(KUGOU_VERSION, APP_VERSION)

    def test_incomplete_qt_is_rejected_before_creating_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'DancingLyrics-Kugou.exe').write_bytes(b'exe')
            with self.assertRaisesRegex(ValueError,'QtCore.pyd'):
                validate_runtime(root)
            for module in ('Core','Gui','Widgets'):
                path=root/f'_internal/PySide6/Qt{module}.pyd'
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'fixture')
            validate_runtime(root)

    def test_archive_allowlist_omits_private_files_and_unrelated_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            allowed=['DancingLyrics-Kugou.exe','使用说明.txt','licenses/MIT.txt','_internal/PySide6/QtCore.pyd']
            private=['.state/settings.ini','app.log','personal.txt','kugou-diagnostic.json',
                     '_internal/settings.ini','_internal/__pycache__/data.pyc','_internal/Qt6VirtualKeyboard.dll']
            for name in allowed+private:
                path=root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('fixture',encoding='utf-8')
            self.assertEqual({p.relative_to(root).as_posix() for p in public_files(root)},set(allowed))
