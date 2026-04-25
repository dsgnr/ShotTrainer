"""Detect a single dark circle on a light background for calibration.

Tries several thresholding strategies (Otsu, adaptive at two block
sizes) and pools their candidates, then scores each by a combination
of circularity, fill, size and proximity to the frame centre. The
centre-proximity term is the key practical fix: the user is aiming at
the calibration circle while the frame may also contain large dark
distractors (camera/scope housing, mounting hardware), so "circular and
near where the user is looking" is a much more reliable signal than
"largest dark blob".

Centroids come from image moments for sub-pixel-stable results;
``cv2.minEnclosingCircle`` gives the radius.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

log = logging.getLogger(__name__)

# Gates a candidate must pass to be considered at all. ``_MIN_FILL``
# at 0.85 cleanly rejects squares (which fill ~0.637 of their enclosing
# circle) while still allowing moderately elliptical circles (a 0.7
# aspect-ratio ellipse fills ~0.7 of its enclosing circle, and a more
# typical 0.85 aspect ratio fills ~0.85). ``_MAX_RADIUS_VARIATION`` is
# the real shape gate: how much the contour-point distances to the
# centroid are allowed to vary, normalised by the mean distance. A
# perfect circle scores 0. A square scores ~0.16. A slightly squashed
# circle stays under 0.06.
_MIN_CIRCULARITY = 0.6
_MIN_FILL = 0.85
_MAX_RADIUS_VARIATION = 0.12

# Reject blobs that are tiny (likely noise) or essentially the whole
# frame (likely the background).
_MIN_AREA_FRACTION = 0.0005
_MAX_AREA_FRACTION = 0.5

# The user is aiming at the calibration circle, so the circle should
# sit near the centre of the frame. Anything beyond this fraction of
# the frame's half-diagonal is rejected outright. This keeps small
# distractor circles in the periphery from being misidentified.
_MAX_CENTRE_DISTANCE_FRACTION = 0.4


def detect_calibration_circle(
    frame_bgr: np.ndarray,
) -> tuple[float, float, float] | None:
    """Return ``(cx_px, cy_px, radius_px)`` of the best calibration circle.

    Returns ``None`` if no convincing circle was found.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    h, w = gray.shape[:2]
    image_area = float(h * w)
    cx_frame = w / 2.0
    cy_frame = h / 2.0
    # Diagonal/2. Used to normalise the centre-proximity score so the
    # weighting is independent of resolution.
    half_diag = float(np.hypot(cx_frame, cy_frame))
    max_centre_distance = half_diag * _MAX_CENTRE_DISTANCE_FRACTION

    candidates: list[tuple[float, float, float, float]] = []  # (cx, cy, r, score)

    for binary in _binarisations(blurred):
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            cand = _score_contour(
                c,
                image_area,
                cx_frame,
                cy_frame,
                half_diag,
                max_centre_distance,
            )
            if cand is not None:
                candidates.append(cand)

    if not candidates:
        # Re-walk the contours collecting per-stage rejection counts so
        # the user (and us) can see *why* nothing matched. This is the
        # single most common support question and is otherwise opaque.
        rejection_summary = _summarise_rejections(
            blurred, image_area, cx_frame, cy_frame, max_centre_distance
        )
        log.info("Calibration detect: no circle. %s", rejection_summary)
        return None

    cx, cy, r, _ = max(candidates, key=lambda t: t[3])
    log.debug(
        "Calibration detect: chose circle at (%.1f, %.1f) r=%.1f from %d candidates",
        cx, cy, r, len(candidates),
    )
    return (cx, cy, r)


def _summarise_rejections(
    blurred: np.ndarray,
    image_area: float,
    cx_frame: float,
    cy_frame: float,
    max_centre_distance: float,
) -> str:
    """Tally why each contour was thrown out.

    Walks the same multi-strategy binarisations and records which gate
    each contour failed. Returned as a one-line string for the log so
    a glance at the log explains a "Could not find a circle" result.
    """
    counts = {
        "considered": 0,
        "size": 0,
        "perimeter": 0,
        "circularity": 0,
        "fill": 0,
        "moments": 0,
        "shape": 0,
        "centre": 0,
    }
    for binary in _binarisations(blurred):
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            counts["considered"] += 1
            stage = _rejection_stage(c, image_area, cx_frame, cy_frame, max_centre_distance)
            if stage is not None:
                counts[stage] += 1
    return ", ".join(f"{k}={v}" for k, v in counts.items() if v)


def _rejection_stage(
    contour: np.ndarray,
    image_area: float,
    cx_frame: float,
    cy_frame: float,
    max_centre_distance: float,
) -> str | None:
    """Return the name of the gate that rejected ``contour``, or ``None``."""
    area = cv2.contourArea(contour)
    if area < _MIN_AREA_FRACTION * image_area or area > _MAX_AREA_FRACTION * image_area:
        return "size"
    perim = cv2.arcLength(contour, True)
    if perim <= 0:
        return "perimeter"
    circularity = 4.0 * np.pi * area / (perim * perim)
    if circularity < _MIN_CIRCULARITY:
        return "circularity"
    (_, _), enclosing_r = cv2.minEnclosingCircle(contour)
    if enclosing_r <= 0:
        return "size"
    fill = area / (np.pi * enclosing_r * enclosing_r)
    if fill < _MIN_FILL:
        return "fill"
    m = cv2.moments(contour)
    if m["m00"] <= 0:
        return "moments"
    cx = m["m10"] / m["m00"]
    cy = m["m01"] / m["m00"]
    distance = float(np.hypot(cx - cx_frame, cy - cy_frame))
    if distance > max_centre_distance:
        return "centre"
    points = contour.reshape(-1, 2).astype(np.float64)
    distances = np.hypot(points[:, 0] - cx, points[:, 1] - cy)
    mean_distance = float(np.mean(distances))
    if mean_distance <= 0:
        return "shape"
    if float(np.std(distances) / mean_distance) > _MAX_RADIUS_VARIATION:
        return "shape"
    return None


def _binarisations(blurred: np.ndarray):
    """Yield several binary masks of dark blobs.

    Pooling candidates from multiple thresholders means a circle that
    one strategy misses (e.g. Otsu when the scene has lots of dark
    competing blobs) can still be found by another. Each mask is a
    full-frame binary image where dark pixels become foreground (255).
    """
    # Otsu on the inverted image. Excellent for a high-contrast printed
    # circle on white paper.
    _, otsu = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    yield otsu

    # Adaptive thresholds at two block sizes so the strategy works for
    # both small and large circles in the frame. Block size must be odd.
    for block in (31, 91):
        adaptive = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            block,
            5,
        )
        yield adaptive


def _score_contour(
    contour: np.ndarray,
    image_area: float,
    cx_frame: float,
    cy_frame: float,
    half_diag: float,
    max_centre_distance: float,
) -> tuple[float, float, float, float] | None:
    """Return ``(cx, cy, r, score)`` for a contour, or ``None`` if rejected."""
    area = cv2.contourArea(contour)
    if area < _MIN_AREA_FRACTION * image_area or area > _MAX_AREA_FRACTION * image_area:
        return None
    perim = cv2.arcLength(contour, True)
    if perim <= 0:
        return None

    circularity = 4.0 * np.pi * area / (perim * perim)
    if circularity < _MIN_CIRCULARITY:
        return None

    (_, _), enclosing_r = cv2.minEnclosingCircle(contour)
    if enclosing_r <= 0:
        return None
    fill = area / (np.pi * enclosing_r * enclosing_r)
    if fill < _MIN_FILL:
        return None

    m = cv2.moments(contour)
    if m["m00"] <= 0:
        return None
    cx = m["m10"] / m["m00"]
    cy = m["m01"] / m["m00"]

    # Hard centre gate: the user is aiming at the circle, so it has to
    # be near the middle of the frame. Without this gate, small
    # circular distractors elsewhere in the scene (turret cards,
    # buttons, etc.) win on shape score even though the user clearly
    # isn't aiming at them.
    distance = float(np.hypot(cx - cx_frame, cy - cy_frame))
    if distance > max_centre_distance:
        return None

    # Radius variance: distance from each contour point to the centroid,
    # normalised by the mean distance. A perfect circle has zero
    # variance. A square has ~16%. An ellipse with 0.85 aspect ratio
    # has ~5%. This is the real shape test. Circularity and fill are
    # both perimeter/area metrics and can be fooled by a sufficiently
    # convex non-circular shape (e.g. a black square frame on a wall).
    points = contour.reshape(-1, 2).astype(np.float64)
    distances = np.hypot(points[:, 0] - cx, points[:, 1] - cy)
    mean_distance = float(np.mean(distances))
    if mean_distance <= 0:
        return None
    radius_variation = float(np.std(distances) / mean_distance)
    if radius_variation > _MAX_RADIUS_VARIATION:
        return None

    # Centre proximity: 1.0 at the exact centre, falling to 0.0 at the
    # edge of the acceptance window. Used as a tiebreaker once the hard
    # gate above has filtered out everything obviously off-target.
    centre_term = 1.0 - (distance / max_centre_distance)

    # Size term: prefer larger blobs but with diminishing returns, so a
    # giant scope housing doesn't automatically beat a smaller circle of
    # perfect shape near the frame centre.
    size_term = float(np.sqrt(area / image_area))

    score = float(circularity * fill * size_term * (0.3 + centre_term))
    return (float(cx), float(cy), float(enclosing_r), score)
