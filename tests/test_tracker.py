from __future__ import annotations

import cv2
import numpy as np
import pytest

from shottrainer.tracking.calibration import LinearCalibration
from shottrainer.tracking.tracker import Tracker


def _frame_with_circle(x: int, y: int, r: int = 25) -> np.ndarray:
    img = np.full((480, 640, 3), 255, dtype=np.uint8)
    cv2.circle(img, (x, y), r, (0, 0, 0), thickness=-1)
    return img


def test_tracker_returns_none_when_nothing_detected():
    tracker = Tracker()
    blank = np.full((480, 640, 3), 255, dtype=np.uint8)
    assert tracker.process(blank, timestamp=0.0) is None


def test_tracker_emits_pixel_only_sample_without_calibration():
    tracker = Tracker()
    sample = tracker.process(_frame_with_circle(320, 240), timestamp=1.5)
    assert sample is not None
    assert sample.x_mm is None
    assert sample.y_mm is None
    assert sample.x_px == pytest.approx(320.0, abs=2.0)
    assert sample.timestamp == 1.5
    assert sample.frame_id == 1


def test_tracker_applies_calibration():
    tracker = Tracker(calibration=LinearCalibration(mm_per_pixel=0.5, origin_px=(320.0, 240.0)))
    sample = tracker.process(_frame_with_circle(340, 240), timestamp=0.0)
    assert sample is not None
    assert sample.x_mm == pytest.approx(10.0, abs=1.0)
    assert sample.y_mm == pytest.approx(0.0, abs=1.0)


def test_tracker_increments_frame_id_each_call():
    tracker = Tracker()
    a = tracker.process(_frame_with_circle(320, 240), timestamp=0.0)
    b = tracker.process(_frame_with_circle(320, 240), timestamp=0.1)
    assert a is not None and b is not None
    assert b.frame_id == a.frame_id + 1


def test_manual_point_overrides_detector():
    tracker = Tracker(calibration=LinearCalibration(mm_per_pixel=0.5, origin_px=(320.0, 240.0)))
    tracker.set_manual_point(360.0, 240.0)
    blank = np.full((480, 640, 3), 255, dtype=np.uint8)
    sample = tracker.process(blank, timestamp=0.0)
    assert sample is not None
    assert sample.x_px == 360.0
    assert sample.y_px == 240.0
    assert sample.confidence == 0.0
    assert sample.x_mm == pytest.approx(20.0)


def test_manual_point_can_be_cleared():
    tracker = Tracker()
    tracker.set_manual_point(100.0, 100.0)
    tracker.set_manual_point(None, None)
    assert tracker.manual_point is None
    blank = np.full((480, 640, 3), 255, dtype=np.uint8)
    # Without override, the detector returns nothing for a blank frame.
    assert tracker.process(blank, timestamp=0.0) is None
