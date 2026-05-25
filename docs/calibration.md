# Calibration

Calibration converts pixels in the camera frame to millimetres on the
target plane. You will need to redo it any time the camera, the rifle
mount, or the target distance changes.

## What's actually being measured

The camera is mounted on the rifle and looks forward at the target. As
you aim, the target appears at different positions in the frame.
Calibration measures a single circle of known diameter printed on the
marker sheet: from its size in pixels we know how many millimetres a
pixel represents at that range, and from its centre we know where the
trace's origin sits in the image. The target's position in any frame
can then be reported in millimetres relative to that origin.

## Workflow

1. Print the marker sheet from `Tools > Print marker sheet`. The
   diameter you choose there (60 mm by default) is the value the
   calibration step expects.
2. Pin the printed sheet at your target distance, in the same plane the
   target will sit in.
3. Adopt your normal shooting position and bring the sights to bear on
   the centre of the printed circle. Hold steady.
4. Open `Tools > Calibrate target` from the main menu.
5. Confirm the diameter shown matches what you printed, then press
   **Detect**. If the auto-detector picks the circle out it'll be
   highlighted in cyan. Press **OK** to accept. If detection fails,
   press **Pick manually**, click the circle's centre, then click any
   point on its edge.
6. The dialog reports the calibration scale in mm per pixel and saves
   it. The calibration is also written to disk so it survives a
   restart.

The position of the circle inside the frame doesn't matter as long as
it's fully visible. What does matter is that the circle sits in the
same plane the target will sit in, and that the camera is roughly
square-on to that plane.

## What is stored

A calibration profile records:

- The image-space centre of the circle (px) and its detected radius
  (px).
- The printed diameter (mm), so a future recalibration defaults to the
  same size.
- The resulting `mm_per_pixel` scale, with the origin at the circle's
  centre.

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

A single circle gives a uniform scale and an origin but does not
correct for perspective tilt or rotation. The setup assumes the camera
is roughly square-on to the target plane, which is the normal case for
a barrel or rail-mounted camera. Lens distortion is not corrected;
wide-angle lenses or noticeably angled cameras will produce drift
toward the edges of the frame.
