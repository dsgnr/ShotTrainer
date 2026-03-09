from __future__ import annotations

from pathlib import Path

from shottrainer.app.calibration_store import load_calibration, save_calibration
from shottrainer.tracking.calibration import (
    HomographyCalibration,
    LinearCalibration,
    a4_target_corners,
    fit_homography,
)


def test_returns_none_when_missing(tmp_path: Path):
    assert load_calibration(tmp_path / "nope.json") is None


def test_linear_roundtrip(tmp_path: Path):
    p = tmp_path / "cal.json"
    cal = LinearCalibration(mm_per_pixel=0.42, origin_px=(160.0, 120.0))
    save_calibration(cal, p)
    loaded = load_calibration(p)
    assert isinstance(loaded, LinearCalibration)
    assert loaded.mm_per_pixel == 0.42
    assert loaded.origin_px == (160.0, 120.0)


def test_homography_roundtrip(tmp_path: Path):
    p = tmp_path / "cal.json"
    image_pts = [(100.0, 50.0), (500.0, 50.0), (500.0, 600.0), (100.0, 600.0)]
    target_pts = a4_target_corners("centre")
    cal = fit_homography(image_pts, target_pts)
    save_calibration(cal, p)

    loaded = load_calibration(p)
    assert isinstance(loaded, HomographyCalibration)
    # The reloaded matrix should map the same input points onto the same mm coordinates.
    for img, tgt in zip(image_pts, target_pts, strict=True):
        x_mm, y_mm = loaded.to_mm(*img)
        assert abs(x_mm - tgt[0]) < 1e-6
        assert abs(y_mm - tgt[1]) < 1e-6


def test_save_none_removes_file(tmp_path: Path):
    p = tmp_path / "cal.json"
    save_calibration(LinearCalibration(mm_per_pixel=1.0), p)
    assert p.exists()
    save_calibration(None, p)
    assert not p.exists()


def test_garbage_file_returns_none(tmp_path: Path):
    p = tmp_path / "cal.json"
    p.write_text("not json")
    assert load_calibration(p) is None


def test_unknown_type_returns_none(tmp_path: Path):
    p = tmp_path / "cal.json"
    p.write_text('{"type": "unknown"}')
    assert load_calibration(p) is None
