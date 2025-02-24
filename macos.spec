from PyInstaller.building.api import PYZ, EXE, COLLECT, BUNDLE
from PyInstaller.building.build_main import Analysis

block_cipher = None
a = Analysis(
    ["index_ripper.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["tkinter", "tkinter.ttk"],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="IndexRipper_MacOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

app = BUNDLE(
    exe,
    name="IndexRipper_MacOS.app",
    icon=None,
    bundle_identifier="com.indexripper.app",
) 