---
description: "Read the design decisions behind ShotTrainer’s target detection, optical tracking and shot analysis, including experiments and implementation trade-offs."
---

# Engineering notes

The current implementation uses Rust for device processing, application
coordination and persistence, with Tauri hosting the Svelte interface. Keep
hardware operations in backend crates and communicate with views through typed
commands, events and the frame channel.

## Timing and missing data

Shot registration, trace recording and replay use a shared monotonic time base.
Preserve timestamp meaning when changing buffering, audio callbacks or replay
windows. Unavailable positions must remain distinguishable from valid zero
coordinates. The frontend filters unavailable points when drawing traces.

## Compatibility

SQLite migrations, JSON preferences, target-face definitions and CSV exports are
compatibility surfaces. Golden fixtures and legacy database schemas remain as
test inputs. Check existing migrations and fixture tests before changing
formats. CSV output preserves established column order, formatting and CRLF line
endings.

Session rows store pre-shot, post-shot, release-window and refractory timings,
shot diameter and the target profile. Schema version 4 adds the numeric settings
without replacing existing rows. Older sessions retain their target profile and
receive standard defaults for settings that were never stored. Global JSON
preferences retain their legacy keys for compatibility, but session controls do
not update those values.

## Devices and preview

System camera capture is feature-gated behind OpenCV. Synthetic backends allow
repeatable desktop tests without hardware and use isolated temporary storage.
Preference preview has a lifecycle separate from committing saved settings.
Retain cancellation and device cleanup behaviour when changing it.

## Validation

Run Rust formatting, Clippy and workspace tests, then frontend checking, tests
and production build. The browser mock checks interface behaviour but cannot
validate the Tauri bridge, device permissions or actual capture. Compilation
with OpenCV does not establish real camera or microphone behaviour. Packaging
and hardware checks must be reported separately for each platform tested.

See [contributor
instructions](https://github.com/dsgnr/ShotTrainer/blob/main/CONTRIBUTING.md)
for commands, and [architecture](architecture.md) for crate ownership.

## Shot registration after tracking loss

The controller can map and score a shot using an earlier valid tracking sample
when the target is subsequently lost. It does not currently enforce a maximum
sample age for that mapping. A displayed score therefore does not prove that the
target was being tracked at the instant of the shot. Check the camera and
tracking status, restore a clear target view, and treat shots recorded during
tracking loss as unreliable. This inherited behaviour needs a separate timing
policy and regression tests before it is changed.
