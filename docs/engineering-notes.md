# Engineering notes

A running log of decisions, alternatives, and trade-offs. Written during
development so the reasoning isn't lost.

## Target detection

The detector runs an adaptive threshold over the grayscale frame and then
walks the resulting contours, scoring each by circularity (4π·area /
perimeter²) and how well it fills its enclosing circle. The highest-scoring
blob within the radius range wins. This rejects long rectangles like the
edge of the marker sheet.

Alternatives considered:

- **Hough circle transform.** Works well when parameters match the target,
  but is sensitive to radius range, blur, and contrast. The OpenCV
  implementation gives sub-pixel centres which is attractive for
  high-resolution frames. We kept it in mind as a drop-in replacement.
- **Template matching.** Fast and simple, but does not generalise across
  distances or zoom levels without a pyramid.
- **Fiducial markers (ArUco).** Probably the most robust if you can stick
  one near the target, but defeats the point of using a plain printed sheet.
- **Manual selection.** Available as a fallback when automatic detection
  fails. The user clicks the centre of the target.

## Calibration

Calibration uses a single circle of known diameter printed on the marker
sheet. The user shows the circle to the camera, the app fits its centre
and radius (either automatically with the same contour pipeline as the
live detector, or by two manual clicks), and the printed diameter divided
by the detected diameter in pixels gives a uniform mm-per-pixel scale.
The circle's centre is taken as the image-space origin.

Trade-offs:

- **Single circle vs four corners.** A single circle gives scale and an
  origin but cannot recover perspective tilt. Acceptable here because the
  camera is rail- or barrel-mounted and roughly square-on to the target;
  if non-trivial tilt becomes a problem the upgrade path is to fit an
  ellipse and recover plane pose from it.
- **Manual point selection.** Always available as a fallback when the
  detector can't find the circle (centre click + edge click).
- **Camera intrinsics.** Lens distortion is a separate problem. Not
  attempted here. The linear scale handles distance and zoom only.

## Audio shot detection

The detector watches short-term RMS energy with an adaptive baseline and a
refractory window to avoid double-triggering on echoes and ringing. This is
adequate for a clearly audible shot in a quiet room. Live fire on a range
needs noise-rejection tuning, exposed via the sensitivity controls.

Alternatives:

- **Plain amplitude threshold.** Easy but fragile. Loud handling noise will
  trigger it.
- **Spectral / impulse detection.** Look at the high frequency content. More
  selective but more code to get right.
- **Onset detection libraries.** Overkill for a single transient.

The shot timestamp is the time at which the audio block crossed the
threshold, captured from the same monotonic clock as tracking samples. There
is a known offset of a few milliseconds from audio buffering and OS latency.
It is documented rather than compensated for.

## Storage

SQLite via SQLAlchemy. One file per installation, schema kept simple, an
index on `(session_id, timestamp)` so trace lookups are cheap. Trace inserts
are batched so each sample does not pay the cost of its own transaction.

Alternatives:

- **Parquet for trace data, SQLite for metadata.** Better for very large
  sessions, more code complexity. Worth reconsidering if session sizes grow
  large enough to make SQLite trace queries slow.
- **Plain JSON files.** Easier to inspect, slower to query.

## Threading

Camera and audio each run on their own thread. Communication is via Qt
signals (queued) and a small ring buffer for the latest tracking samples.
The UI thread does drawing only.

## Packaging

PyInstaller is the chosen packager. It has the broadest platform coverage
and the least new tooling. Briefcase and Nuitka are interesting
alternatives that were not pursued.

## Accuracy

See [`accuracy.md`](accuracy.md). TLDR at long ranges the
limit is camera resolution and optics, not the software.
