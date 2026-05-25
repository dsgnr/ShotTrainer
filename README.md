# ShotTrainer

ShotTrainer is a DIY hold-tracking and shot-scoring tool for shooting
practice. You bring your own camera and microphone, mount the camera
to your rifle's barrel or stock, and point it at a printed paper
target. As you aim around the target, the camera sees the target drift
through its frame, and ShotTrainer turns that drift into your rifle's
hold trace. The microphone picks up the shot, the trace freezes around
it, and the hit is marked on the digital target.

Useful for:

- Air rifle and air pistol dry-fire and live-fire practice.
- Smallbore (.22) practice at indoor and outdoor ranges.
- Coaching feedback on hold stability, follow-through and trigger
  release.
- Recording groups and shot timing for review and export.

Inspired by commercial optical trainers. Runs on Windows, macOS and Linux.

It is a personal/hobby project, not a product, and makes no accuracy
guarantees. See [`docs/accuracy.md`](docs/accuracy.md) for what is and
isn't achievable with this kind of setup, and
[`docs/cameras.md`](docs/cameras.md) for success and failure stories
with various cameras people have tried.

## Contents

- [What it does](#what-it-does)
- [How it's set up](#how-its-set-up)
- [Documentation](#documentation)
- [Installing](#installing)
  - [Windows](#windows)
  - [macOS](#macos)
  - [Linux](#linux)
- [Running](#running)
  - [Keyboard shortcuts](#keyboard-shortcuts)
- [Status](#status)
- [Requirements](#requirements)
- [Development](#development)
  - [Setup](#setup)
  - [Workflow](#workflow)
  - [Pre-commit hooks (optional)](#pre-commit-hooks-optional)
  - [Project layout](#project-layout)
- [Calibration](#calibration)
- [Packaging](#packaging)
- [Troubleshooting](#troubleshooting)
- [Licence](#licence)

## What it does

- Live preview of what the barrel-mounted camera sees.
- Calibration to convert pixels to millimetres on the target.
- Audio shot detection from a microphone.
- Automatic ring scoring against your selected target face.
- Records the rifle's hold trace continuously while practising.
- Stores sessions and shots in a local SQLite database.
- Lets you replay the trace around each shot.

## How it's set up

1. Print and place a paper target at your shooting position.
2. Mount a small USB webcam to the rifle barrel or stock so it looks
   forward at the target.
3. Calibrate once: ShotTrainer measures a printed circle of known
   diameter and builds a millimetres-per-pixel mapping for the target
   plane.
4. Aim, shoot, repeat. The trace and hit position appear in real time.

## Documentation

- [Setup and camera alignment](docs/setup.md)
- [How tracking works](docs/how-tracking-works.md)
- [Accuracy and target sizing](docs/accuracy.md)
- [Cameras tested](docs/cameras.md)
- [Using federation targets (NSRA, ISSF)](docs/provided-targets.md)
- [Architecture](docs/architecture.md)
- [Calibration](docs/calibration.md)
- [Engineering notes](docs/engineering-notes.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Releases and upgrades](docs/releases.md)

The same docs are published as a site at
<https://dsgnr.github.io/ShotTrainer/> via GitHub Pages.

## Installing

Pre-built downloads are attached to each tagged release on
[GitHub releases](https://github.com/dsgnr/ShotTrainer/releases).
Pick the one for your platform.

### Windows

1. Download `ShotTrainer-Setup.exe` from the latest release.
2. Run it and follow the installer.
3. Launch ShotTrainer from the Start menu.

A portable `ShotTrainer-Windows.zip` is also published. Unzip
anywhere and run `ShotTrainer.exe` from the unpacked folder if you'd
rather not install.

### macOS

1. Download `ShotTrainer-macOS.dmg` from the latest release.
2. Open the .dmg and drag **ShotTrainer.app** into your Applications
   folder.
3. The first launch will prompt for camera and microphone access. Allow
   both.

The app isn't yet signed by an Apple Developer ID, so on first launch
macOS may show "ShotTrainer can't be opened because Apple cannot check
it for malicious software". Right-click the app and pick **Open** to
override. MacOS remembers the choice from then on.

### Linux

1. Download `ShotTrainer-Linux.tar.gz` from the latest release.
2. Extract somewhere convenient: `tar -xzf ShotTrainer-Linux.tar.gz`.
3. Run `./ShotTrainer/ShotTrainer`.

You'll need access to `/dev/video*` (usually via the `video` group)
and a working PortAudio install (PulseAudio or ALSA). On Wayland you
may need the X11 plugin if PySide6 cannot find a working Wayland
platform plugin on your system.

## Running

```bash
shottrainer
```

When running from source via `uv`:

```bash
uv run shottrainer
```

### Keyboard shortcuts

- `Ctrl+S` (`Cmd+S` on macOS): start or stop the current session.
- `Ctrl+R` (`Cmd+R`): clear the displayed shots (only when not recording).
- `Space`: play / pause replay when a shot is selected.

## Status

The app boots, runs the live preview, detects shots, records sessions, and
replays the trace around each shot. Calibration uses a printed circle of
known diameter and survives restarts. Preferences include camera rotation
and mirroring, audio gain and sensitivity, target face selection, and
pre/post-shot windows. The stats
panel shows shot group metrics live, plus hold tremor, trace length, and
time-in-ring percentages over the pre-shot window of the selected shot. See
[`docs/troubleshooting.md`](docs/troubleshooting.md) for the rough edges and
[`docs/engineering-notes.md`](docs/engineering-notes.md) for trade-offs.

## Requirements

- Python 3.11 or newer (only for source installs, not for the packaged builds).
- A webcam, ideally with manual focus and decent zoom.
- A microphone within hearing range of the firing point.
- Operating system: Windows, macOS, or Linux.

On macOS you will be prompted for camera and microphone permissions the first
time the app runs. On Linux the user must be in the appropriate `video` and
`audio` groups, or have access to `/dev/video*` and ALSA/PulseAudio.

## Development

### Setup

We use [uv](https://docs.astral.sh/uv/) to manage Python and dependencies.
If you don't already have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # macOS / Linux
# or: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  on Windows
```

Then, from the repo root:

```bash
uv sync                  # install runtime + dev dependencies in .venv/
```

`uv sync` creates a virtual environment in `.venv/` and resolves
everything from `uv.lock` so you get a reproducible install. To add
or upgrade a dependency edit `pyproject.toml` and run `uv lock`.

If `sounddevice` fails to install you may need PortAudio. On macOS:
`brew install portaudio`. On Debian/Ubuntu: `sudo apt install libportaudio2`.

Run from source with:

```bash
uv run shottrainer
```

Or, if you've activated `.venv` manually:

```bash
shottrainer
# or: python -m shottrainer.app.main
```

### Workflow

The Makefile wraps the common commands:

```bash
make sync       # install / refresh dependencies
make test       # run pytest
make lint       # ruff check
make format     # ruff format + auto-fixable lints
make run        # launch the app
make package    # PyInstaller build, see packaging/README.md
make dmg        # macOS only: build dist/ShotTrainer-macOS.dmg
make installer  # Windows only: build dist/ShotTrainer-Setup.exe
```

Run them directly with `uv run` if you'd rather not use Make.

A typical change looks like:

1. `uv sync` to make sure your env matches the lockfile.
2. Make your edit. Add or update tests next to the code where it makes
   sense.
3. `make test` and `make lint` before committing.
4. Commit with conventional commit messages (`feat: ...`, `fix: ...`,
   `refactor: ...`, `docs: ...`, `test: ...`, `chore: ...`).

The image and audio tests use synthetic data and do not require a
physical camera or microphone, so they are safe to run anywhere.

### Pre-commit hooks (optional)

Install [pre-commit](https://pre-commit.com/) and the hooks defined in
`.pre-commit-config.yaml` to catch trailing whitespace, formatting drift,
and lint regressions before they land:

```bash
uvx pre-commit install
```

Hooks then run on every `git commit`. Run them manually with
`uvx pre-commit run --all-files`.

### Project layout

```
src/shottrainer/
    app/         entry point, controller, settings, paths
    ui/          PySide6 widgets and dialogs
    tracking/    camera capture, target detection, calibration
    audio/       microphone input and shot detection
    sessions/    database, models, repository
    replay/      trace replay logic
    services/    coordination between subsystems
docs/            engineering notes, accuracy notes, troubleshooting
packaging/       PyInstaller spec and platform notes
tests/           pytest suite
```

See [`docs/architecture.md`](docs/architecture.md) for a longer description.

## Calibration

You aim a printed circle of known diameter at the camera. The application
detects the circle and uses its physical size to compute a millimetres-per-
pixel ratio, with the circle's centre as the image-space origin. The
result is stored with the session so that hits can be reported in
millimetres relative to the centre of the target.

Calibration must be redone if the camera or target moves. See
[`docs/calibration.md`](docs/calibration.md) for the workflow.

## Packaging

PyInstaller specs live under `packaging/`. The README in that directory
covers platform-specific notes (PySide6 plugins, OpenCV bundling, signing,
DMG and Inno Setup installer).

## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for the common
issues with cameras, microphones, calibration, and replay.

## Licence

GPL-3.0-or-later. See [`LICENCE`](LICENCE).
