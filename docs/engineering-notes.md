# Engineering notes

A running log of decisions, alternatives, and trade-offs. Written during
development so the reasoning isn't lost.

## Target detection

The detector tries Hough circle detection first
(`cv2.HoughCircles`). Hough works on the image gradient directly,
so it finds the circle as a whole even when the target has scoring
rings or internal white lines that would split a thresholded binary
into separate contours. When Hough finds a circle in the allowed
radius range, it wins. This solved the problem where the tracker
would jump between different ring fragments frame-to-frame on
federation targets.

When Hough fails (small targets, poor contrast, unusual marks) the
detector falls back to the contour-based approach: adaptive
threshold, morphological opening (to sever bridges to nearby dark
patches), morphological closing (to fill narrow ring gaps inside
the target), contour extraction, and scoring by circularity and
fill ratio. The fallback still works well for plain printed circles
without internal detail.

Other approaches I tried or considered:

- Template matching. Fast, but doesn't generalise across distances
  or zoom without a pyramid, and at that point you've written most
  of a detector.
- ArUco fiducials. Probably the most robust option if you can stick
  one near the target, but the whole idea was to use a plain
  printed sheet, so that wasn't on the table.
- Manual selection is still there as a fallback when the auto
  detector gives up. The user clicks the centre of the target.

## Tracking

Every frame, find the printed circle, divide its known diameter (mm)
by twice its detected radius (px) to get a per-frame mm/px, and
report the rifle's aim as frame-centre minus circle-centre, scaled to
mm. Both the radius and the centroid are smoothed with a short EMA
(~20 frames) so detector jitter doesn't bleed into the trace. There
is no separate calibration step.

This is the third design I tried. The first two each got something
embarrassingly wrong in user testing, so it's worth writing down what
went wrong and why.

### v1: four-corner A4 sheet > homography

The first attempt was the classic computer-vision approach. Print an
A4 sheet, find the four corners, fit a homography
(`cv2.findHomography`) that maps image pixels to target millimetres,
persist it, reuse forever.

The setup friction killed it on its own. Pinning the sheet, getting
all four corners to detect reliably, and re-running the calibration
every time anything moved was more ceremony than the rest of the app
put together.

It also drifted on tilt. A homography compensates for plane tilt at
the moment of calibration, but moving the rifle into prone changed
the camera-to-sheet relationship and the trace was wrong by a small
but visible amount across the whole field.

The worst part was that the failure mode was invisible. The
calibration dialog only showed a single mm/px figure, which doesn't
tell you whether the four image-space points actually round-trip back
to the four target-space corners. One build shipped with a botched
detector lock and the homography quietly embedded the wrong corner.
The trace still looked believable. It was about 30% off.

### v2: single circle > linear or homography calibration

v2 dropped the four-corner sheet for a single printed circle of
known diameter. The circle was easier to detect, easier to print
(the marker-sheet dialog), and the calibration code shrank to a
linear scale with origin at the circle's centre. When the imaged
circle was visibly elliptical (off-axis camera) the calibration
fitted an ellipse and built a homography from the four ellipse-
axis points. The linear fit was the round-circle special case.

This worked for the most part, but it surfaced a pile of secondary
problems.

The detector was easy to confuse. It would lock onto picture frames
on the wall, dark turret cards on the scope, the bore opening of the
camera lens itself. Each fix narrowed one failure mode and introduced
the next. Radius variance to reject squares brought back picture
frames. A centre-proximity gate to prefer the central blob caused it
to ignore the real target if the camera was framed slightly off. A
hard size floor helped indoors but failed at distance. Tests caught
the symptoms. In practice users mostly just hit "Pick manually".

There was also drift between calibration and use. Calibrating
standing up and then dropping into prone shifted the camera-to-target
distance by 10–30 cm. The persisted homography didn't know about
that, so the trace was off by 5–10% during shooting. I added an
auto-scale layer that compared the live target's pixel radius against
the calibration-time radius and applied a corrective multiplier, with
a "+4%" badge in the header so you could see when it was actually
doing something.

By the end the calibration flow had three preferences, two stored
files, two dialogs and one in-line fallback path, mostly to paper
over differences between the calibration scene and the shooting
scene.

### v3: live circle, no calibration

The thing that bothered me about v2 was that "calibration" was a
stale snapshot of a relationship the app could measure live. If the
same printed circle is found every frame and we know its diameter,
we already have the mm/px scale.

Trade-offs:

- **The circle has to stay in frame.** If the rifle pivots far
  enough that the circle leaves the field of view there's no
  scale signal and the trace pauses until it returns. Documented
  as a limitation. Not papered over.
- **Direction is image-plane, not rifle-plane.** A camera rolled
  relative to the rifle bleeds horizontal aim into a small
  vertical component, and vice versa. The trace's *magnitude* is
  rotation-invariant. The *direction* isn't. The two `Invert
  trace` toggles in Preferences cover full 90° / 180° flips.
  Small roll angles (a few degrees) live with the trade-off
  rather than a full image-rotation pipeline.
- **Camera intrinsics.** Lens distortion is a separate problem,
  still not attempted. The simple per-frame scale handles
  distance and zoom only. If a future setup demands it, the
  classic answer (chessboard-based `cv2.calibrateCamera`,
  undistort every frame upstream of the detector) slots in
  cleanly without touching anything in the tracker itself.

The detector itself survived all three iterations roughly intact.
The pipeline around it (calibration, persistence, the meaning of
"mm/px") is what kept getting rewritten.

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

The first packaging pass used PyInstaller. Broad platform coverage,
nothing new to learn, fastest path to a distributable artefact. It
ran on PyInstaller long enough to ship Windows and macOS installers
and a Linux tarball.

Nuitka took over after a few PyInstaller failings started to
add up:

- **Version drift.** The macOS bundle's `Info.plist` lived in a
  templated file separate from `pyproject.toml`, so the version had
  to be remembered in two places. Nuitka derives the plist values
  from command-line flags in the build driver, so a single constant
  in `packaging/build_nuitka.py` is the source of truth.
- **Bundle shape.** PyInstaller produces a frozen interpreter plus a
  zip of pyc files. Nuitka compiles the Python source to C and emits
  a real native binary. The resulting bundles are smaller and start
  faster.
- **Hook surface.** PySide6, OpenCV and SoundDevice each needed their
  own PyInstaller hook config (`collect_dynamic_libs`,
  `collect_data_files`, `collect_submodules`). Nuitka's
  `--enable-plugin=pyside6` and the standard import-graph walk cover
  the same ground without the spec file.

Tradeoffs:

- Compile time goes from seconds to 5-15 minutes per platform. CI feels
  it more than local dev.
- Nuitka downloads a C compiler the first time it runs on a fresh
  machine. The build driver passes `--assume-yes-for-downloads` so
  this isn't interactive.
- macOS has a case-insensitive filesystem (APFS by default), so the
  bundle's `Contents/MacOS/ShotTrainer` binary collides with the
  compiled `Contents/MacOS/shottrainer/` package directory placed
  alongside it. The driver renames the macOS binary to
  `ShotTrainer-bin` and lets `CFBundleExecutable` point at it.

Briefcase was considered as a more opinionated alternative that bakes
notarisation and Linux installers into the build pipeline. It was set
aside because the existing installer scripts (`make_dmg.sh`,
`shottrainer.iss`) already cover the same ground without the
project-layout churn Briefcase requires.

## Accuracy

See [`accuracy.md`](accuracy.md). TLDR at long ranges the
limit is camera resolution and optics, not the software.
