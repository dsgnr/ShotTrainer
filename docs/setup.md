---
title: "Mount and set up the tracking camera"
description: "Mount and align your camera for ShotTrainer. Set the measured circle diameter, image transforms and tracking region, then check the live preview."
---

# Camera and target setup

## Mount the camera

Mount the camera rigidly to the rifle and point it towards a fixed target. Keep
the aiming mark visible throughout the expected hold movement. Use even lighting
and a dark circular mark against a light background.

## Check the camera image

Use **Pop out camera** in the navigation rail to inspect the camera image.
The popup resizes with the window and keeps its Close button visible.

Open **Preferences** from the navigation rail. Select **Camera**, adjust
**Rotation**, brightness, contrast and flips, then save. The **Auto-optimise**
control tunes circle detection from the available image. Check the tracking
status afterwards rather than assuming a successful result.

## Set the circle diameter and scoring face

In **Preferences > Tracking**, set **Circle diameter** to the measured diameter
of the dark aiming mark. **Tracking region** limits where detection looks.
Select the scoring face and projectile diameter under **Session settings** on
the target page, or when creating a new session.

## Next steps

See [audio setup](audio-setup.md), [calibration](calibration.md), and
[accuracy](accuracy.md). Camera reports describe hardware information, not a
validation of hardware support on your machine.

Compare hardware in the [camera reports](cameras.md), and see
[troubleshooting](troubleshooting.md) if the circle is not detected reliably.
