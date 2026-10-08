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

JSON preferences, target-face definitions, session export files and the session
database are data formats. Golden fixtures are test inputs. Check the fixture
tests before changing a format. Session export files carry a `version` field,
which the importer checks.

The session database is created from a single layout and records its schema
version in `schema_meta`. A database stamped with any other version is refused
and left unchanged. The app has no migrations, so a layout change needs a new
version number and a decision on how existing data is carried over.

Session rows store pre-shot, post-shot, release-window and refractory timings,
shot diameter, shooting position, series size and the target profile. Each shot
stores its series index. Membership is stored independently of list position so
deletion cannot move shots between series. The recording counter advances even
when a shot cannot be saved.

Shooting position is excluded from the global settings file. Global JSON
preferences retain their persisted keys, but session controls do not update
those values.

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

`ShotCoordinator::handle_shot` maps a shot to the nearest trace sample only when
that sample lies within `max_sample_gap_ms` of the shot (250 ms by default).
Beyond that the shot has no sample and `score_for` returns an empty score.
`TraceBuffer::nearest` has no age limit of its own, so its golden cases are
unchanged. The `handle_shot` golden cases run with an unbounded gap, and the
limit has its own test. See [troubleshooting](troubleshooting.md) for the
user-facing behaviour.
