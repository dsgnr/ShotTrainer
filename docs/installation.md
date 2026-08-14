# Installation

Pre-built versions of ShotTrainer are available from the project's
[GitHub Releases](https://github.com/dsgnr/ShotTrainer/releases) page.

Download the package for your operating system and follow the instructions
below.

## Windows

### Installer

1. Download **ShotTrainer-Setup.exe** from the latest release.
2. Run the installer.
3. Follow the on-screen instructions.
4. Launch ShotTrainer from the Start menu.

### Portable version

If you prefer not to install the application:

1. Download **ShotTrainer-Windows.zip**.
2. Extract the archive to any folder.
3. Run **ShotTrainer.exe** from the extracted directory.

## macOS

1. Download **ShotTrainer-macOS.dmg** from the latest release.
2. Open the disk image.
3. Drag **ShotTrainer.app** into your **Applications** folder.
4. Launch ShotTrainer.

The first time the application starts, macOS will request permission to access
the camera and microphone. Both permissions are required for normal operation.

### Gatekeeper warning

ShotTrainer is not currently signed with an Apple Developer ID certificate.

Because of this, macOS may display a warning stating that it cannot verify the
application.

To open the application:

1. Right-click **ShotTrainer.app**
2. Select **Open**
3. Confirm the prompt

macOS remembers this decision, so you only need to do it once.

## Linux

1. Download **ShotTrainer-Linux.tar.gz** from the latest release.
2. Extract the archive:

```bash
tar -xzf ShotTrainer-Linux.tar.gz
```

1. Start the application:

```bash
./ShotTrainer/ShotTrainer
```

### Linux requirements

ShotTrainer requires:

- Access to a camera device (`/dev/video*`)
- A supported audio backend (PipeWire, PulseAudio, or ALSA)
- A working Qt platform plugin

Depending on your distribution and desktop environment, additional packages may
be required.

On some Wayland systems, you may need to install the X11 compatibility plugin if
Qt cannot find a suitable Wayland platform plugin.

## Running from source

If you would like to run ShotTrainer directly from source, install:

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

Clone the repository, then run:

```bash
uv sync
uv run shottrainer
```

For development workflows and contributor setup, see the project's README.

## Hardware requirements

To use ShotTrainer you will need:

- A USB camera (manual focus is recommended)
- A microphone within range of the firing point
- A printed target or marker sheet
- Windows, macOS, or Linux

For information on creating a marker sheet, see
[Printing a marker sheet](printing-targets.md).
