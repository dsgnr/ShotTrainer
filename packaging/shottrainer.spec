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
# - sounddevice is a single-file module that statically links PortAudio
#   inside its wheel, so PyInstaller picks it up via the standard import
#   graph; no extra ``collect_*`` calls are needed.
# - SQLAlchemy advertises optional database dialects (psycopg2, MySQLdb,
#   pysqlite2). PyInstaller warns about each; they're fine to leave
#   missing because we only use the stdlib sqlite3 driver.
# - On macOS the spec also produces a ``ShotTrainer.app`` bundle next to
#   the one-folder build via the ``BUNDLE`` step. The bundle's
#   Info.plist is read from ``packaging/Info.plist.in`` so camera and
#   microphone usage descriptions are present.

# ruff: noqa
import platform
import plistlib
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_data_files,
    collect_submodules,
)

block_cipher = None

SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent
ASSETS_DIR = PROJECT_ROOT / "src" / "shottrainer" / "ui" / "assets"
ICNS_PATH = SPEC_DIR / "icon.icns"
ICO_PATH = ASSETS_DIR / "icon.ico"


def _read_plist() -> dict:
    plist_path = SPEC_DIR / "Info.plist.in"
    if not plist_path.exists():
        return {}
    with plist_path.open("rb") as fh:
        try:
            return plistlib.load(fh)
        except Exception:
            return {}


def _icon_for_platform():
    """Return the icon path PyInstaller should embed.

    Windows takes the ``.ico``; macOS prefers an ``.icns`` if one has
    been generated next to this spec (``packaging/icon.icns``).
    Otherwise PyInstaller falls back to its default icon.
    """
    if platform.system() == "Darwin" and ICNS_PATH.exists():
        return str(ICNS_PATH)
    if platform.system() == "Windows" and ICO_PATH.exists():
        return str(ICO_PATH)
    return None


binaries = []
binaries += collect_dynamic_libs("cv2")

datas = []
datas += collect_data_files("cv2")
datas += collect_data_files("shottrainer", subdir="ui/assets")

hiddenimports = []
hiddenimports += collect_submodules("shottrainer")

a = Analysis(
    [str(PROJECT_ROOT / "src" / "shottrainer" / "app" / "main.py")],
    pathex=[str(PROJECT_ROOT / "src")],
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
    icon=_icon_for_platform(),
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

if platform.system() == "Darwin":
    plist_overrides = _read_plist()
    app = BUNDLE(
        coll,
        name="ShotTrainer.app",
        icon=str(ICNS_PATH) if ICNS_PATH.exists() else None,
        bundle_identifier=plist_overrides.get(
            "CFBundleIdentifier", "org.shottrainer.app"
        ),
        info_plist=plist_overrides or None,
    )
