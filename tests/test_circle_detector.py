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
    """Circle near, but not exactly at, the frame centre. Real users
    won't have it pixel-perfect, so the centre acceptance window
    has to accommodate normal hold drift and aim offset."""
    img = _scene_with_circle(centre=(280, 220), radius=50)
    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, r = result
    assert abs(cx - 280) <= 1.5
    assert abs(cy - 220) <= 1.5
    assert abs(r - 50) <= 2.0


def test_returns_none_on_blank_frame():
    blank = np.full((480, 640, 3), 240, dtype=np.uint8)
    assert detect_calibration_circle(blank) is None


def test_prefers_circle_over_rectangle():
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    # A long dark rectangle in the corner that should lose to the circle.
    cv2.rectangle(img, (10, 10), (250, 60), (10, 10, 10), thickness=-1)
    cv2.circle(img, (320, 240), 70, (10, 10, 10), thickness=-1)

    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, _ = result
    assert abs(cx - 320) <= 2.0
    assert abs(cy - 240) <= 2.0


def test_prefers_central_circle_over_distant_distractor():
    """Mimics the real-world failure: a small calibration circle sits
    near the centre of the frame while a much bigger dark blob (camera
    or scope housing) sits at one edge. The detector should pick the
    central circle even though the distractor is larger."""
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    # Big circular blob far to the right. Like a scope housing.
    cv2.circle(img, (600, 240), 100, (10, 10, 10), thickness=-1)
    # The actual calibration circle, smaller, near the centre.
    cv2.circle(img, (320, 240), 40, (10, 10, 10), thickness=-1)

    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, r = result
    assert abs(cx - 320) <= 2.5
    assert abs(cy - 240) <= 2.5
    assert abs(r - 40) <= 3.0


def test_detects_small_circle():
    """Small circles should still be detected. The user might be far
    from the target with a low-resolution camera. Rejecting on size
    alone gives them no path to calibrate."""
    img = _scene_with_circle(centre=(320, 240), radius=15)
    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, _ = result
    assert abs(cx - 320) <= 2.0
    assert abs(cy - 240) <= 2.0


def test_handles_uneven_lighting():
    """A faint vertical gradient across the paper background. Otsu can
    fail on this but the adaptive thresholds in the multi-strategy
    pool should still recover the circle."""
    img = np.tile(
        np.linspace(180, 240, 640, dtype=np.uint8)[None, :, None], (480, 1, 3)
    ).astype(np.uint8)
    cv2.circle(img, (320, 240), 60, (10, 10, 10), thickness=-1)
    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, r = result
    assert abs(cx - 320) <= 2.0
    assert abs(cy - 240) <= 2.0
    assert abs(r - 60) <= 3.0


def test_rejects_solid_square():
    """A solid black square should not be misidentified as a circle.

    Squares pass loose circularity/fill gates (circularity ~0.785,
    fill ~0.637) so the radius-variance check is what rejects them.
    Mimics the real-world failure where a picture frame on the wall
    was reported as the calibration circle."""
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    cv2.rectangle(img, (220, 140), (420, 340), (10, 10, 10), thickness=-1)
    assert detect_calibration_circle(img) is None


def test_rejects_when_only_distractors_present():
    """No actual circle in the frame, just a square and a long rectangle.
    Detector should return None, not pick the closest non-circle."""
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (200, 200), (10, 10, 10), thickness=-1)
    cv2.rectangle(img, (300, 100), (500, 140), (10, 10, 10), thickness=-1)
    assert detect_calibration_circle(img) is None


def test_circle_wins_over_square_in_same_scene():
    """A circle and a square coexist. The detector picks the circle.

    Both shapes sit roughly central since the centre gate would reject
    anything far off-axis."""
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    cv2.rectangle(img, (160, 160), (300, 300), (10, 10, 10), thickness=-1)
    cv2.circle(img, (400, 280), 50, (10, 10, 10), thickness=-1)
    result = detect_calibration_circle(img)
    assert result is not None
    cx, cy, _ = result
    assert abs(cx - 400) <= 2.0
    assert abs(cy - 280) <= 2.0


def test_rejects_circle_far_from_centre():
    """A small circle near the frame edge is not what the user is
    aiming at. The centre gate rejects it.

    Mirrors the real failure where a small circle on a turret card
    was misidentified even though the user's aim point was clearly
    elsewhere."""
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    cv2.circle(img, (60, 60), 30, (10, 10, 10), thickness=-1)
    assert detect_calibration_circle(img) is None
