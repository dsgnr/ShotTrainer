# Using federation targets (NSRA, ISSF, and others)

ShotTrainer can track standard competition targets as well as the supplied
marker sheet.

The tracker follows any dark circular aiming mark against a lighter background,
including the black aiming centres found on most NSRA, ISSF, NRA, CMP, and
similar federation targets. As long as the aiming circle is visible to the
camera and its diameter is known, it can be used for tracking.

## Setting up a federation target

1. Mount your target as you normally would for shooting.
2. Attach the camera to the rifle and position it as you would for a regular
   session.
3. Ensure the black aiming mark is clearly visible in the camera view.

For reliable tracking:

- The aiming mark should appear at least 30 pixels across in the camera image.
- Normal hold movement should not cause the aiming mark to leave the central
  tracking area.

See [Accuracy and target sizing](accuracy.md) for guidance on selecting an
appropriate camera position and target size.

1. Open **Preferences > Target**.
2. Enter the diameter of the target's black aiming centre in **Tracking circle
   diameter**.
3. Select the target face that matches the target you are shooting.

ShotTrainer uses the tracking circle diameter to calculate the live
millimetres-per-pixel scale. No separate calibration step is required.

## Built-in target faces

ShotTrainer includes several commonly used target faces.

### NSRA 25 yd Prone Rifle

NSRA 2510 BM/89-18.

Five scoring rings ranging from a 41.5 mm outer ring to a 13 mm 10-ring.

### NSRA 50 m Prone Rifle

NSRA MM 12 C 1996-18.

Seven scoring rings ranging from a 105.5 mm outer ring to a 4.5 mm X-ring.

### NSRA 100 yd Prone Rifle

NSRA 1001C 1996-18.

Seven scoring rings ranging from a 205 mm outer ring to an 11.5 mm X-ring.

### ISSF 10 m Air Rifle

Ten scoring rings with a 0.5 mm X-ring and a 10-ring diameter of 1.0 mm.

### ISSF 50 m Rifle

Ten scoring rings with a 10-ring diameter of 10.4 mm.

### Default rings

A simple set of concentric rings intended for informal practice and testing.

## Custom target faces

If your discipline uses a different scoring layout, you can add your own target
definitions.

Create a file named:

```text
<data dir>/custom_target_faces.json
```

See [Troubleshooting](troubleshooting.md#where-the-app-stores-its-data) for the
location of the data directory on your platform.

The file contains a JSON object whose keys are face identifiers:

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

Changes are detected automatically, so updates usually appear without restarting
the application.

If a custom face uses the same identifier as a built-in face, the custom version
takes precedence.

## How tracking works

The selected target face only affects scoring and the rings drawn on the target
view.

The detector tracks the largest circular dark object visible in
the image. On most federation targets this will be the black aiming mark.

Changing target faces does not change how tracking works.

## How shots are scored

When a shot is detected, ShotTrainer calculates its position relative to the
centre of the target and evaluates it against the active target face.

Scoring is based on the configured shot diameter:

**Preferences > Target > Shot diameter**

A shot that touches a higher-value ring receives the higher score, matching
standard paper-target scoring rules.

The score labels come directly from the target face definition, allowing both
standard competition labels and custom scoring schemes.

### X-ring scoring

If a target face includes an X-ring, shots inside that ring are displayed as
**X**.

For score totals, X counts as 10 points. The X count is treated as a separate
tie-break value rather than additional score.

### Re-scoring a session

Sessions are scored using the target face that was active when they were
recorded.

If you load a session and select a different target face, the original scores
remain unchanged.

To calculate scores using the currently selected face, choose:

**Tools > Re-score with current face**

The updated scores are shown immediately in the shot list and statistics panel.

Re-scoring only affects the currently loaded session view. The original session
data stored in the database is not modified.

## When a target face cannot be loaded

If no target face is selected, or a face definition cannot be loaded,
ShotTrainer can still track shots and display them on the target.

However, no scores will be calculated until a valid target face becomes
available.

## Adding a new built-in face

If your discipline uses a target that is not currently included, contributions
are welcome.

When requesting a new built-in face, please provide:

- The discipline and governing body (ISSF, NSRA, NRA, CMP, BSSF, etc.)
- A link to the official target specification or dimensions document
- The ring diameters in millimetres

You can also submit a pull request containing a new target face definition.

## Large black-field targets

Some targets, particularly certain pistol targets, use a large black field that
can occupy most of the camera image.

In these cases, tracking may be less reliable because the detector sees the
entire black area as a single shape.

If this occurs, try:

- Moving the camera closer
- Using a longer focal length
- Adjusting the framing so the aiming mark occupies more of the image

This helps the detector lock onto a clearly defined circular boundary.
