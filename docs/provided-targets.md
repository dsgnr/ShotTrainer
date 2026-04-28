# Using federation targets (NSRA, ISSF)

The detector tracks any black circular mark on a light background.
That includes the printed scoring centres on standard NSRA and ISSF
targets. You don't have to use ShotTrainer's marker sheet. Any
printed circle whose diameter you can measure works.

## How to set up

1. Pin the official target where you'd normally shoot it.
2. Mount your camera on the rifle as you would for any session. The
   target's black aiming centre needs to be reasonably big in the frame
   when you're on aim, at least 30 pixels across the centre, and small
   enough that natural hold motion doesn't push it out of the central
   tracked area. See [`accuracy.md`](accuracy.md) for sizing.
3. Set the diameter under `Preferences > Target > Tracking circle`
   and enter the diameter of the black aiming centre on your printed
   target (or, if you'd rather use ShotTrainer's marker sheet, the
   diameter you printed). The mm/px scale derives from this value
   live. There is no calibration step.
4. In Preferences > Target, pick the face that matches your discipline.
   The rings drawn on the target view will then match your printed face.

## Built-in faces

ShotTrainer ships with some standard target faces:

- **10 m air rifle (ISSF).** Ten rings from 45.5 mm diameter down to a
  0.5 mm diameter 10-ring (5 mm wide rings, 1.0 mm 10-ring).
- **50 m smallbore (ISSF).** Ten rings from 154.4 mm diameter down to a
  10.4 mm diameter 10-ring.
- **Default rings.** Generic concentric rings for casual practice.

The built-ins are JSON files under
`src/shottrainer/ui/assets/target_faces/` in the source tree. Their
format is identical to the user file described below. If you want to
contribute a new built-in face, copy one of the existing files, tweak
the diameters, and open a pull request.

## Custom faces

If your discipline uses a different ring layout, drop a JSON file at
`<data dir>/custom_target_faces.json`. See
[Troubleshooting](troubleshooting.md#where-the-app-stores-its-data) for
where the data directory lives on your platform. The file is a dict of
faces keyed by their internal id:

```json
{
  "my_face": {
    "label": "My discipline",
    "rings": [
      { "diameter_mm": 150.0, "label": "1" },
      { "diameter_mm": 60.0, "label": "5" },
      { "diameter_mm": 10.0, "label": "X" }
    ]
  }
}
```

The file is reread when its modification time changes, so edits show up
without restarting the app. A custom entry whose key matches a built-in
overrides it.

## Asking for a built-in face

If you're shooting on a federation target that isn't shipped, please
open an issue with:

- The discipline and federation (ISSF, NSRA, NRA, CMP, BSSF, etc).
- A link or photograph of the official target dimensions document.
- The diameters you want, in millimetres.

Or send a pull request adding a JSON file to
`src/shottrainer/ui/assets/target_faces/`. We're happy to take any
real-world target.

## What the detector actually tracks

Whichever face you choose, the detector locks onto the largest, most
circular, dark blob in the frame. On a standard target that's the
black aiming circle. The scoring rings drawn on the target view are
purely for your reference. They have no effect on detection.

## How shots are scored

When a shot is detected, ShotTrainer reads its (x, y) position on the
target plane and walks the active face's rings from inside outward.
The shot scores the innermost ring whose disc the shot circle
overlaps, using the configured shot diameter (Preferences > Target >
Shot diameter). A shot that touches a ring counts as the higher value,
matching how paper targets are scored. The label shown is taken
verbatim from the face JSON, so federation labels (1..10, X) and
custom labels both work.

A label of `X` is treated as 10 for the running total, mirroring the
common federation rule that the inner ten counts the same as a 10
unless tied. Labels that don't parse as numbers contribute zero to the
total, so mixed-discipline labels still produce a sensible figure.

### Re-scoring a loaded session

Scores are captured at recording time against whatever face was
active. If you open a saved session and switch to a different face
(say to compare a 50 m smallbore session against a different ring
layout), the on-screen scores still reflect the original face. Use
**Tools > Re-score with current face** to refresh the displayed
scores against the active face. The change is in-memory only.
Re-opening the session reloads the originally captured scores.

## Black-target faces

Targets with a large black field (some pistol distances) can defeat
the contour detector because the entire target reads as one blob. For
these, swap to a longer lens or a closer mount so the black field
fills the frame and the detector locks onto its outer edge.
