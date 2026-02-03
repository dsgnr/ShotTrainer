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
replays the trace around each shot. Calibration uses an A4 sheet and survives
restarts. Preferences include camera rotation and mirroring, audio gain and
sensitivity, target face selection, and pre/post-shot windows. The stats
panel shows shot group metrics live, plus hold tremor, trace length, and
time-in-ring percentages over the pre-shot window of the selected shot. See
[`docs/troubleshooting.md`](docs/troubleshooting.md) for the rough edges and
[`docs/engineering-notes.md`](docs/engineering-notes.md) for trade-offs.

## Requirements

- Python 3.11 or newer.
- A webcam, ideally with manual focus and decent zoom.
- A microphone within hearing range of the firing point.
- Operating system: Windows, macOS, or Linux.

On macOS you will be prompted for camera and microphone permissions the first
time the app runs. On Linux the user must be in the appropriate `video` and
`audio` groups, or have access to `/dev/video*` and ALSA/PulseAudio.

## Development setup

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

## Running

```bash
uv run shottrainer
```

Or, if you've activated the `.venv` manually:

```bash
shottrainer
# or: python -m shottrainer.app.main
```

## Development workflow

The Makefile wraps the common commands:

```bash
make sync       # install / refresh dependencies
make test       # run pytest
make lint       # ruff check
make format     # ruff format + auto-fixable lints
make run        # launch the app
make package    # PyInstaller build, see packaging/README.md
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
