# Packaging

PyInstaller is the chosen packager. A single spec file works on Windows,
macOS and Linux with platform-specific tweaks for permissions and signing.

## Build

```
pip install -e ".[package]"
pyinstaller packaging/shottrainer.spec --noconfirm
```

The output lands in `dist/ShotTrainer/`. Run the binary from there to
sanity-check before signing or packaging into an installer.

## Windows

PyInstaller produces a directory with `ShotTrainer.exe`. Wrap it in an
installer of your choice (Inno Setup, NSIS) for distribution. No special
permissions handling is required for the camera or microphone.

If antivirus tooling flags the bootloader, build with
`--bootloader-ignore-signals` removed and consider code-signing the
executable.

## macOS

The `.app` bundle needs an `Info.plist` that declares camera and microphone
usage descriptions, otherwise macOS will reject the permission prompts.
Use `packaging/Info.plist.in` as a starting point.

After PyInstaller finishes:

1. Copy `Info.plist.in` into `dist/ShotTrainer.app/Contents/Info.plist`,
   merging with the file PyInstaller wrote.
2. Sign the bundle:
   `codesign --deep --force --options runtime --sign "Developer ID Application: ..." dist/ShotTrainer.app`
3. Notarise via `notarytool submit ... --wait` and `xcrun stapler staple`.

If the user denies camera or microphone access, the relevant subsystem
will surface an error in the status bar. Recording stops gracefully.

## Linux

The output directory works as-is on most distributions. For wider reach
package it as an AppImage with `appimagetool` or build a `.deb` / `.rpm`
with `fpm`.

The user must have access to `/dev/video*` (usually via the `video`
group) and to PortAudio via PulseAudio or ALSA. Wayland users may need
the X11 plugin if PySide6 cannot find a working Wayland platform plugin
on their system.

## Reproducible builds

PyInstaller is not deterministic out of the box. For closer-to-reproducible
builds set `SOURCE_DATE_EPOCH` and pin all dependencies with hashes. This
is best handled in the CI workflow rather than in this spec.
