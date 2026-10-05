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

SQLite migrations, JSON preferences, target-face definitions and session export files are
data formats. Golden fixtures and versioned database schemas are test inputs.
Check existing migrations and fixture tests before changing
formats. Session export files carry a `version` field, which the importer
checks.

Session rows store pre-shot, post-shot, release-window and refractory timings,
shot diameter and the target profile. Schema version 4 adds the numeric settings
without replacing existing rows. Older sessions retain their target profile and
receive standard defaults for settings that were never stored.

Shooting position is stored with each session and defaults to standing for
older records. It is excluded from the global settings file. Global JSON
preferences retain their persisted keys, but session controls do
not update those values.

Schema version 6 stores the session series size and each shot's series index.
Older shots are grouped chronologically into series of 10. Membership is
stored independently of list position so deletion cannot move shots between
series. The recording counter advances even when a shot cannot be saved.

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

The nearest trace sample is selected without a maximum age limit. A shot after
tracking loss can therefore receive a position and score from an earlier
sample. A timing policy must preserve timestamp alignment and cover stale,
missing and newly reacquired samples. See [troubleshooting](troubleshooting.md)
for the user-facing limitation.
