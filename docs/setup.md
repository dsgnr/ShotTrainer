---
description: "Mount and align your camera for ShotTrainer. Set the measured circle diameter, image transforms and tracking region."
---

# Camera and target setup

Mount the camera rigidly to the rifle and point it towards a fixed target. Keep
the aiming mark visible throughout the expected hold movement. Use even lighting
and a dark circular mark against a light background.

Use **Pop out camera** in the navigation rail to inspect the camera image.
The popup resizes with the window and keeps its Close button visible.

Open **Preferences** from the navigation rail. Select **Camera**, adjust
**Rotation**, brightness, contrast and flips, then save. The **Auto-optimise**
control tunes circle detection from the available image. Check the tracking
status afterwards rather than assuming a successful result.

In the **Target** section, set **Circle diameter** to the measured diameter of
the dark aiming mark. **Tracking region** limits where detection looks. Select
the scoring face and projectile diameter independently of the tracking mark.

See [audio setup](audio-setup.md), [calibration](calibration.md), and
[accuracy](accuracy.md). Camera reports describe hardware information, not a
validation of the current Rust build.
