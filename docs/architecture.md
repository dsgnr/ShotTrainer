---
description: "Explore ShotTrainer’s Rust and Tauri architecture, from camera capture and optical tracking to audio shot detection, session storage and the desktop interface."
---

# Architecture

ShotTrainer is a Cargo workspace with a Svelte and TypeScript frontend hosted by
Tauri 2. Application processing and persistence run in Rust.

| Component           | Responsibility                                                                       |
| ------------------- | ------------------------------------------------------------------------------------ |
| `crates/tracking`   | Frames, transforms, circle detection, tracking and optional OpenCV capture           |
| `crates/audio`      | CPAL audio input and RMS shot detection                                              |
| `crates/core`       | Scoring, trace buffering, recording, replay lookup, SQLite repository and CSV import/export |
| `crates/settings`   | Preferences, JSON stores, platform paths and target-face catalogue                   |
| `crates/controller` | Device backends, runtime coordination, sessions, previews and event production       |
| `crates/testkit`    | Shared test fixture support                                                          |
| `src-tauri`         | Desktop lifecycle, permissions, updates, commands, events and frame transport                 |
| `frontend`          | Svelte views, state reducers, typed bridge and browser mock                          |

The frontend sends typed commands through its bridge. The Tauri shell converts
wire commands to controller operations and emits state events back to the
frontend. Camera pixels use a separate binary frame channel. The frontend pairs
frame packets with metadata for display. Views render state and dispatch
commands rather than accessing devices or SQLite directly.

The controller owns device lifecycles, recording and replay. Tracking and shot
events share a monotonic time base so recorded trace windows align with shots.
The core crate handles scoring and storage without a UI dependency. Settings and
session schemas have golden fixtures and versioned schema tests.

Without the `opencv` feature the desktop shell selects synthetic backends. With
it, system devices are available, while `--fake-devices` or
`SHOTTRAINER_FAKE_DEVICES=1` selects synthetic mode explicitly. Synthetic data
uses a separate temporary directory. The browser mock is independent of this
Rust device mode and does not use the desktop database. Both modes generate
automatic shots only while a session is recording, with the first shot five
seconds after starting. Camera previews and quiet audio levels continue while
idle or reviewing a session. The synthetic camera stays centred outside
recording. During recording, approaches enter from below the target at six
o’clock and move towards the 10 with varied speed, a wobble and a slower
final approach, entering just below the face. The first approach begins
immediately. Later approaches begin after follow-through and recovery,
without a stationary side-to-side hold at the entry point. Trace rendering uses cubic
curves through the samples to avoid angular joins. Both dev cameras sample at about 60 Hz. The wider synthetic field
of view keeps the larger off-face recoil loop within the camera frame.
The synthetic circle moves opposite to the aim coordinates
to account for the tracker’s camera-to-rifle conversion. Starting recording
resets centroid smoothing so the trace begins at the first recorded aim. Trigger
pull starts a rapid recoil away from the aim point within 15 ms, followed by
an asymmetric loop extending well beyond the face before returning near
the shot, with varied direction, width and shape. Camera movement and
automatic triggers share elapsed recording time, so slow camera updates do
not move the trigger along the approach. Live and replay traces show the configured release window
in yellow and the post-shot window in red. Live samples are recoloured when
the shot is detected.
