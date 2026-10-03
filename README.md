# ShotTrainer

Optical shooting practice with a rifle-mounted camera and microphone.
ShotTrainer tracks a dark circular aiming mark, records hold traces, scores
shots, and saves local sessions for replay and CSV export.

The application is written in Rust with a Tauri 2 desktop shell and a Svelte 5
interface.

## Run from source

Use Rust 1.90 or newer, Node.js 26 and npm 11, plus the native Tauri desktop
prerequisites for your platform. Run all commands from the repository root:

```bash
npm --prefix frontend ci
cargo install tauri-cli --version 2.12.1 --locked
cargo tauri dev
```

Install the CLI only if needed. The default build uses synthetic devices and
keeps their data in a separate temporary directory. To explicitly select them:

```bash
SHOTTRAINER_FAKE_DEVICES=1 cargo tauri dev
```

For real camera and microphone input, install OpenCV, its compiler/libclang
requirements and the platform audio dependencies, then run:

```bash
cargo tauri dev --features opencv
```

For a browser-only mock preview, run `npm --prefix frontend run dev` and open
the URL Vite prints. This mode does not access devices or the desktop database.
Hardware and platform packaging require validation on the intended machine.

## Using the application

Open Preferences using the cog at the bottom of the navigation rail to select
devices and set the measured tracking circle diameter. On Sessions, choose New
session, enter a name and category, and configure the target face, shooting
position, timing windows, shot diameter and series size. Create the session, then
start recording from the target page. Stop recording and select a shot to
inspect its trace. Sessions also offers review, rename, category, delete and CSV
import/export actions. The muted print icon beside the target controls prints
the results. About shows the version, repository and update check. Space toggles
an enabled replay. Up and Down select adjacent shots outside inputs and dialogues.

## Repository layout

- `crates/`: tracking, audio, core processing, settings, controller and test support.
- `src-tauri/`: desktop shell, wire bridge, permissions and frame transport.
- `frontend/`: Svelte interface, typed state and browser mock.
- `testdata/`: compatibility and golden test inputs.
- `docs/`: documentation site.
- `packaging/`: packaging documentation.

## Documentation

[Documentation site](https://dsgnr.github.io/ShotTrainer/) ·
[Installation](docs/installation.md) · [Getting started](docs/getting-started.md) ·
[Architecture](docs/architecture.md) · [Contributing](CONTRIBUTING.md) ·
[Packaging](packaging/README.md)

Licensed under GPL-3.0-or-later. See [LICENCE](LICENCE).
