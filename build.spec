# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for MHG2GA."""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'src' / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'src' / 'gui' / 'resources'), 'src/gui/resources'),
        (str(ROOT / 'src' / 'config' / 'default.yaml'), 'src/config'),
    ],
    hiddenimports=[
        'airtest',
        'airtest.core.api',
        'airtest.core.android',
        'airtest.core.android.adb',
        'cv2',
        'numpy',
        'PIL',
        'yaml',
        'PyQt6',
        'PyQt6.sip',
        *collect_submodules('airtest'),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MHG2GA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / 'src' / 'gui' / 'resources' / 'icon.png'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MHG2GA',
)
