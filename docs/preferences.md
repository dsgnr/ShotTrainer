---
description: "Configure ShotTrainer’s camera, target, microphone and recording settings. Learn what each preference controls and how to save your setup."
---

# Preferences

Open **Preferences** from the navigation rail. Changes are edited in a draft.
Save to apply them or cancel to leave the saved preferences in place.

- **Camera:** camera selection, rotation, brightness, contrast and flips.
  Preview commands support camera and image adjustments. **Auto-optimise** requests
  detector tuning and reports its status.
- **Audio:** microphone and gain.
- **Detection:** shot threshold, refractory interval, pre-shot, post-shot and
  release windows, in milliseconds.
- **Target:** target face, projectile diameter, tracking region, measured circle
  diameter and display toggles.

The tracking circle diameter sets the measurement scale. The target face and
shot diameter set scoring geometry. They serve different purposes.

Real-device settings are stored in the platform application data directory:
`%APPDATA%/ShotTrainer` on Windows, `~/Library/Application Support/ShotTrainer`
on macOS, and `$XDG_DATA_HOME/shottrainer` on Linux (default
`~/.local/share/shottrainer`). The controller uses `settings.json`,
`detector_settings.json`, `zero_offset.json`, `camera_selection.json` and
`custom_target_faces.json`, alongside `sessions.db`. Back up this directory
before editing files manually. Synthetic mode uses a separate temporary
directory.
