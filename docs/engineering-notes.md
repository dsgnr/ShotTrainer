# Engineering notes

A running log of decisions, alternatives, and trade-offs. Written during
development so the reasoning isn't lost.

## Target detection

First implementation uses contour detection on a thresholded frame. The
target is assumed to be the largest dark, roughly circular blob on a light
background. We compute circularity (4π·area / perimeter²) to reject
rectangles like the A4 sheet itself.

Alternatives considered:

- **Hough circle transform.** Works well when parameters match the target,
  but is sensitive to radius range, blur, and contrast. We may add it as a
  fallback. The OpenCV implementation also gives sub-pixel centres which is
  attractive for high-resolution frames.
- **Template matching.** Fast and simple, but does not generalise across
  distances or zoom levels without a pyramid.
- **Fiducial markers (ArUco).** Probably the most robust if you can stick
  one near the target, but defeats the point of using a plain printed sheet.
- **Manual selection.** Will be supported as a fallback when automatic
  detection fails.

## Calibration

The first implementation uses a known-size A4 sheet. The user shows the sheet
to the camera, the app finds its corners, and the resulting homography gives
both pixels per millimetre and a perspective correction. Without perspective
correction the mm-per-pixel ratio is only valid at the centre of the frame
when the camera is square-on to the target.

Alternatives:

- **Known-size circle.** Simpler, but only gives a scale, not perspective.
- **Manual point selection.** Always available as a fallback.
- **Camera intrinsics.** A separate problem (lens distortion) that can be
  layered on top later.

## Audio shot detection

First implementation: short-term RMS energy with an adaptive baseline and a
refractory window to avoid double-triggering on echoes. This is good enough
for a noticeable shot in a quiet room. Live fire on a range will probably
need more work.

Alternatives:

- **Plain amplitude threshold.** Easy but fragile. Loud handling noise will
  trigger it.
- **Spectral / impulse detection.** Look at the high frequency content. More
  selective but more code to get right.
- **Onset detection libraries.** Overkill for a single transient.

The shot timestamp is the time at which the audio block crossed the
threshold, captured from the same monotonic clock as tracking samples. There
is a known offset of a few milliseconds due to audio buffering and OS
latency. We document it but do not currently try to compensate.

## Storage

SQLite via SQLAlchemy. One file per installation, schema kept simple, an
index on `(session_id, timestamp)` so trace lookups are cheap.

Alternatives:

- **Parquet for trace data, SQLite for metadata.** Better for very large
  sessions, more code complexity. Will revisit if real sessions get big.
- **Plain JSON files.** Easier to inspect, slower to query.

We batch trace inserts to avoid one transaction per sample.

## Threading

Camera and audio each on their own thread. Communication via Qt signals
(queued) and a small ring buffer for the latest tracking samples. The UI
thread does drawing only.

## Packaging

PyInstaller first, because it has the broadest platform coverage and least
new tooling. Briefcase and Nuitka are interesting alternatives but PyInstaller
will get us a working build sooner.

## Accuracy

See [`accuracy.md`](accuracy.md). TLDR at long ranges the
limit is camera resolution and optics, not the software.
