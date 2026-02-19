# ShotTrainer

A desktop application for optical shooting practice. It uses a camera to track
the aiming point on a paper target, detects shots from audio, marks the hit
position, and records the full aiming trace for later replay.

This is an open project for optical shooting trainers. It is not a
commercial product and makes no accuracy guarantees. See
[`docs/accuracy.md`](docs/accuracy.md) for an honest discussion of what is and
isn't achievable with a webcam.

## What it does

- Live camera preview with target detection.
- Calibration to convert pixels to millimetres on the target.
- Audio shot detection from a microphone.
- Records the aiming trace continuously while practising.
- Stores sessions and shots in a local SQLite database.
- Lets you replay the trace around each shot.

## Status

The app boots, runs the live preview, detects shots, records sessions, and
replays the trace around each shot. Calibration uses an A4 sheet. The audio
threshold is exposed in preferences. See [`docs/troubleshooting.md`](docs/troubleshooting.md)
for the rough edges and [`docs/engineering-notes.md`](docs/engineering-notes.md)
for trade-offs.

## Requirements

- Python 3.11 or newer.
- A webcam, ideally with manual focus and decent zoom.
- A microphone within hearing range of the firing point.
- Operating system: Windows, macOS, or Linux.

On macOS you will be prompted for camera and microphone permissions the first
time the app runs. On Linux the user must be in the appropriate `video` and
`audio` groups, or have access to `/dev/video*` and ALSA/PulseAudio.

## Installing for development

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

If `sounddevice` fails to install you may need PortAudio. On macOS:
`brew install portaudio`. On Debian/Ubuntu: `sudo apt install libportaudio2`.

## Running

```bash
shottrainer
```

Or:

```bash
python -m shottrainer.app.main
```

## Running tests

```bash
pytest
```

The image and audio tests use synthetic data and do not require a physical
camera or microphone.

## Linting and formatting

```bash
ruff check .
ruff format .
```

## Project layout

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

You aim a printed A4 sheet with a black circle at the camera. The application
detects the sheet (or the circle) and uses its known physical size to compute
a pixels-per-millimetre ratio. The result is stored with the session so that
hits can be reported in millimetres relative to the centre of the target.

Calibration must be redone if the camera or target moves. See
[`docs/calibration.md`](docs/calibration.md) for the workflow.

## Packaging

PyInstaller specs live under `packaging/`. The README in that directory
covers platform-specific notes (PySide6 plugins, OpenCV bundling, signing).

## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for the common
issues with cameras, microphones, calibration, and replay.

## Licence

GPL-3.0-or-later. See [`LICENCE`](LICENCE).
