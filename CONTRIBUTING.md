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

## Rust workspace

The Cargo workspace under `crates/` needs a stable Rust toolchain with `clippy`
and `rustfmt`. From the repository root:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

Run `cargo fmt --all` to apply formatting. The [rust workflow](.github/workflows/rust.yml)
runs the same three commands on Linux, macOS and Windows, so avoid tests that
depend on POSIX paths, file permissions or the platform clock resolution.

The `tracking` crate has an optional `opencv` feature that the commands above
do not build. It needs OpenCV 4 or 5 and libclang. On macOS run
`brew install opencv pkgconf`. On Debian and Ubuntu run
`sudo apt-get install libopencv-dev clang libclang-dev pkg-config`. Then:

```bash
cargo clippy -p shottrainer-tracking --features opencv --all-targets -- -D warnings
cargo test -p shottrainer-tracking --features opencv
```

The CI job for these is best effort and is not required to pass.

Golden fixtures are regenerated from the Python code with
`uv run python scripts/generate_golden.py <name>`. The crate layout, fixtures
and compatibility checks are described in the
[architecture notes](docs/architecture.md#rust-workspace).

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

The docs live in [`docs/`](docs/) and build with Zensical:

```bash
make docs-serve     # local preview at http://localhost:8000
make docs-build     # one-off build into site/
```

Give each page a unique `description` in its YAML front matter. Use `title`
when a more descriptive search title is needed. The shared template generates
Open Graph and Twitter preview metadata, and Zensical supplies canonical URLs
and the sitemap. `make docs-build` and CI validate the generated metadata and
check that local images, videos and posters exist with `scripts/check_docs_seo.py`.

The [docs workflow](.github/workflows/docs.yml) builds and validates the site
on pull requests. GitHub Pages publishes it after a successful build on `main`;
pull requests do not receive deployment permissions.

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
