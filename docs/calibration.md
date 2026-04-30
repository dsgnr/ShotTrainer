# Tracking and the printed circle

ShotTrainer uses a known circle diameter to convert camera measurements into
real-world millimetres.

Unlike many target-tracking systems, there is no separate calibration procedure.
The scale is calculated continuously from the detected size of the tracking
circle, so every frame effectively calibrates itself.

The tracking circle diameter is configured in:

**Preferences > Target > Tracking circle**

The same value is used by the marker sheet printing tool, helping ensure that
the printed marker and tracking settings remain consistent.

## How scaling works

The camera is mounted to the rifle and points towards the target.

For each frame, ShotTrainer detects the tracking circle and measures:

- The circle centre in image pixels
- The circle radius in image pixels

The centre of the camera image represents the current pointing direction of the
rifle.

The difference between the image centre and the detected circle centre gives the
rifle's offset from the target centre.

To convert that offset into millimetres, ShotTrainer calculates a scale factor
using the known diameter of the tracking circle:

```text
mm per pixel =
tracking circle diameter (mm)
÷
detected circle diameter (pixels)
```

Because the detector measures the circle size continuously, the scale updates
automatically if the apparent size of the circle changes.

For example:

- Moving the camera closer makes the circle appear larger.
- Moving the camera further away makes the circle appear smaller.

In both cases, ShotTrainer automatically adjusts the scale calculation to
compensate.

## Setup workflow

Using a marker sheet only requires a few steps.

### 1. Print a marker sheet

Open:

**Tools > Print marker sheet**

Choose the diameter you want to use.

The default value of **60 mm** works well for general-purpose testing.

### 2. Mount the marker

Place the marker sheet at the target location and secure it so that it remains
flat.

Ideally, the marker should be positioned in the same plane as the target you
intend to shoot.

### 3. Check the tracking circle setting

Open:

**Preferences > Target > Tracking circle**

Ensure the value matches the diameter of the printed marker.

The marker sheet dialog updates this value automatically when the marker is
generated.

### 4. Start aiming

Once the camera can see the marker, tracking begins automatically.

There is no separate calibration button or setup wizard.

## Zero on aim

The centre of the tracking circle is not necessarily the same as the rifle's
actual point of aim.

This is because the camera's optical axis is offset from the bore axis.

To compensate, use **Zero on aim**.

When pressed, the current aim position becomes the new `(0, 0)` reference point
for the trace.

This allows the displayed trace to be centred on your actual aiming point rather
than the geometric centre of the marker.

The zero offset is saved and restored automatically between sessions.

To remove the adjustment and return to the marker centre, use **Clear zero**.

## When to check the tracking circle diameter

The tracking circle diameter rarely needs changing, but it is worth verifying
if:

- You print a marker sheet with a different diameter.
- You switch to a target with a different aiming mark size.
- Measured offsets appear consistently larger or smaller than expected.

If the configured diameter does not match the real diameter of the tracked
circle, all millimetre measurements will be scaled incorrectly.

## Limitations

Tracking depends on the detector being able to see the tracking circle.

If the circle leaves the camera's field of view, tracking cannot continue and
the trace will pause until the circle becomes visible again.

For best results:

- Keep the tracking circle fully visible.
- Ensure good contrast between the circle and its background.
- Avoid glare and reflections on the target surface.
- Use a camera position that keeps the circle comfortably within the tracking
  region during normal aiming movement.
