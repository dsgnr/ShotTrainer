# Frontend views Implementation Plan

**Goal:** Build the remaining views of the Svelte front end in `frontend/` on the interfaces the foundation
plan established (stores, bridge, frame sink, shell layout, camera view). The result is a refined port of the
Python interface in `src/shottrainer/ui/`: the same information architecture, controls and copy, drawn with the
already-refined theme tokens, with visible focus and screen-reader labels. Each task is test-first and
mutation-proven, with one Conventional Commit per task.

**Baseline:** branch `feat/rust-rewrite`, continuing after the foundation plan's eight commits (HEAD `58ba44e`).

**Scope:** target model and target view, hero stats, session controls, shot list, replay controls,
preferences dialog, session browser, plus the pop-out camera window, zoom controls and marker sheet.

## Global Constraints

- Work only in `/Users/Dan.hand/dev/ShotTrainer` on branch `feat/rust-rewrite`.
- Do not edit the Python code in `src/shottrainer/` or `tests/`. It is the behavioural reference.
- Conventional Commits, single line, lowercase imperative, at most 72 characters, no scope, body or trailers.
  Never use `--no-verify`.
- UK English in prose, comments and user-facing copy. Identifiers mirroring the wire format or external APIs
  keep their spelling.
- No semicolons, unnecessary colons or em dashes in prose or comments. Comments only where code cannot say it.
- Node 26 and npm 11. Dependencies pinned, nothing added unless a task says so.
- Gates per task, from the worktree root: `npm --prefix frontend run check`, `npm --prefix frontend test`,
  `npm --prefix frontend run build`, plus `cargo fmt --all --check` (Rust is otherwise untouched). Never
  `--all-features`, never `--no-verify`.
- Every new test must be mutation-provable. Break the line a new test guards once, confirm the test fails,
  restore it, record both runs.

## Interfaces consumed (from the foundation plan)

- `src/lib/wire/types.ts`: all `Wire*` types, `F64`, `Pair`.
- `src/lib/wire/numbers.ts`: `finitePair`, `finiteOr`, `isFiniteNumber`.
- `src/lib/wire/samples.ts`: `SAMPLE_EVENTS`, `SAMPLE_PREFERENCES`, `SAMPLE_COMMANDS`.
- `src/lib/stores/*`: `AppState` and the per-store state and reducers.
- `src/lib/bridge`: `Bridge`, `createBridge`.
- `src/lib/frames/sink.ts`: `FrameSink`.
- `src/components/AppShell.svelte`: `side` and `target` snippets, already wired for `header`/`camera`/`status`.
- `src/styles/theme.css`: `--target-*`, `--trace-*`, `--panel`, `--text`, `--accent`, etc.

## Tasks

### Task 1: Target model and geometry

Port `target_view.py`'s non-painting logic into testable units.

- Create `src/lib/target/geometry.ts`: `targetScale(size, extentMm)`, `mmToView(point, centre, scale)`,
  `extentForRings(rings)` (max ring radius x 1.15, default when empty), zoom step helpers
  (`ZOOM_MIN_MM=5`, `ZOOM_MAX_MM=500`, logarithmic `extentFromRatio`/`ratioFromExtent`, matching
  `zoom_controls.py`), and the wheel factor (0.9 in, 1.1 out).
- Create `src/lib/target/model.ts`: `TargetModel` holding the live trace (capacity 600, clip at 4x extent),
  the three phase polylines (approach/release/follow) split by `releaseIndex`/`shotIndex`, shots, selected
  shot, live aim, playhead, hold zone, shot diameter, isolate-selected flag, and a `version` counter bumped
  on every mutation so the canvas redraws. Methods mirror `target_view.py`:
  `appendTracePoint`, `setTrace`, `setTraceSegments`, `setPlayhead`, `setHoldZone`, `clearTrace`,
  `setShots`, `setSelectedShot`, `setIsolateSelectedShot`, `setShotDiameter`, `setExtent`.
- Test `src/lib/target/geometry.test.ts` and `model.test.ts`. Cover: extent from rings and default; log zoom
  round-trips at min/mid/max; wheel factor; trace capacity holds at 600 dropping the oldest; a point beyond 4x
  extent is dropped and does not break the trace; the boundary sample belongs to the new phase; isolate
  suppresses appends; playhead clipping of the three polylines; version bumps.
- Mutations: change capacity 600 to 6000 (capacity test fails); change clip `4` to `400` (clip test fails);
  change the boundary comparison `i > shot` to `i >= shot` (phase-boundary test fails).
- Commit: `feat: model the target trace and its zoom geometry`.

### Task 2: Target drawing and the target view component

- Create `src/lib/target/draw.ts`: `drawTarget(ctx, width, height, model, rings)` painting the dark face,
  rings and labels, dashed crosshair, hold zone, shots (isolate + playhead gating), the three-colour joined
  trace (one path, no gap at boundaries), and the live aim dot. Uses `--target-*`/`--trace-*` tokens read from
  the canvas's computed style. Pure given a context, so it is tested against a recording fake 2D context.
- Create `src/components/TargetView.svelte`: a device-pixel-ratio canvas that redraws on `model.version`,
  rings, or size change, with a wheel handler calling `model.setExtent` and emitting the new extent. Labelled
  group, canvas `aria-hidden`.
- Create `src/components/ZoomControls.svelte` from `zoom_controls.py`: zoom out/in buttons, a log slider, an
  `N mm` readout, two-way bound to the extent.
- Test `src/lib/target/draw.test.ts` with a fake context recording calls. Cover: rings drawn at the right
  radii; trace is a single stroked path per phase; live aim hidden during replay/isolate; hold zone drawn only
  when set; shots gated by playhead when isolating.
- Mutations: skip the live-aim replay guard (hidden-in-replay test fails); draw each phase as separate
  polylines with a gap (joined-path test fails).
- Wire `TargetView` + `ZoomControls` into `App.svelte`'s `target` snippet, driven by a `TargetModel` built in
  `main.ts` and fed from `app.camera`/`app.shots`/`app.replay` via a small effect.
- Commit: `feat: draw the target with its trace and zoom`.

### Task 3: Hero stats

- Port `hero_stats.py`. Create `src/lib/stats/hero.ts`: pure derivations of the four figures (total score,
  group size with mean-radius tooltip, hold tremor, time-on-target with the diagnostic-ring caption) from
  `WireShotStats`, `WireTraceStats`, total score and rings. The scoring/stats come from the controller events,
  so this formats rather than recomputes, matching the wire contract.
- Create `src/components/HeroStats.svelte` rendering the four `analysisCard` figures with captions and
  subcaptions.
- Test `hero.ts`: dash when empty; `g`-format total; `N shots` fallback when total <= 0; `X.X mm` group with
  tooltip text; tremor formatting; time-on-target percentage and caption naming the diagnostic ring.
- Mutations: change the `<= 0` total guard to `< 0` (fallback test fails); drop the diagnostic-ring caption
  (caption test fails).
- Commit: `feat: show the headline shot and hold figures`.

### Task 4: Session controls

- Port `session_controls.py`. Create `src/components/SessionControls.svelte`: name field, category select
  (categories from a new `src/lib/wire/categories.ts` mirroring `SESSION_CATEGORIES`/`DEFAULT_SESSION_CATEGORY`
  in `sessions/models.py`), a primary Start/Stop button that swaps label and variant, a Clear shots button,
  and a summary line. Buttons disabled while recording as Python does. Emits commands through the bridge.
- Test `src/lib/wire/categories.ts` and a small `session-controls` logic module for the primary-button label
  and the disabled set, derived from `WireSessionState`.
- Mutations: invert the active-state label (Start/Stop test fails); drop the disabled-while-recording rule.
- Commit: `feat: add the session start, stop and clear controls`.

### Task 5: Shot list

- Port `shot_list.py`. Create `src/lib/shots/rows.ts`: `shotRows(shots)` producing per-row number, score or
  dash, and the `+5.1, +5.1 mm` offset or `Position unavailable`. Create `src/components/ShotList.svelte`:
  a scrollable, keyboard-navigable list (Up/Down step, Delete/Backspace requests deletion), empty-state copy,
  selection emitting `selectShot`, clicking a row scrubs replay.
- Test `rows.ts`: offset formatting with sign and one decimal; dash score; unavailable position; step logic
  (first on down from none, last on up from none, clamped).
- Mutations: change the offset precision; change the step clamp.
- Commit: `feat: list each shot with its score and offset`.

### Task 6: Replay controls

- Port `replay_controls.py`. Create `src/lib/replay/format.ts`: `formatSeconds(ms)` (`M:SS.t`) and the
  `offset / duration` time label. Create `src/components/ReplayControls.svelte`: reset and play/pause buttons
  (glyph and label swap on playing), a scrubber bound to progress, the time label, enabled only when a window
  is loaded. Space toggles play/pause. Emits `replayPlay`/`replayPause`/`replayReset`/`replaySeek`.
- Test `format.ts`: `0:00.0`, rounding to tenths, negative clamped, minutes rollover.
- Mutations: change the tenths rounding; drop the negative clamp.
- Commit: `feat: add the replay transport and scrubber`.

### Task 7: Preferences dialog

- Read `preferences_dialog.py` and `target_face_preview.py` first. Create `src/components/PreferencesDialog.svelte`
  mirroring its fields (camera, rotation, flips, brightness/contrast with the preview, audio device and gain,
  detection thresholds and windows, target face and shot diameter, tracking region, circle diameter, trace
  inversions, hold-zone toggle). Values are the finite `WirePreferences`, sent back unchanged via
  `setPreferences`; the live preview uses `beginPreview`/`previewCamera`/`previewImage`/`previewTransform`/
  `endPreview` and the auto-optimise flow.
- Create `src/lib/preferences/form.ts`: pure mapping between `WirePreferences` and form field descriptors,
  plus validation ranges mirroring `preferences.rs` so the dialog cannot send an out-of-range value.
- Test `form.ts`: round-trip of `SAMPLE_PREFERENCES`; each range clamp; the camera-null case.
- Mutations: widen a clamp range; break the null-camera mapping.
- Commit: `feat: edit preferences with a live camera preview`.

### Task 8: Session browser, marker sheet and camera pop-out

- Port `session_browser.py`. Create `src/lib/sessions/rows.ts`: the meta line (`DD Mon YYYY, HH:MM · N shots ·
  Xm Ys`/`in progress`) and the score badge (`N pts` when score > 0), plus the in-memory search and category
  filter. Create `src/components/SessionBrowser.svelte`: list, search field, category filter, Open/Rename/
  Category/Delete/Export actions bound to selection, empty and no-match states, loading state. Emits
  `listSessions`/`openSession`/`renameSession`/`setSessionCategory`/`deleteSession`/`exportSession`.
- Port `marker_sheet.py` into `src/components/MarkerSheet.svelte` (the printable shot sheet) and
  `camera_popout.py` into `src/components/CameraPopout.svelte` reusing `CameraView` with the same props.
- Test `src/lib/sessions/rows.ts`: meta formatting, duration cases, score badge, filter by name and category.
- Mutations: change the duration format; drop the category filter term.
- Commit: `feat: browse sessions and pop out the camera`.

### Task 9: Documentation

- Update `docs/architecture.md` and `README.md` to describe the completed views, in UK English and the project
  tone (no semicolons, unnecessary colons or em dashes, state facts once). Remove the "does not yet offer every
  view" qualifier added in the foundation plan if every view is now present.
- Commit: `docs: describe the completed front end views`.
