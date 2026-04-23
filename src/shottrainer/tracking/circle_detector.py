"""Detect a single dark circle on a light background for calibration.

Mirrors the live target detector's approach (adaptive threshold,
contour analysis, circularity score) but tuned for a one-shot search:
no temporal lock, no centred acceptance region. The largest blob whose
shape passes the circularity and fill checks wins, and its
:func:`cv2.minEnclosingCircle` gives the radius. The centroid comes
from image moments for a sub-pixel-stable result.
"""

from __future__ import annotations

import cv2
import numpy as np

# Match the live detector's defaults so a circle that tracks at runtime
# also calibrates well.
_BLUR_KERNEL = 5
_ADAPTIVE_BLOCK_SIZE = 31
_ADAPTIVE_OFFSET = 5
_MIN_CIRCULARITY = 0.7
_MIN_FILL = 0.7
# Reject blobs that are tiny relative to the frame (likely noise) or
# essentially the whole frame (likely the background).
_MIN_AREA_FRACTION = 0.001
_MAX_AREA_FRACTION = 0.6


def detect_calibration_circle(
    frame_bgr: np.ndarray,
) -> tuple[float, float, float] | None:
    """Return ``(cx_px, cy_px, radius_px)`` of the most circular dark blob.

    Returns ``None`` if no convincing circle was found.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr
    blurred = cv2.GaussianBlur(gray, (_BLUR_KERNEL, _BLUR_KERNEL), 0)

    block = max(3, _ADAPTIVE_BLOCK_SIZE | 1)  # must be odd
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        _ADAPTIVE_OFFSET,
    )

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h, w = gray.shape[:2]
    image_area = float(h * w)
    min_area = _MIN_AREA_FRACTION * image_area
    max_area = _MAX_AREA_FRACTION * image_area

    best: tuple[float, float, float] | None = None
    best_score = 0.0

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        perim = cv2.arcLength(c, True)
        if perim <= 0:
            continue
        circularity = 4.0 * np.pi * area / (perim * perim)
        if circularity < _MIN_CIRCULARITY:
            continue

        (_, _), enclosing_r = cv2.minEnclosingCircle(c)
        if enclosing_r <= 0:
            continue
        fill = area / (np.pi * enclosing_r * enclosing_r)
        if fill < _MIN_FILL:
            continue

        m = cv2.moments(c)
        if m["m00"] <= 0:
            continue
        cx = m["m10"] / m["m00"]
        cy = m["m01"] / m["m00"]

        # Prefer larger, rounder, fuller blobs. Multiplying by the area
        # biases toward the calibration circle over small noise blobs that
        # might score well on shape alone.
        score = float(circularity * fill * area)
        if score > best_score:
            best_score = score
            best = (float(cx), float(cy), float(enclosing_r))

    return best
