# Accuracy notes

ShotTrainer aims to give useful feedback, not laboratory-grade
measurements. This page is an honest summary of what affects accuracy
and what you can realistically expect.

The setup ShotTrainer assumes: a small webcam mounted on the rifle
itself (barrel, stock, or a Picatinny / dovetail rail) looking forward
at a static paper target. Aim moves the rifle, which moves the camera,
which moves where the target appears in the frame. ShotTrainer detects
the target's position in each frame and translates that motion into a
hold trace.

## What "millimetre accuracy" actually depends on

Reaching mm-level precision at the target depends on several things that are
not the application:

- **Sensor resolution.** A 1080p webcam pointed at a target 50 m away
  produces a target image only a handful of pixels across. The
  mm-per-pixel ratio at the target is a hard ceiling on accuracy.
- **Optical magnification.** Without a longer focal length lens you
  cannot recover pixels you never captured. A telephoto webcam or a
  C-mount tele lens is the usual answer at longer ranges.
- **Lens quality and focus.** Soft focus and chromatic aberration smear
  the target edge so the centroid wanders.
- **Mount rigidity.** The camera must move with the rifle and only with
  the rifle. Any flex or play in the mount adds spurious motion to the
  trace that has nothing to do with hold.
- **Lighting.** Strong shadows or backlighting change which pixels the
  detector picks as "the circle".
- **Atmospheric effects.** At long range, mirage and heat shimmer can
  move the apparent target by more than the rifle's group size.
- **Frame rate and timestamp alignment.** A shot moving across the
  trace during a frame's exposure is averaged. The audio shot time has
  its own latency.

A practical short range setup (10 m, 1080p webcam, decent lighting,
solid mount) can resolve a few millimetres on the target. A long range
setup without optical magnification cannot, regardless of the software.

## Framing the target

The target needs to be small enough in the frame that natural rifle
motion keeps it on screen, and large enough that the centroid is
precise.

Two competing constraints:

- **Pixels across the target mark.** Below 30 pixels of diameter the
  centroid jitters by appreciable fractions of a millimetre. More
  pixels is better for precision.
- **Headroom for hold motion.** A standing position can wobble several
  centimetres on the target plane. The target plus that wobble must
  stay inside the frame, otherwise the detector loses lock during the
  hold.

A useful rule of thumb: frame so the target is roughly a quarter to a
third of the frame width when the rifle is on aim. That leaves room
for the worst-case wobble before the target reaches the edge of the
tracking region.

Approximate target diameters at common practice ranges, assuming a
1080p sensor and the framing rule above:

| Range  | Suggested mark diameter | Notes |
|--------|-------------------------|-------|
| 5 m    | 25 to 50 mm             | Indoor air rifle, classroom range. |
| 10 m   | 30 to 60 mm             | Standard 10 m air discipline. |
| 25 m   | 80 to 150 mm            | Pistol practice or sighter. |
| 50 m   | 150 to 250 mm           | Smallbore distance, optical magnification helpful. |
| 100 yd | 300 mm or larger        | A telephoto lens is essentially required. |

If your mark is below the suggested range, expect the reported group
centre to wobble by a millimetre or two even on a perfectly steady
hold. That wobble is detector noise, not your hold.

## Diagnostic

The header shows the current calibrated mm-per-pixel value. Multiply by
the scoring ring tolerance you care about to see whether your setup
can theoretically resolve it.

For example, if you want to resolve the 10-ring of a 50 m smallbore
target (roughly 10 mm diameter) and your calibration says 2 mm per
pixel, you have about 5 pixels across the ring, which is too few for
stable centroid estimation.

## Time alignment

Tracking samples are timestamped from `time.monotonic()` at the moment
the frame is read off the camera. Shot events are timestamped from the
same clock at the moment the audio block crosses the detection
threshold. There is a small unknown latency from the microphone and
audio buffer. Realistic alignment is on the order of one or two video
frames, not microseconds.

## What the app does well

- Pixel-to-mm conversion is unit tested and reused across recording and
  replay so the same numbers come out on either side.
- The trace stored around a shot includes a configurable pre and post
  window, so post-hoc analysis of hold and follow-through is honest
  about what was sampled.
- Confidence is recorded per sample so low-quality detections can be
  filtered or down-weighted during analysis.
