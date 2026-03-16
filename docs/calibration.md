# Tracking and the printed circle

ShotTrainer doesn't have a calibration step. The trace is computed from
each frame independently using the printed circle's known diameter,
set once in **Preferences > Target > Tracking circle**, no separate menu
item or workflow to run. The same number is used by the marker-sheet
print dialog so what you print and what you tell the app are guaranteed
to agree.

## What's actually being measured

The camera is mounted on the rifle and looks forward at the target. The
detector finds the printed black circle every frame and reports

- the circle's centre in image pixels, and
- its radius in image pixels.

The frame's centre is "where the rifle is pointing". The vector from
the circle's centre to the frame's centre is the rifle's aim offset in
pixels. Convert pixels to millimetres using the live radius

`mm/pixel = diameter_mm / (2 * radius_px)`

and you have the offset in millimetres on the target plane. No
separate calibration step is needed because every frame
self-calibrates. If the camera moves closer the imaged circle grows,
the radius is larger, the mm/px scale is smaller, and the trace
continues to read the right millimetre offset.

## Workflow

1. Print the marker sheet from `Tools > Print marker sheet`. The
   diameter you choose there (60 mm by default) is the value the live
   tracker uses.
2. Pin the printed sheet at your target distance, in the same plane
   the target will sit in.
3. Set the same diameter under **Preferences > Target > Tracking
   circle**. The marker-sheet dialog updates this for you when you
   close it.
4. Aim at the printed circle from your shooting position.

That's it. There is no "Calibrate" button to press.

## Zero on aim

The camera's optical axis isn't the rifle's bore axis, so the trace's
"0" (the printed circle's centre, in image space) isn't where the rifle
is pointing when you're holding on aim. The **Zero on aim** button in
the left column locks the current aim point as the trace's (0, 0). The
offset is saved across restarts. Use **Clear zero** to revert to the
circle's centre as origin.

## When to recheck the diameter

- You changed the size of the printed circle.
- Hits aren't reading at the millimetre offsets you'd expect across the
  whole circle (the per-frame mm/px reported in the header should
  closely match a ruler measurement of pixel-to-mm at the target).

## Limitations

The detector has to keep finding the circle every frame. If you swing
the rifle far enough that the circle leaves the field of view there's
nothing to measure and the trace pauses until the circle is in frame
again.
