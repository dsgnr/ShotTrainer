# Contributing

ShotTrainer uses Rust for device processing and persistence, Tauri 2 for the
desktop shell, and Svelte 5 with TypeScript for the interface. Read
[architecture](docs/architecture.md) and [engineering notes](docs/engineering-notes.md)
before changing processing, timing or persistence.

## Set up

Install Rust 1.90 or newer, Node.js 26 and npm 11, and the native Tauri 2
prerequisites for your operating system. Real camera builds additionally need
OpenCV and its compiler/libclang dependencies. Linux audio needs ALSA
development libraries. Run commands from the repository root:

```bash
npm --prefix frontend ci
cargo install tauri-cli --version 2.12.1 --locked
cargo tauri dev
```

The default desktop build uses synthetic devices and a separate temporary data
directory. Use `SHOTTRAINER_FAKE_DEVICES=1 cargo tauri dev` to request synthetic
mode explicitly, or `cargo tauri dev --features opencv` for system backends.
`npm --prefix frontend run dev` starts a browser mock without desktop storage or
hardware access.

## Validate changes

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
npm --prefix frontend run check
npm --prefix frontend test
npm --prefix frontend run build
```

For camera/backend changes, also compile and test the relevant targets with
`--features opencv` where native dependencies are available. Report hardware,
platform and packaging checks separately. Do not infer them from unit tests. Use
temporary directories for tests, never the real application data directory.
Preserve golden fixtures and versioned schema tests when changing data formats.

## Documentation

Each documentation page needs a unique description in YAML front matter. Keep
user instructions aligned with the actual interface and add navigation entries
in `zensical.toml` for new pages. Run the documentation tools with:

```bash
uv tool run --from zensical zensical build --strict
uv run --no-project python scripts/check_docs_seo.py
```

Remove generated `site/` output after validation.

## Changes and pull requests

Keep changes focused. Include regression tests for behaviour changes and update
the relevant documentation. Preserve SQLite, JSON and CSV compatibility unless a
change is deliberate and documented. Use the pull request template, explain what
changed and how it was tested, and report any checks you could not run. Use a
concise commit subject under 70 characters with an appropriate prefix such as
`fix:`, `feat:`, `docs:` or `chore:`.

See the [native dependency setup](docs/installation.md) for macOS, Debian/Ubuntu
and Windows requirements.
