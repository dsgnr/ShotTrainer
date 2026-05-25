from __future__ import annotations

import cv2
import numpy as np

from shottrainer.tracking.circle_detector import detect_calibration_circle


def _scene_with_circle(
    centre: tuple[int, int],
    radius: int,
    size: tuple[int, int] = (480, 640),
) -> np.ndarray:
    """White background with a single black filled disc."""
    img = np.full((size[0], size[1], 3), 240, dtype=np.uint8)
    cv2.circle(img, centre, radius, (10, 10, 10), thickness=-1)
    return img


def test_detects_centred_circle():
    img = _scene_with_circle(centre=(320, 240), radius=80)
    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, r = result
    assert abs(cx - 320) <= 1.5
    assert abs(cy - 240) <= 1.5
    assert abs(r - 80) <= 2.0


def test_detects_off_centre_circle():
    img = _scene_with_circle(centre=(150, 320), radius=50)
    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, r = result
    assert abs(cx - 150) <= 1.5
    assert abs(cy - 320) <= 1.5
    assert abs(r - 50) <= 2.0


def test_returns_none_on_blank_frame():
    blank = np.full((480, 640, 3), 240, dtype=np.uint8)
    assert detect_calibration_circle(blank) is None


def test_prefers_circle_over_rectangle():
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    # A long dark rectangle in the corner that should lose to the circle.
    cv2.rectangle(img, (10, 10), (250, 60), (10, 10, 10), thickness=-1)
    cv2.circle(img, (400, 300), 70, (10, 10, 10), thickness=-1)

    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, _ = result
    assert abs(cx - 400) <= 2.0
    assert abs(cy - 300) <= 2.0
