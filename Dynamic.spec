# Dynamic.spec
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ('icons', 'icons'),
    ('assets', 'assets'),
]
binaries = []
hiddenimports = [
    'src',
    'src.core.Fetcher',
    'src.core',
    'src.core.app_info',
    'src.core.downloader',
    'src.core.models',
    'src.core.universal_scraper',
    'src.core.updater',
    'src.paths',
    'src.ui',
    'src.ui.components',
    'src.ui.components.combo',
    'src.ui.components.controls',
    'src.ui.components.navigation',
    'src.ui.components.overlay',
    'src.ui.components.skeleton',
    'src.ui.components.toast',
    'src.ui.helpers',
    'src.ui.mixins',
    'src.ui.mixins.about',
    'src.ui.mixins.downloads',
    'src.ui.mixins.home',
    'src.ui.mixins.settings',
    'src.ui.mixins.updates',
    'src.ui.mixins.window',
    'src.ui.styles',
    'src.ui.trim',
    'src.ui.trim.download',
    'src.ui.trim.helpers',
    'src.ui.trim.player',
    'src.ui.trim.processing',
    'src.ui.trim.signals',
    'src.ui.trim.standalone',
    'src.ui.trim.tab',
    'src.ui.trim.ui',
    'src.ui.trim.widgets',
    'theme',
    'yt_dlp',
]

for pkg in ('PySide6', 'shiboken6'):
    d, b, h = collect_all(pkg)
    datas.extend(d)
    binaries.extend(b)
    hiddenimports.extend(h)

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6',
        'PyQt5',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Dynamic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/icon.ico',
)