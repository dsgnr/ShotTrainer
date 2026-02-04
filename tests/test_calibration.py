from __future__ import annotations

import math

import numpy as np
import pytest

from shottrainer.tracking.calibration import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    LinearCalibration,
    a4_target_corners,
    fit_homography,
)


def test_linear_calibration_roundtrip():
    cal = LinearCalibration(mm_per_pixel=0.5, origin_px=(100.0, 200.0))
    x_mm, y_mm = cal.to_mm(120.0, 220.0)
    assert x_mm == pytest.approx(10.0)
    assert y_mm == pytest.approx(10.0)
    x_px, y_px = cal.to_pixels(x_mm, y_mm)
    assert x_px == pytest.approx(120.0)
    assert y_px == pytest.approx(220.0)


def test_linear_calibration_origin_default():
    cal = LinearCalibration(mm_per_pixel=2.0)
    assert cal.to_mm(5.0, 7.0) == (10.0, 14.0)


def test_a4_corners_centre_origin_are_symmetric():
    corners = a4_target_corners("centre")
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    assert math.isclose(min(xs), -A4_WIDTH_MM / 2)
    assert math.isclose(max(xs), A4_WIDTH_MM / 2)
    assert math.isclose(min(ys), -A4_HEIGHT_MM / 2)
    assert math.isclose(max(ys), A4_HEIGHT_MM / 2)


def test_homography_maps_a4_corners_correctly():
    # Image points: an axis-aligned rectangle in pixels.
    image_pts = [(100.0, 50.0), (500.0, 50.0), (500.0, 600.0), (100.0, 600.0)]
    target_pts = a4_target_corners("centre")
    cal = fit_homography(image_pts, target_pts)

    for img, tgt in zip(image_pts, target_pts):
        mm = cal.to_mm(*img)
        assert mm[0] == pytest.approx(tgt[0], abs=1e-6)
        assert mm[1] == pytest.approx(tgt[1], abs=1e-6)


def test_homography_centre_is_zero_zero():
    image_pts = [(100.0, 50.0), (500.0, 50.0), (500.0, 600.0), (100.0, 600.0)]
    target_pts = a4_target_corners("centre")
    cal = fit_homography(image_pts, target_pts)

    cx = (100 + 500) / 2
    cy = (50 + 600) / 2
    mm = cal.to_mm(cx, cy)
    assert mm[0] == pytest.approx(0.0, abs=1e-6)
    assert mm[1] == pytest.approx(0.0, abs=1e-6)


def test_homography_mm_per_pixel_diagnostic():
    image_pts = [(0.0, 0.0), (210.0, 0.0), (210.0, 297.0), (0.0, 297.0)]
    target_pts = a4_target_corners("top-left")
    cal = fit_homography(image_pts, target_pts)
    # 1 pixel should equal 1 mm in this contrived case.
    assert cal.mm_per_pixel_at(50.0, 50.0) == pytest.approx(1.0, abs=1e-6)


def test_homography_requires_four_points():
    with pytest.raises(ValueError):
        fit_homography([(0.0, 0.0), (1.0, 0.0)], [(0.0, 0.0), (1.0, 0.0)])


def test_rifle_homography_negates_target_axes():
    """For a rifle-mounted camera, target image left of frame centre means
    the rifle is aimed right. The rifle homography returns positive-X."""
    from shottrainer.tracking.calibration import fit_rifle_homography

    # An axis-aligned square in pixels, centred at (320, 240).
    image_pts = [(220, 140), (420, 140), (420, 340), (220, 340)]
    # Same square in target millimetres (centre at 0,0).
    target_pts = [
        (-100.0, -100.0),
        (100.0, -100.0),
        (100.0, 100.0),
        (-100.0, 100.0),
    ]
    cal = fit_rifle_homography(image_pts, target_pts)

    # Frame centre maps to (0, 0).
    cx, cy = cal.to_mm(320, 240)
    assert cx == pytest.approx(0.0, abs=1e-6)
    assert cy == pytest.approx(0.0, abs=1e-6)

    # Pixel left of frame centre (target appears left = rifle aimed right)
    # should produce a positive-X mm result.
    rx, _ = cal.to_mm(220, 240)
    assert rx > 0.0
