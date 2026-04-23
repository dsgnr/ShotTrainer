from __future__ import annotations

import pytest

from shottrainer.tracking.calibration import (
    LinearCalibration,
    fit_circle_calibration,
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


def test_circle_calibration_scale_and_origin():
    # 60 mm circle imaged at 100 px radius -> 0.3 mm/px (negated for the
    # rifle-aim sign convention) with origin at the circle centre.
    cal = fit_circle_calibration(centre_px=(320.0, 240.0), radius_px=100.0, diameter_mm=60.0)

    assert cal.mm_per_pixel == pytest.approx(-0.3)
    assert cal.origin_px == (320.0, 240.0)
    assert cal.diameter_mm == pytest.approx(60.0)

    # Centre maps to (0, 0).
    assert cal.to_mm(320.0, 240.0) == pytest.approx((0.0, 0.0))


def test_circle_calibration_rifle_aim_sign():
    """Target appearing left of frame centre means the rifle is aimed right.

    With the negated mm/px, a pixel x < origin_x must report a *positive*
    mm x (rifle aimed right of centre), and y above origin_y (smaller y
    in image coords) must report a *positive* mm y.
    """
    cal = fit_circle_calibration(centre_px=(320.0, 240.0), radius_px=100.0, diameter_mm=60.0)

    rx_mm, _ = cal.to_mm(220.0, 240.0)  # 100 px to the left
    assert rx_mm > 0.0
    assert rx_mm == pytest.approx(30.0)  # 100 px * 0.3 mm/px

    _, ry_mm = cal.to_mm(320.0, 140.0)  # 100 px above
    assert ry_mm > 0.0
    assert ry_mm == pytest.approx(30.0)


def test_circle_calibration_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        fit_circle_calibration(centre_px=(0.0, 0.0), radius_px=0.0, diameter_mm=60.0)
    with pytest.raises(ValueError):
        fit_circle_calibration(centre_px=(0.0, 0.0), radius_px=10.0, diameter_mm=0.0)
