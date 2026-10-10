# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from app_info import APP_VERSION

root = Path(SPECPATH)
a = Analysis([str(root / 'main_mac.py')], pathex=[str(root)],
    binaries=[], datas=[(str(root / 'assets'), 'assets')], hiddenimports=[],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtVirtualKeyboard'],
    noarchive=False, optimize=0)
# The general Qt GUI hook also discovers unused PDF / virtual keyboard plugins.
def used_runtime(entry):
    name = entry[0].lower()
    return not any(part in name for part in ('qtvirtualkeyboard', 'qtpdf', 'libqpdf.'))
a.binaries = [entry for entry in a.binaries if used_runtime(entry)]
a.datas = [entry for entry in a.datas if used_runtime(entry)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CityEchoes',
    debug=False, strip=False, upx=False, console=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CityEchoes')
app = BUNDLE(coll, name='都市回响.app', icon=str(root / 'build/macos/CityEchoes.icns'),
    bundle_identifier='com.celine258.cityechoes', info_plist={
        'CFBundleName': '都市回响', 'CFBundleDisplayName': '都市回响',
        'CFBundleShortVersionString': APP_VERSION, 'CFBundleVersion': '0.6.0',
        'LSMinimumSystemVersion': '13.0', 'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
    })
