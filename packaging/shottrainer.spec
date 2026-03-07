# PyInstaller spec for ShotTrainer.
#
# Build with:
#   pyinstaller packaging/shottrainer.spec
#
# Notes:
# - PySide6 ships its own Qt plugins. PyInstaller's PySide6 hook usually
#   picks them up; if you trim your build, ensure the platform plugin
#   directory still ends up bundled.
# - opencv-python ships its own native libs and a small numpy import path.
#   ``collect_dynamic_libs`` makes sure the .so/.dylib/.dll come along.
# - sounddevice depends on PortAudio. PortAudio is bundled inside the
#   sounddevice wheel on the platforms we care about.

# ruff: noqa
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_data_files,
    collect_submodules,
)

block_cipher = None

binaries = []
binaries += collect_dynamic_libs("cv2")
binaries += collect_dynamic_libs("sounddevice")

datas = []
datas += collect_data_files("cv2")
datas += collect_data_files("sounddevice")
datas += collect_data_files("shottrainer", subdir="ui/assets")

hiddenimports = []
hiddenimports += collect_submodules("shottrainer")

a = Analysis(
    ["../src/shottrainer/app/main.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
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
    name="ShotTrainer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="../src/shottrainer/ui/assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ShotTrainer",
)
