# Troubleshooting

## Camera

**No image, status bar says "Camera: Could not open camera 0".** Another app is
holding the device, or the index is wrong. Close other camera apps, then open
Tools > Preferences and pick a different camera. On Linux, check that you are in
the `video` group:

```
groups | tr ' ' '\n' | grep video
```

**Image is upside-down or mirrored.** Most cameras ship with a default
orientation that doesn't match a barrel-mounted setup. Open
**Tools > Preferences > Camera** and pick a rotation (0, 90, 180, or 270
degrees) and/or toggle the horizontal or vertical mirror until the live preview
matches what your eye sees through the sights.

**Frame rate looks low.** Check the camera's native resolution and FPS in its
vendor utility. The controller currently uses default settings. You can tune via
`CameraConfig` if you embed the app, but the GUI does not expose this yet.

## Microphone

**No shots are detected.** Open Tools > Preferences > Audio and watch the level
meter while you clap or make a sharp noise near the microphone. The blue marker
shows the threshold. If your peaks don't pass that marker, lower the threshold
or raise the **Volume** slider. The same meter is available in the left column
of the main window during a session.

**Every loud noise registers as a shot.** Increase the threshold and the
refractory window. Persistent room noise (fan, AC) raises the noise floor. Try a
directional mic placed close to the firing point.

**"Could not open microphone" or "PortAudio unavailable".** Another app is
holding the device, the device was unplugged, or the system audio service is
not running. Close any other apps using the mic, then open Preferences > Audio
and pick a different input. On Linux, make sure PulseAudio or PipeWire is
running (`pactl info` should respond). After plugging in a USB mic press the
**Refresh** button in the Audio tab to re-enumerate devices.

**macOS does not show the microphone permission prompt.** The packaged app asks
for permission on first launch through its bundled
`NSMicrophoneUsageDescription`. When running from source via Python, macOS
prompts for the _Terminal_ (or your IDE) the first time, not for ShotTrainer
itself. If you denied it by accident, toggle the permission off and on again
under **System Settings > Privacy & Security > Microphone**.

## Tracking

**The trace stops moving and the camera view says "lost".** The detector can't
see the printed circle in the current frame. Either the circle has moved out of
view (swing the rifle until it's back in frame) or it has too little contrast
against the background. Improve the lighting on the target side, or print a
larger circle.

**The tracking marker jumps around or wanders on a still target.** If you're
using a target with scoring rings (white lines inside the black circle), the
detector may be fragmenting the circle into ring contours. Press
**Auto-optimise** in the detector panel. The optimiser tries different settings
including morphological closing, which fills the ring gaps. If the target is
well-lit and large in the frame, Hough detection should pick it up cleanly
without needing any tweaks.

**The mm-per-pixel value in the header looks wrong.** The header reads "Tracking
N mm circle - X.XXX mm/px". Confirm the diameter (N) matches what you actually
printed. Set it under **Preferences > Target > Tracking circle** if not.

**The trace doesn't sit where the rifle is actually pointing.** The trace's
origin is the printed circle's centre. The camera's optical axis isn't the
rifle's bore axis, so there's a fixed offset between "where the camera sees the
centre" and "where the rifle is pointing". Hold the rifle on the target's centre
(or your zeroing group's centre) and click **Zero on aim** in the left column.
That locks the current aim point as (0, 0). The offset persists across restarts.
While it's in force the camera preview shows a magenta cross at the chosen zero
and a "Manual zero" badge in the bottom-left. **Clear zero** reverts to the
circle's centre as origin.

## Sessions and replay

**Sessions don't appear in the browser after recording.** The session is written
to the local SQLite database when you press Stop. If you closed the app via the
OS instead of stopping the session first, the trace and shots are still saved
but the session is marked as not ended. ShotTrainer warns you when you try to
quit while a session is in progress. Pick **Stop and quit** for a clean save.

**Replay scrubber is greyed out.** Replay only enables once you select a shot
from the shot list. If a session has no shots there is nothing to scrub.

## Where the app stores its data

ShotTrainer keeps everything in a per-user data directory:

- macOS: `~/Library/Application Support/ShotTrainer/`
- Linux: `$XDG_DATA_HOME/shottrainer/` (or `~/.local/share/shottrainer/`)
- Windows: `%APPDATA%\ShotTrainer\`

Inside you'll find `sessions.db` (sessions and shot data), `settings.json`,
`detector_settings.json`, `zero_offset.json`, and `ui_state.json`. Deleting any
of them resets the relevant state to defaults. Deleting `sessions.db` wipes
recorded shots so keep a backup if you care about the history.
