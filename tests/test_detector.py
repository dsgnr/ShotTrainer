"""Detector tests using synthetic images, no camera needed."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from shottrainer.tracking.detector import CircleTargetDetector, DetectorSettings


def _white_canvas(w: int = 640, h: int = 480) -> np.ndarray:
    return np.full((h, w, 3), 255, dtype=np.uint8)


def _draw_circle(img: np.ndarray, x: int, y: int, r: int) -> None:
    cv2.circle(img, (x, y), r, (0, 0, 0), thickness=-1)


def test_detects_centred_circle():
    img = _white_canvas()
    _draw_circle(img, 320, 240, 30)

    det = CircleTargetDetector().detect(img)
    assert det.found
    assert det.x_px == pytest.approx(320.0, abs=2.0)
    assert det.y_px == pytest.approx(240.0, abs=2.0)
    assert det.radius_px == pytest.approx(30.0, abs=2.0)


def test_returns_not_found_on_blank():
    img = _white_canvas()
    det = CircleTargetDetector().detect(img)
    assert not det.found


def test_circle_off_centre_is_located():
    img = _white_canvas()
    _draw_circle(img, 100, 80, 20)
    det = CircleTargetDetector().detect(img)
    assert det.found
    assert det.x_px == pytest.approx(100.0, abs=2.0)
    assert det.y_px == pytest.approx(80.0, abs=2.0)


def test_rejects_clearly_rectangular_shape():
    img = _white_canvas()
    cv2.rectangle(img, (200, 100), (300, 400), (0, 0, 0), thickness=-1)
    det = CircleTargetDetector().detect(img)
    # A 100x300 rectangle is not circular enough to trigger detection.
    assert not det.found


def test_handles_blur_and_noise():
    img = _white_canvas()
    _draw_circle(img, 320, 240, 25)
    img = cv2.GaussianBlur(img, (7, 7), 0)
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 5, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    det = CircleTargetDetector().detect(img)
    assert det.found
    assert det.x_px == pytest.approx(320.0, abs=3.0)
    assert det.y_px == pytest.approx(240.0, abs=3.0)


def test_picks_largest_when_multiple_circles():
    img = _white_canvas()
    _draw_circle(img, 100, 100, 10)
    _draw_circle(img, 400, 300, 40)
    det = CircleTargetDetector().detect(img)
    assert det.found
    # largest circle dominates the score
    assert det.x_px == pytest.approx(400.0, abs=2.0)
    assert det.y_px == pytest.approx(300.0, abs=2.0)


def test_settings_min_radius_excludes_small_circle():
    img = _white_canvas()
    _draw_circle(img, 320, 240, 5)
    det = CircleTargetDetector(DetectorSettings(min_radius_px=20)).detect(img)
    assert not det.found


def test_centroid_uses_image_moments_for_sub_pixel_accuracy():
    # Generate a sub-pixel offset by drawing at a slightly higher resolution
    # and then downscaling. The detector should land within half a pixel.
    big = np.full((960, 1280, 3), 255, dtype=np.uint8)
    cv2.circle(big, (640, 480), 60, (0, 0, 0), thickness=-1)
    img = cv2.resize(big, (640, 480), interpolation=cv2.INTER_AREA)
    det = CircleTargetDetector().detect(img)
    assert det.found
    assert abs(det.x_px - 320.0) < 0.5
    assert abs(det.y_px - 240.0) < 0.5
