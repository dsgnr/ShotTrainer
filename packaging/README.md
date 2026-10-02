# Desktop packaging

ShotTrainer is packaged by Tauri 2. The application contains a Rust backend and
the compiled Svelte frontend. It does not bundle a Python interpreter.

Install Rust 1.90 or newer, Node.js 26, npm 11, the platform's Tauri desktop
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

## Signed updates

The app checks the stable release’s `latest.json` on GitHub. Its verification
key is configured in `src-tauri/tauri.conf.json`. Keep the matching private key
and password outside the repository and back them up securely. Replacing the
public key prevents existing installations from accepting new updates signed
with a different key.

Configure the GitHub Actions repository secrets `TAURI_SIGNING_PRIVATE_KEY`
with the encrypted private key contents and
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD` with its password. The release workflow
uses them to sign updater bundles. It builds from a version tag, checks that
the tag matches Cargo, and uploads bundles, signatures and `latest.json` to a
draft release. Publish the draft after testing the bundles. The updater only
checks the latest public stable release.

For a local signed build, supply those environment variables and run:

```bash
cargo tauri build --features opencv --config src-tauri/tauri.release.conf.json
```

Ordinary development and package builds do not use the release configuration
and do not require signing credentials. Linux package installations update
manually. AppImages, macOS bundles and Windows installers support in-app
updates. Updater signatures do not replace platform code signing or macOS
notarisation.
