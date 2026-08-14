# Engineering notes

A running record of design decisions, experiments, and trade-offs made during
development. The goal is to capture the reasoning behind the current
implementation so future changes have historical context.

## Target detection

The detector uses a two-stage approach.

### Primary path: Hough circles

The detector first attempts circle detection using `cv2.HoughCircles`.

Hough detection works directly from image gradients, making it robust when
tracking federation targets that contain scoring rings, white gaps, or other
internal markings. Instead of treating the target as a collection of contours,
it identifies the circle as a single object.

If a circle is found within the expected radius range, that result is used.

This approach eliminated a common problem in early versions where the tracker
would jump between different ring fragments on printed targets.

### Fallback path: contour detection

If Hough detection fails-for example due to poor contrast, small targets, or
unusual markings-the detector falls back to a contour-based pipeline:

1. Adaptive thresholding
2. Morphological opening
3. Morphological closing
4. Contour extraction
5. Circularity and fill-ratio scoring

The fallback remains effective for plain printed circles and simple marker
sheets.

### Alternatives considered

#### Template matching

Simple and reasonably fast, but difficult to make scale-independent without
introducing image pyramids and additional complexity.

#### ArUco markers

Likely the most robust option overall, but the project goal was to work with
ordinary printed targets rather than specialised fiducials.

#### Manual selection

Still available as a fallback. If automatic detection fails, the user can
manually select the target centre.

---

## Tracking

The tracker converts target movement into real-world coordinates.

For each frame:

1. Detect the target circle.
2. Calculate the live mm-per-pixel scale.
3. Measure the offset between the circle centre and frame centre.
4. Convert that offset into millimetres.

Both the detected radius and centroid are smoothed using a short EMA to reduce
detector jitter.

No separate calibration step is required.

### Design evolution

The current approach is the third major design iteration.

### v1: A4 sheet and homography

The original design used a printed A4 calibration sheet.

The workflow was:

1. Detect all four corners.
2. Fit a homography using `cv2.findHomography`.
3. Persist the mapping.
4. Reuse it until recalibration.

In practice, this created more friction than the rest of the application
combined.

Problems included:

- Corner detection reliability.
- Recalibration whenever the setup changed.
- Sensitivity to camera position changes.
- Difficult-to-diagnose failures.

A particularly problematic issue was that incorrect calibrations often produced
believable-looking traces, making errors difficult to spot.

### v2: Single-circle calibration

The second design replaced the A4 sheet with a single circle of known diameter.

This simplified setup considerably:

- Easier to print.
- Easier to detect.
- Simpler calibration logic.

When the circle appeared elliptical due to camera angle, the calibration
attempted to compensate using an ellipse-based homography.

Although generally successful, several issues emerged:

- Detector confusion with other dark circular objects.
- Calibration drift when changing shooting position.
- Increasing complexity around calibration management.
- Additional settings and correction layers to compensate for changing geometry.

By the end of the experiment, the calibration system had become more complicated
than the tracking system itself.

### v3: Live scale from the target

The current design removes calibration entirely.

If the target circle is visible and its real-world diameter is known, the
application can calculate scale directly from each frame.

The result is a continuously updated measurement rather than a stored
calibration snapshot.

#### Trade-offs

**The target must remain visible**

If the circle leaves the frame there is no scale reference and tracking pauses
until it returns.

**Direction remains image-plane based**

Small camera roll angles introduce a small coupling between horizontal and
vertical movement.

The effect is usually negligible and is considered an acceptable trade-off.

**Lens distortion is not compensated**

The live scaling model handles distance and zoom changes only.

Lens calibration can be added later without changing the tracker architecture.

---

## Audio shot detection

Shot detection is based on:

- Short-term RMS energy
- An adaptive baseline
- A configurable refractory window

This works well for clearly audible shots in typical shooting environments.

### Alternatives considered

#### Fixed amplitude threshold

Very simple, but prone to false triggers from handling noise.

#### Spectral or impulse detection

Potentially more selective, but significantly more complex.

#### Dedicated onset-detection libraries

Capable, but excessive for a single transient event.

### Timing

Shot timestamps are derived from the same monotonic clock used by the tracking
system.

A small timing offset remains due to audio buffering and operating system
latency. This is documented rather than compensated for.

---

## Storage

ShotTrainer uses SQLite through SQLAlchemy.

The database schema is intentionally simple and includes an index on:

```text
(session_id, timestamp)
```

to support efficient trace lookups.

Tracking samples are written in batches to avoid transaction overhead.

### Alternatives considered

#### Parquet for trace data

Potentially more efficient for very large datasets, but introduces additional
complexity and storage formats.

Worth reconsidering if session sizes grow significantly.

#### JSON files

Easy to inspect manually, but poor for querying and large datasets.

---

## Threading

Camera capture and audio capture run on independent worker threads.

Communication occurs through queued Qt signals and a small in-memory buffer of
recent tracking samples.

The UI thread is responsible only for rendering and interaction.

This keeps acquisition and processing work away from the event loop.

---

## Packaging

The first release pipeline used PyInstaller.

It worked well enough to ship Windows, macOS, and Linux builds, but several
long-term maintenance issues emerged.

### Why move to Nuitka?

#### Single source of truth for versioning

PyInstaller required version information in multiple locations.

Nuitka allows the build driver to generate platform metadata from a single
version constant.

#### Smaller and faster bundles

PyInstaller packages a Python interpreter and bytecode archive.

Nuitka compiles the application into native binaries, producing smaller bundles
and faster startup times.

#### Reduced packaging complexity

PySide6, OpenCV, and SoundDevice required custom PyInstaller hook configuration.

Nuitka's plugin system handles most of this automatically.

### Trade-offs

- Longer build times.
- Initial compiler downloads on new systems.
- Additional macOS bundle handling to avoid filename collisions.

### Alternatives considered

#### Briefcase

Briefcase was evaluated because of its packaging and notarisation workflow.

It was ultimately rejected because the existing build pipeline already covered
the required platforms without requiring significant project restructuring.

---

## Accuracy

Accuracy is primarily limited by optics, resolution, and environmental
conditions rather than the software itself.

For detailed discussion, see:

[Accuracy and target sizing](accuracy.md)

The short version. At longer distances, the limiting factor is almost always the
number of usable pixels on the target rather than the tracking algorithm.
