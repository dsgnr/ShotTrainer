# Troubleshooting

## Camera

**No image, status bar says "Camera: Could not open camera 0".**
Another app is holding the device, or the index is wrong. Close other
camera apps, then open Tools > Preferences and pick a different camera.
On Linux, check that you are in the `video` group:

```
groups | tr ' ' '\n' | grep video
```

**Image is upside-down or mirrored.**
Most webcams ship with a default orientation that doesn't match a
barrel-mounted setup. The app does not yet apply rotation. Mount the
camera the right way up or open the camera's vendor utility to flip the
image.

**Frame rate looks low.**
Check the camera's native resolution and FPS in its vendor utility. The
controller currently uses default settings. You can tune via
`CameraConfig` if you embed the app, but the GUI does not expose this yet.

## Microphone

**No shots are detected.**
Open Tools > Preferences and lower the shot threshold. Make a clap or
sharp noise near the mic to verify. The level meter is not surfaced in
the UI yet, so try threshold values around 0.05 to 0.1 for indoor use.

**Every loud noise registers as a shot.**
Increase the threshold and the refractory window. Persistent room noise
(fan, AC) raises the noise floor. Try a directional mic placed close to
the firing point.

**macOS does not show the microphone permission prompt.**
The packaged app needs `NSMicrophoneUsageDescription` in its Info.plist.
See `packaging/Info.plist.in`. When running from source via Python, macOS
prompts for the *Terminal* (or your IDE) the first time, not for
ShotTrainer itself.

## Calibration

**Detect can't find the calibration circle.**
Make sure the printed circle contrasts strongly with the background and
is fully visible. If automatic detection still fails, click "Pick
manually", click the circle's centre, then click any point on its edge.

**The mm-per-pixel value looks wildly off.**
Confirm the diameter shown in the dialog matches the diameter you
actually printed. The marker sheet's footer reports the size it was
rendered at.

**The trace doesn't sit where the rifle is actually pointing.**
The calibrated origin is the centre of the calibration circle, not the
bore axis. Hold the rifle on the target's centre (or your zeroing
group's centre) and click **Zero on aim** in the left column. That
locks the current aim point as (0, 0). The offset persists across
restarts; **Clear zero** reverts to the calibrated origin.

## Sessions and replay

**Sessions don't appear in the browser after recording.**
The session is written to the local SQLite database when you press Stop.
If you closed the app via the OS instead of stopping the session first,
the trace and shots are still saved but the session is marked as not
ended. ShotTrainer warns you when you try to quit while a session is
in progress. Pick **Stop and quit** for a clean save.

**Replay scrubber is greyed out.**
Replay only enables once you select a shot from the shot list. If a
session has no shots there is nothing to scrub.


## Where the app stores its data

ShotTrainer keeps everything in a per-user data directory:

- macOS: `~/Library/Application Support/ShotTrainer/`
- Linux: `$XDG_DATA_HOME/shottrainer/` (or `~/.local/share/shottrainer/`)
- Windows: `%APPDATA%\ShotTrainer\`

Inside you'll find `sessions.db` (sessions and shot data), `settings.json`,
`calibration.json`, `detector_settings.json`, `zero_offset.json`, and
`ui_state.json`. Deleting any of them resets the relevant state to
defaults. Deleting `sessions.db` wipes recorded shots so keep a backup
if you care about the history.
