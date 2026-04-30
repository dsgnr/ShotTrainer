# Packaging

Nuitka compiles the Python source into a native standalone bundle. Per-platform
tooling wraps the bundle into a `.dmg` (macOS) or `.exe` installer (Windows).

## Build

The simplest path is `make` from the repo root:

```
make package        # standalone Nuitka build for the current platform
make dmg            # macOS only: wraps dist/ShotTrainer.app in a .dmg
make installer      # Windows only: runs Inno Setup over dist/ShotTrainer
```

Each higher-level target depends on `make package`, so a single command gets you
a distributable artefact.

The raw folder lives at `dist/ShotTrainer/`. On macOS Nuitka instead emits
`dist/ShotTrainer.app`. The per-folder build is unused there because the `.app`
is the deliverable.

If you'd rather drive the build directly:

```
uv sync --extra package
uv run --extra package python packaging/build_nuitka.py
```

`build_nuitka.py` is a thin driver that calls `python -m nuitka` with the right
flags per platform, including `--enable-plugin=pyside6` for Qt and the
`--macos-app-protected-resource` entries for camera and microphone permissions.

Compile time is the main tradeoff vs PyInstaller: 5-15 minutes on a warm cache,
longer on a cold one. The bundle itself is smaller and starts faster.

## macOS

`make package` produces `dist/ShotTrainer.app`. Nuitka writes the bundle's
`Info.plist` from the `--macos-app-*` flags in `build_nuitka.py`, including the
camera and microphone usage descriptions, so macOS shows the permission prompts
on first launch.

The icon is generated from the PNG sources by `build_icns.sh`. The
`make package` target runs that script automatically. If you ever invoke Nuitka
without going through Make, run `bash packaging/build_icns.sh` first so Nuitka
can embed the icon.

`make dmg` calls `make_dmg.sh`, which uses the system `hdiutil` to build
`dist/ShotTrainer-macOS.dmg` containing the `.app` and a shortcut to
`/Applications`.

For signing and notarising:

```
codesign --deep --force --options runtime \
    --sign "Developer ID Application: ..." dist/ShotTrainer.app
xcrun notarytool submit dist/ShotTrainer-macOS.dmg --keychain-profile <profile> --wait
xcrun stapler staple dist/ShotTrainer-macOS.dmg
```

If the user denies camera or microphone access, the relevant subsystem surfaces
an error in the status bar and recording stops gracefully.

## Windows

`make installer` runs `make_installer.ps1`, which invokes Inno Setup 6 over
`packaging/shottrainer.iss`. The installer lands at
`dist/ShotTrainer-Setup.exe`.

Install Inno Setup 6 first (Chocolatey: `choco install innosetup`). The
PowerShell wrapper looks for `iscc` on PATH and falls back to the default
install location.

The Nuitka build embeds product metadata (name, version, company) into the
resulting `ShotTrainer.exe` via the `--windows-product-*` flags in
`build_nuitka.py`, so the installer's "About" tab and Windows' Properties dialog
both populate correctly.

## Linux

The Nuitka folder works as-is on most distributions. For wider reach package it
as an AppImage with `appimagetool`, or build a `.deb` or `.rpm` with `fpm`.
Neither is set up in the project yet because distro packaging conventions vary.
Reports and PRs welcome.

The user must have access to `/dev/video*` (usually via the `video` group) and
to PortAudio via PulseAudio or ALSA. Wayland users may need the X11 plugin if
PySide6 cannot find a working Wayland platform plugin on their system.

## Why Nuitka

The previous setup used PyInstaller. Nuitka was picked up because it:

- compiles the Python source to C, producing a real native binary rather than a
  frozen interpreter + zip. Bundles are smaller and startup is faster.
- handles PySide6, OpenCV and SoundDevice via standard plugin/data inclusion
  flags rather than per-package hooks.
- accepts the macOS plist values and Windows resource metadata as command-line
  flags, so version drift between `pyproject.toml` and a templated `Info.plist`
  is no longer possible.

Tradeoffs:

- Compile time is much longer than PyInstaller.
- The first build on a machine downloads a C compiler if one isn't already
  present (Nuitka uses MinGW on Windows by default. MacOS and Linux use the
  system clang/gcc).
