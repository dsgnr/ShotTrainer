---
description: "Explore ShotTrainer’s Rust and Tauri architecture, from camera capture and optical tracking to audio shot detection, session storage and the desktop interface."
---

# Architecture

ShotTrainer is a Cargo workspace with a Svelte and TypeScript frontend hosted by
Tauri 2. All application processing and persistence run in Rust. Python is used
only by documentation tooling. There is no Python application runtime.

| Component           | Responsibility                                                                       |
| ------------------- | ------------------------------------------------------------------------------------ |
| `crates/tracking`   | Frames, transforms, circle detection, tracking and optional OpenCV capture           |
| `crates/audio`      | CPAL audio input and RMS shot detection                                              |
| `crates/core`       | Scoring, trace buffering, recording, replay lookup, SQLite repository and CSV export |
| `crates/settings`   | Preferences, JSON stores, platform paths and target-face catalogue                   |
| `crates/controller` | Device backends, runtime coordination, sessions, previews and event production       |
| `crates/testkit`    | Shared test fixture support                                                          |
| `src-tauri`         | Desktop lifecycle, permissions, commands, events and frame transport                 |
| `frontend`          | Svelte views, state reducers, typed bridge and browser mock                          |

The frontend sends typed commands through its bridge. The Tauri shell converts
wire commands to controller operations and emits state events back to the
frontend. Camera pixels use a separate binary frame channel. The frontend pairs
frame packets with metadata for display. Views render state and dispatch
commands rather than accessing devices or SQLite directly.

The controller owns device lifecycles, recording and replay. Tracking and shot
events share a monotonic time base so recorded trace windows align with shots.
The core crate handles scoring and storage without a UI dependency. Settings and
session schemas retain compatibility fixtures from the previous implementation.
Those fixtures do not require the old runtime.

Without the `opencv` feature the desktop shell selects synthetic backends. With
it, system devices are available, while `--fake-devices` or
`SHOTTRAINER_FAKE_DEVICES=1` selects synthetic mode explicitly. Synthetic data
uses a separate temporary directory. The browser mock is independent of this
Rust device mode and does not use the desktop database.
