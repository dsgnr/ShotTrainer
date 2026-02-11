# Using federation targets (NSRA, ISSF)

The detector tracks any black circular mark on a light background. That
includes the printed scoring centres on standard NSRA and ISSF targets.
You don't have to use the calibration sheet provided by ShotTrainer.

## How to set up

1. Pin the official target where you'd normally shoot it.
2. Mount your camera on the rifle as you would for any session. The
   target's black aiming centre needs to be reasonably big in the frame
   when you're on aim, at least 30 pixels across the centre, and small
   enough that natural hold motion doesn't push it out of the central
   tracked area. See [`accuracy.md`](accuracy.md) for sizing.
3. Calibrate: pin an A4 sheet in roughly the same plane as the target,
   either alongside or in place of the target for the calibration step.
   Aim at the sheet, then run the automatic detector or click the four
   corners manually. The calibration is independent of which face you're
   tracking.
4. In Preferences > Target, pick the face that matches your discipline.
   The rings drawn on the target view will then match your printed face.

## Built-in faces

ShotTrainer ships with some standard target faces:

- **10 m air rifle (ISSF).** Ten rings from 22.75 mm radius down to a
  0.25 mm radius 10-ring (5 mm wide rings, 0.5 mm 10-ring).
- **50 m smallbore (ISSF).** Ten rings from 77.2 mm radius down to a
  5.2 mm radius 10-ring.
- **Default rings.** Generic concentric rings for casual practice.

## Custom faces

If your discipline uses a different ring layout, drop a JSON file at
`<data dir>/custom_target_faces.json`. See [`README.md`](../README.md) for
where the data directory lives on your platform. Format:

```json
{
  "my_face": {
    "label": "My discipline",
    "rings": [
      { "radius_mm": 75.0, "label": "1" },
      { "radius_mm": 30.0, "label": "5" },
      { "radius_mm": 5.0, "label": "X" }
    ]
  }
}
```

## What the detector actually tracks

Whichever face you choose, the detector locks onto the largest, most
circular, dark blob in the frame. On a standard target that's the
black aiming circle. The scoring rings drawn on the target view are
purely for your reference. They have no effect on detection.

## Black-target faces

Targets with a large black field (some pistol distances) can defeat
the contour detector because the entire target reads as one blob. For
these, either swap to a longer lens / closer mount so the black field
fills the frame and the detector locks onto its outer edge, or use
the manual aim picker to set the centre yourself.
