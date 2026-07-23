# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für SPOCK2 unter Windows.

Build:
  pip install pyinstaller pywin32
  pyinstaller packaging/windows/spock2.spec
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

ROOT = Path(SPECPATH).resolve().parents[1]
SRC = ROOT / "src"

datas = collect_data_files(
    "spock2",
    includes=["**/*.qss", "**/*.png", "**/*.ico", "py.typed"],
)
binaries: list = []
hiddenimports = [
    "spock2",
    "spock2.__main__",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

tmp_ret = collect_all("PySide6")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

if sys.platform == "win32":
    hiddenimports += ["win32print", "win32api", "pywintypes"]

a = Analysis(
    [str(SRC / "spock2" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="spock2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SRC / "spock2" / "ui" / "resources" / "bildmarke.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="spock2",
)
