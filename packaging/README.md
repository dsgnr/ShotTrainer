# Desktop packaging

ShotTrainer is packaged by Tauri 2. The application contains a Rust backend and
the compiled Svelte frontend. It does not bundle a Python interpreter.

Install Rust 1.88 or newer, Node.js 26, npm 11, the platform's Tauri desktop
build prerequisites, and OpenCV with its compiler/libclang requirements. System
audio dependencies are also required (including ALSA development libraries on
Linux).

Run from the repository root:

```bash
npm --prefix frontend ci
cargo install tauri-cli --version 2.12.1 --locked
cargo tauri build --features opencv
```

The CLI install is only needed if the required version is absent. Tauri runs the
frontend production build through its configured before-build command.
`src-tauri/tauri.conf.json` owns bundle configuration, icons and platform
settings. Cargo owns the application version. Build output is under Cargo's
`target/release` tree, with bundles produced by Tauri for the host platform.

The OpenCV feature enables real camera and microphone backends. Omitting it
produces a synthetic-device application and is intended for development, not a
real-device release. Test a generated bundle on the target operating system,
including camera/microphone permissions and runtime library availability.
Compilation alone does not validate bundle installation, signing, notarisation,
hardware support or distribution on other platforms.

Keep native library distribution and licensing requirements in mind when
preparing a release. Record actual supported platforms and installation steps in
its release notes. Tauri is the active build path.

See the [native dependency setup](../docs/installation.md) for macOS,
Debian/Ubuntu and Windows requirements.
