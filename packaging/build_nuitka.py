"""Build the standalone ShotTrainer bundle with Nuitka.

Replaces the previous PyInstaller spec. Outputs the same paths the
downstream installer scripts (``make_dmg.sh``, ``shottrainer.iss``)
expect, so they keep working unchanged:

- All platforms: ``dist/ShotTrainer/``  (the standalone folder)
- macOS:         ``dist/ShotTrainer.app``  (alongside the folder build)
- Windows:       ``dist/ShotTrainer/ShotTrainer.exe`` inside the folder

Run via the Makefile (``make package``) or directly:

    uv run --extra package python packaging/build_nuitka.py

Notes:

- Nuitka picks up ``shottrainer`` and ``cv2`` via the venv created by
  ``uv sync --extra package``. No PYTHONPATH gymnastics needed.
- ``--enable-plugin=pyside6`` bundles Qt plugins, QML files, and
  translations the same way the PySide6 PyInstaller hook used to.
- Compile time is the main tradeoff against PyInstaller: 5-15 minutes
  on CI. ``--remove-output`` keeps disk usage in check by deleting the
  intermediate build tree once the bundle is written.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGING = PROJECT_ROOT / "packaging"
DIST = PROJECT_ROOT / "dist"
ENTRY = PACKAGING / "ShotTrainer.py"
ICNS = PACKAGING / "icon.icns"
ICO = PROJECT_ROOT / "src" / "shottrainer" / "ui" / "assets" / "icon.ico"


def _read_version() -> str:
    """Return the project version, taken from ``pyproject.toml``.

    The version lives in one place (``pyproject.toml``) and is exposed
    at runtime through ``shottrainer.__version__``.
    """
    pyproject = PROJECT_ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError(f"Could not parse version from {pyproject}")
    return match.group(1)


APP_NAME = "ShotTrainer"
BUNDLE_ID = "org.shottrainer.app"
APP_VERSION = _read_version()

CAMERA_USAGE = "ShotTrainer uses the camera to track the aiming point on the target."
MIC_USAGE = "ShotTrainer listens for the sound of a shot to record hit timing."


def _common_args() -> list[str]:
    args = [
        "--standalone",
        "--enable-plugin=pyside6",
        "--include-package=shottrainer",
        "--include-package-data=shottrainer",
        "--include-package-data=cv2",
        f"--output-dir={DIST}",
        "--remove-output",
        "--assume-yes-for-downloads",
        # Quiets the runtime "Nuitka is running in non-deployment mode"
        # banner and skips a few self-execution checks unsuitable for
        # release builds.
        "--deployment",
    ]
    # macOS has a case-insensitive filesystem (APFS by default), which
    # means the bundle's binary at ``Contents/MacOS/ShotTrainer`` would
    # collide with the compiled ``shottrainer`` package directory placed
    # alongside it. Renaming the binary side-steps that without
    # affecting Linux or Windows, where the layout doesn't collide.
    # The .app's CFBundleExecutable is set from ``--output-filename``
    # so macOS still launches the right thing when the user opens the
    # .app.
    if platform.system() == "Darwin":
        args.append("--output-filename=ShotTrainer-bin")
    else:
        args.append(f"--output-filename={APP_NAME}")
    return args


def _platform_args() -> list[str]:
    sysname = platform.system()
    if sysname == "Darwin":
        args = [
            "--macos-create-app-bundle",
            "--macos-app-mode=gui",
            f"--macos-app-name={APP_NAME}",
            f"--macos-app-version={APP_VERSION}",
            f"--macos-signed-app-name={BUNDLE_ID}",
            f"--macos-app-protected-resource=NSCameraUsageDescription:{CAMERA_USAGE}",
            f"--macos-app-protected-resource=NSMicrophoneUsageDescription:{MIC_USAGE}",
        ]
        if ICNS.exists():
            args.append(f"--macos-app-icon={ICNS}")
        return args
    if sysname == "Windows":
        args = [
            "--windows-console-mode=disable",
            f"--windows-product-name={APP_NAME}",
            f"--windows-product-version={APP_VERSION}.0",
            "--windows-company-name=dsgnr",
            f"--windows-file-description={APP_NAME}",
        ]
        if ICO.exists():
            args.append(f"--windows-icon-from-ico={ICO}")
        return args
    # Linux: nothing platform-specific. The user's distro provides
    # libportaudio2 / OpenGL / xkbcommon at runtime.
    return []


def _rename_dist_folder() -> None:
    """Rename ``dist/ShotTrainer.dist/`` to ``dist/ShotTrainer/``.

    Nuitka uses the entry script's basename for the output directory.
    On macOS the ``.app`` bundle is the deliverable so this rename is
    skipped. On Windows and Linux the Inno Setup script and the
    release archiver expect the bare folder name.
    """
    nuitka_dist = DIST / f"{APP_NAME}.dist"
    final_dist = DIST / APP_NAME
    if not nuitka_dist.exists():
        return
    if final_dist.exists():
        shutil.rmtree(final_dist)
    nuitka_dist.rename(final_dist)


def main() -> int:
    if not ENTRY.exists():
        print(f"Entry script missing: {ENTRY}", file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        *_common_args(),
        *_platform_args(),
        str(ENTRY),
    ]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, check=False)
    if proc.returncode != 0:
        return proc.returncode

    if platform.system() != "Darwin":
        _rename_dist_folder()

    return 0


if __name__ == "__main__":
    sys.exit(main())
