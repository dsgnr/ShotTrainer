---
title: "Install on Windows, macOS and Linux"
description: "Build and run ShotTrainer from source with Rust, Tauri and Svelte, including native dependencies and synthetic or real-device modes."
---

# Installation

The current application runs from the Rust workspace. It does not require a
Python runtime. Install Rust with Cargo (Rust 1.88 or newer), Node.js 26 and npm
11. Install the native desktop prerequisites for Tauri 2 on your platform: a
C/C++ toolchain and platform webview libraries. Linux also needs the ALSA
development libraries for audio.

 On macOS, install Xcode Command Line Tools and use:

```bash
brew install opencv pkgconf
```

On Debian/Ubuntu, the native dependencies used by the Rust workflow are:

```bash
sudo apt-get update
sudo apt-get install -y libopencv-dev clang libclang-dev libasound2-dev \
  pkg-config libwebkit2gtk-4.1-dev libxdo-dev libssl-dev librsvg2-dev
```

On Windows, follow the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)
for the Microsoft C++ build tools and WebView2, and the
[OpenCV Rust crate setup instructions](https://github.com/twistedfall/opencv-rust#installation)
for native OpenCV and binding dependencies. These dependency steps do not
establish successful packaging or hardware support on that platform.

From the repository root:

```bash
npm --prefix frontend ci
cargo install tauri-cli --version 2.12.1 --locked
cargo tauri dev
```

The CLI install is only needed if that version is not already installed. The
last command starts the desktop application with synthetic devices because the
default build omits OpenCV. To explicitly request synthetic devices:

```bash
SHOTTRAINER_FAKE_DEVICES=1 cargo tauri dev
```

Synthetic sessions and settings live under `ShotTrainer-fake-devices` in the
system temporary directory, separate from real-device data.

For real camera and microphone input, install OpenCV and the native compiler and
libclang dependencies needed by its Rust bindings, then run:

```bash
cargo tauri dev --features opencv
```

For a browser-only interface preview:

```bash
npm --prefix frontend run dev
```

Open the URL Vite prints. The browser uses a mock bridge. It does not capture
hardware or access the desktop session database. See [setup](setup.md) for
physical setup and [troubleshooting](troubleshooting.md) for device problems.
