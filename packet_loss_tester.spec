# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_root = Path(globals().get("SPECPATH", Path.cwd())).resolve()

a = Analysis(
    ["main.py"],
    pathex=[str(project_root), str(project_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["tkinter", "tkinter.ttk", "tkinter.scrolledtext"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PacketLossTester",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
