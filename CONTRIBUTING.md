# Contributing

Patches, bug reports, target-face submissions and camera test reports are all
welcome.

## Filing issues

The issue templates cover most cases:

- [Bug](.github/ISSUE_TEMPLATE/bug.yml) for things that don't behave as
  expected. Include the platform, the camera, what you saw and what you
  expected.
- [Feature request](.github/ISSUE_TEMPLATE/feature.yml) for new behaviour. Worth
  opening one of these before writing the code so the shape can be discussed
  first.
- [Target face](.github/ISSUE_TEMPLATE/target-face-request.yml) for federation
  faces that aren't in the list yet.

For a possible security issue, email the maintainer rather than filing it
publicly.

## Setting up

The project uses [uv](https://docs.astral.sh/uv/) to manage Python and the
lockfile.

```bash
uv sync
```

That installs runtime and dev dependencies into `.venv/`. Run the app from
source with:

```bash
uv run shottrainer
```

The Makefile wraps the common commands:

```bash
make sync       # install / refresh dependencies
make test       # run pytest
make lint       # ruff check
make format     # ruff format + auto-fixable lints
make run        # launch the app
```

System packages that sometimes need installing alongside `uv sync`:

- macOS: `brew install portaudio` if `sounddevice` fails to install.
- Debian / Ubuntu: `sudo apt install libportaudio2 libegl1 libgl1`.
- Windows: nothing extra. PortAudio ships with the wheel.

## Working on a change

1. Branch off `main`.
2. Write the code. Tests live in `tests/` and run with `make test` or
   `uv run pytest`. The suite uses synthetic camera frames and audio blocks, so
   it runs fine without hardware.
3. Run `make lint` before pushing. `make format` fixes most of what ruff flags.
4. Commit using [conventional commit](https://www.conventionalcommits.org)
   prefixes: `feat:`, `fix:`, `refactor:`, `perf:`, `docs:`, `test:`, `chore:`,
   `ci:`, `build:`. Keep the subject under 70 characters. Use the body for
   anything that isn't obvious from the diff.
5. Open a pull request describing what changed and how it was tested.

A short before/after screenshot or screen capture in the PR description makes
review of UI changes much faster.

## Style

- Code follows the ruff configuration in [`pyproject.toml`](pyproject.toml).
  Line length 100, the `E F W I B UP N SIM RUF` rule sets, `E501` ignored (the
  formatter handles it).
- Plain language in docstrings and comments. The audience is another shooter who
  has dabbled in Python, not a compiler.
- Frozen dataclasses with `slots=True` are the convention for value types.
- Property tests use [Hypothesis](https://hypothesis.works/) and live alongside
  the example-based tests under `tests/`.
- UK spelling.

## Pre-commit hooks

A [pre-commit](https://pre-commit.com/) config ships with the repo. Install the
hooks once and they run on every commit:

```bash
uvx pre-commit install
```

To run them against every file manually:

```bash
uvx pre-commit run --all-files
```

The hooks cover trailing whitespace, end-of-file fixes, ruff lint and ruff
format.

## Documentation

The docs live in [`docs/`](docs/) and build with mkdocs-material:

```bash
make docs-serve     # local preview at http://localhost:8000
make docs-build     # one-off build into site/
```

GitHub Pages publishes the site from
[`.github/workflows/docs.yml`](.github/workflows/docs.yml) on every push to
`main`.

## Tests that need real hardware

The pytest suite avoids real cameras and microphones. For a fix that
specifically depends on hardware (a quirk of a particular USB camera, a
PortAudio issue, anything that runs differently against `cv2.VideoCapture` than
against synthetic frames), describe what was done in the PR rather than adding a
test that requires a device. CI runs without any.

## Releasing

Tagging `vX.Y.Z` triggers
[`.github/workflows/release.yml`](.github/workflows/release.yml). It builds the
macOS DMG, the Windows installer and the Linux tarball, then attaches them to
the GitHub release. Release notes come from the merged pull-request titles since
the previous tag.

## Licence

Contributions land under [GPL-3.0-or-later](LICENCE), the same licence as the
rest of the project.
