# Architecture

ShotTrainer is split into small modules with clear responsibilities. Each
subsystem can be tested in isolation, and Qt signals connect them at the edges.

## High level

```
camera + tracking ----> tracking samples (timestamp, x_mm, y_mm, ...)
                              |
audio shot detector ---->  shot events  (timestamp, audio_level)
                              |
                  shot coordinator (in services/)
                              |
                  session recorder (in services/)
                              |
                  SQLite via SQLAlchemy
                              |
                            UI
```

The UI never talks to the camera or audio backends directly. It listens to
high level signals from the services layer (new tracking sample, shot
detected, session saved) and reads from the repository when displaying past
sessions.

## Threads

Camera capture and audio capture each run on their own thread. Tracking and
shot detection happen close to the capture loop to keep latency low. Results
are pushed back to the UI thread via Qt's queued signal/slot connections so
nothing blocks the event loop.

## Modules

- `tracking/` Camera capture, target detection, calibration, coordinate
  conversion. Pure functions where possible so they can be tested with
  synthetic images.
- `audio/` Microphone input and shot detection. Configurable threshold and
  refractory window.
- `sessions/` SQLAlchemy models, repository, schema migrations.
- `services/` Coordinates capture, tracking, audio, and storage. The UI
  talks to this layer.
- `replay/` Loads and steps through stored traces for playback.
- `ui/` PySide6 widgets and dialogs. Thin layer.
- `app/` Wiring, settings, logging, entry point.

## Module boundaries

The original sketch had everything inside the camera loop. Pulling
calibration and coordinate conversion out of the capture loop makes them
testable without OpenCV or a real camera, and means the same conversion
logic is used at record time, replay time, and when re-analysing past
sessions after a calibration tweak.

## Replaceable parts

- The detector is one class with a small surface, so a different
  algorithm can be slotted in without touching the tracker or UI.
- The repository hides SQLAlchemy from the rest of the code, so a different
  storage backend can be substituted by reimplementing the same methods.
- The audio backend is hidden behind a thin interface so PortAudio can be
  swapped where it isn't available.
