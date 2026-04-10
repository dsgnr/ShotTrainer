# Setup and camera alignment

Practical guide for getting the camera mounted on the rifle, lined up
with the bore, and pointed at the target so the trace and the shot
both land in sensible places.

## The shape of the problem

The bullet leaves the bore. The camera's optical axis is offset from
the bore by however far apart the two are physically (typically a few
centimetres above or to the side). Both axes ultimately need to point
at the same target, but they don't have to be perfectly parallel.
Anything imperfect in the alignment becomes a fixed offset between
the trace and the actual point of impact, and calibration plus zeroing
absorb that offset.

```mermaid
flowchart LR
    A[Camera<br/>optical axis] -.->|offset| B[Bore axis]
    A --> T[Target]
    B --> T
    style T fill:#2d6cdf,stroke:#1f4f9b,color:#fff
```

What you actually need:

1. The camera moves with the rifle (no flex, no slip).
2. The camera sees the target plainly when you're on aim.
3. The trace direction matches your aim direction once calibrated.
4. The fixed offset between trace and impact is small enough that
   calibration and your zero handle it.

## Mounting the camera

### Where to put it

Two practical positions:

- **On the barrel.** A rail clamp or 3D-printed cradle around the
  barrel near the muzzle. Best line-of-sight to the target. Most
  affected by barrel heating, recoil flex.
- **On the stock or scope rail.** A Picatinny / dovetail rail mount
  on top of the receiver or under the stock. More stable than barrel
  mounts, but the camera looks past the bore at a small angle that
  must be accounted for at the target.

```mermaid
flowchart TB
    subgraph rifle ["Rifle"]
        direction LR
        Stock --- Receiver --- Barrel --- Muzzle
    end
    Camera1[Camera on rail] -.-> Receiver
    Camera2[Camera on barrel] -.-> Muzzle
    Muzzle --> Target
```

Whichever you choose, the camera should be:

- Rigid relative to the rifle. A loose mount is the single biggest
  cause of unexplained trace noise.
- Roughly above or below the bore rather than off to the side, so
  the offset is in one axis only and easier to reason about.
- Aimed forward, with the target near the centre of the frame when
  you're on aim.

### Wiring

Route the USB cable along the stock with cable ties or tape so it can't
tug on the camera as the rifle moves. A coiled cable that lifts off
the rifle as the muzzle rises will show up in the trace.

## Aligning camera to bore

You don't need a laser bore-sight rig. The procedure that works:

1. Set the rifle up at the firing point in your normal stance.
2. Aim the rifle at the centre of the target through the iron sights
   or scope, exactly as you would for a shot. Hold steady.
3. Look at the live preview from the camera. The target should be
   somewhere in the central third of the frame.
4. Adjust the camera mount so the target's centre sits roughly at the
   centre of the frame at this on-aim position. You don't need
   pixel-perfect, you just need it not to drift to the edge during a
   normal hold.
5. Tighten the mount and check the live preview again. Any movement
   between "loose" and "tight" tells you the mount has play. Fix
   that before going further.

```mermaid
sequenceDiagram
    participant U as You
    participant R as Rifle + camera
    participant T as Target
    U->>R: Adopt shooting position
    U->>T: Aim at target centre
    R-->>U: Live preview
    Note over U,R: Target should sit near<br/>frame centre at on-aim
    U->>R: Adjust mount until centred
    U->>R: Tighten and recheck
```

### When you can't get it perfect

You usually can't, and that's fine. The live target image only needs
to stay inside the central tracking region during a normal hold (see
the Tracking region setting in Preferences). If the on-aim image is
slightly off-centre:

- **Off by less than 1/4 of the frame.** Leave it. Calibration handles
  position offsets, and the trace coordinates remain correct relative
  to the target centre.
- **Off by more than 1/4 of the frame.** The hold motion may push the
  target outside the tracking region during natural wobble. Either
  reseat the mount, widen the tracking region in Preferences, or
  reframe by adjusting the camera angle.
- **Trace direction is opposite to aim.** Open Preferences > Camera
  and toggle the horizontal mirror. A barrel-mounted camera mounted
  the other way up flips left-right relative to the shooter. The
  preview makes this obvious.
- **Trace is rotated.** Use the Rotation drop-down in Preferences to
  pick 90, 180, or 270 degrees. This is common when the camera body
  was clamped sideways for clearance.

## Calibrating after alignment

Once the camera is mounted and aligned well enough that the target
sits comfortably in frame on aim, do the calibration once. See
[`calibration.md`](calibration.md) for the full workflow. Briefly:

1. Pin a printed A4 sheet at the target distance, in the same plane
   the target will sit in.
2. Aim at the sheet from your shooting position.
3. Open `Tools > Calibrate target` and let the auto-detector pick the
   four corners (or click them yourself).
4. The dialog reports mm per pixel and saves the calibration.

The camera-to-bore offset doesn't enter calibration. Calibration only
maps pixels on the target plane to millimetres on that plane.

## Zeroing the trace to point of impact

There's still a fixed offset between where the camera looks and where
the bullet goes. To remove it:

1. Calibrate as above.
2. Fire a small group (3 to 5 shots) at the target with the rifle
   zeroed normally.
3. Look at the marked group on the digital target. If the centre of
   the group sits a few millimetres off from where you aimed, that
   offset is the camera-to-bore mismatch.
4. Note the offset. The simplest fix is to ead every shot as
   "trace position plus offset". For a permanent fix, recalibrate
   with the A4 sheet shifted by the offset so the digital centre
   matches the rifle's zero.

For dry-fire practice the offset doesn't matter, since there's no
impact to compare against. The trace alone is what you're analysing.

## Sanity checks

After setup, before recording sessions:

- Move the muzzle by a small known amount (a few centimetres at the
  target plane) and watch the trace move by the same amount.
- Tap the rifle gently. The trace should jump and then settle, not
  drift away.
- Cover the lens. The detector should report tracking lost, not lock
  onto a different blob.
- Fire one shot. The shot mark should appear inside the recorded
  hold zone, not somewhere else entirely.

If any of these fail, revisit the mount before tuning calibration or
detector settings.
