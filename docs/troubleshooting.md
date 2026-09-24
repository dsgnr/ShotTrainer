---
description: "Fix common ShotTrainer camera, tracking and audio problems, including device access, image orientation and missed or false shot detections."
---

# Troubleshooting

## Only synthetic devices appear

The default desktop build has no OpenCV backend. Install the native OpenCV and
compiler dependencies, then use `cargo tauri dev --features opencv` from the
repository root. Ensure `SHOTTRAINER_FAKE_DEVICES` is unset and the application
was not started with `--fake-devices` when testing real hardware.

## Camera or microphone unavailable

Check operating-system permissions, device connections and whether another
application has exclusive access. Select the device in Preferences. Native
backend support depends on your platform and installed libraries. Synthetic mode
and browser mock mode cannot diagnose hardware capture.

## Unstable tracking or wrong scale

Use even lighting, a sharp high-contrast circular mark and a rigid camera mount.
Keep the mark inside the tracking region. Check rotation and flips, then confirm
**Circle diameter** matches the measured mark in millimetres. See
[accuracy](accuracy.md) and [setup](setup.md).

## Missed or duplicate shots

Adjust microphone gain, shot threshold and refractory interval. Test after
changing microphone position or background noise. See [audio
setup](audio-setup.md).

## Frontend fails to start

Use Node.js 26 and npm 11, then run `npm --prefix frontend ci` from the root.
`npm --prefix frontend run dev` is a browser mock. Use `cargo tauri dev` for the
desktop bridge. The status line offers **Restart** when the bridge needs
reconnection.

## Missing sessions

Real-device sessions and synthetic-device sessions use different directories.
See [preferences](preferences.md) for paths. Back up data before attempting any
manual repairs. Include platform, launch mode and relevant error output when
reporting a problem.

## Shot registration after tracking loss

The controller can map and score a shot using an earlier valid tracking sample
when the target is subsequently lost. It does not currently enforce a maximum
sample age for that mapping. A displayed score therefore does not prove that the
target was being tracked at the instant of the shot. Check the camera and
tracking status, restore a clear target view, and treat shots recorded during
tracking loss as unreliable. This inherited behaviour needs a separate timing
policy and regression tests before it is changed.
