# Packaging

PyInstaller produces the platform binaries. Per-platform tooling
wraps them into a `.dmg` (macOS) or `.exe` installer (Windows).

## Build

The simplest path is `make` from the repo root:

```
make package        # one-folder PyInstaller build for the current platform
make dmg            # macOS only: wraps dist/ShotTrainer.app in a .dmg
make installer      # Windows only: runs Inno Setup over dist/ShotTrainer
```

Each higher-level target depends on `make package`, so a single command
gets you a distributable artefact.

The raw folder lives at `dist/ShotTrainer/`. On macOS PyInstaller also
emits `dist/ShotTrainer.app` with the bundle's `Info.plist` populated
from `Info.plist.in`.

If you'd rather drive PyInstaller directly:

```
uv sync --extra package
uv run pyinstaller packaging/shottrainer.spec --noconfirm
```

## macOS

The spec produces both a one-folder build and a `ShotTrainer.app`
bundle. The bundle's `Info.plist` is read from
`packaging/Info.plist.in` so camera and microphone usage descriptions
are populated and macOS shows the permission prompts on first launch.

The icon is generated from the PNG sources by `build_icns.sh`. The
`make package` target runs that script automatically. If you ever
invoke PyInstaller without going through Make, run
`bash packaging/build_icns.sh` first so PyInstaller can embed the
icon.

`make dmg` calls `make_dmg.sh`, which uses the system `hdiutil` to
build `dist/ShotTrainer-macOS.dmg` containing the `.app` and a
shortcut to `/Applications`.

For signing and notarising:

```
codesign --deep --force --options runtime \
    --sign "Developer ID Application: ..." dist/ShotTrainer.app
xcrun notarytool submit dist/ShotTrainer-macOS.dmg --keychain-profile <profile> --wait
xcrun stapler staple dist/ShotTrainer-macOS.dmg
```

If the user denies camera or microphone access, the relevant subsystem
surfaces an error in the status bar and recording stops gracefully.

## Windows

`make installer` runs `make_installer.ps1`, which invokes Inno Setup 6
over `packaging/shottrainer.iss`. The installer lands at
`dist/ShotTrainer-Setup.exe`.

Install Inno Setup 6 first (Chocolatey: `choco install innosetup`).
The PowerShell wrapper looks for `iscc` on PATH and falls back to the
default install location.

If antivirus tooling flags the bootloader, build with
`--bootloader-ignore-signals` removed and consider code-signing the
executable.

## Linux

The PyInstaller folder works as-is on most distributions. For wider
reach package it as an AppImage with `appimagetool`, or build a `.deb`
or `.rpm` with `fpm`. Neither is set up in the project yet because
distro packaging conventions vary. Reports and PRs welcome.

The user must have access to `/dev/video*` (usually via the `video`
group) and to PortAudio via PulseAudio or ALSA. Wayland users may
need the X11 plugin if PySide6 cannot find a working Wayland platform
plugin on their system.

## Reproducible builds

PyInstaller is not deterministic out of the box. For closer-to-
reproducible builds set `SOURCE_DATE_EPOCH` and pin all dependencies
with hashes. This is best handled in the CI workflow rather than in
this spec.
