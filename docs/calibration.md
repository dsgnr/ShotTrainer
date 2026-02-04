# Calibration

Calibration converts pixels in the camera frame to millimetres on the
target plane. You will need to redo it any time the camera, the rifle
mount, or the target distance changes.

## What's actually being measured

The camera is mounted on the rifle and looks forward at the target. As
you aim, the target appears at different positions in the frame.
Calibration finds the four corners of a known-size A4 sheet placed at
the target so we know how many millimetres a pixel represents at that
range. From then on, the target's position in any frame can be
reported in millimetres relative to the target centre.

## Workflow

1. Pin a printed A4 sheet (210 by 297 mm) at your target distance, in
   the same plane the target will sit in. The built-in marker sheet
   from `Tools > Print marker sheet` is a good choice.
2. Adopt your normal shooting position with the rifle and bring the
   sights to bear on the centre of the sheet. Hold steady.
3. Open `Tools > Calibrate target` from the main menu.
4. The dialog shows the live preview. If the auto-detector finds the
   sheet's corners they're overlaid; press **Accept**. If not, press
   **Pick manually** and click the four corners in clockwise order
   starting at top-left.
5. The dialog reports the calibration scale in mm per pixel and saves
   it. The calibration is also written to disk so it survives a
   restart.

The position of the sheet inside the frame doesn't matter much — the
homography handles offset and tilt. What does matter is that all four
corners are visible and the sheet is on the same plane as the target.

## What is stored

A calibration profile records:

- The four target-space points (mm) and the four image-space points
  (px).
- The resulting homography matrix.
- The corresponding session metadata.

The most recent calibration is also stored as a JSON file in the data
directory; the file is reloaded at launch and watched for external
edits while the app is running.

## When to recalibrate

- The camera moved on the rifle, or the rifle's mount changed.
- You moved to a different shooting distance.
- You changed lens, magnification, or resolution.
- You suspect the numbers no longer match reality. The header shows
  the live mm-per-pixel.

## Limitations

The homography approach assumes a single planar target. Lens
distortion is not corrected; wide angle lenses or extreme camera
angles produce drift toward the edges of the frame.
