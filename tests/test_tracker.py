"""Tracker tests using synthetic frames, no camera needed."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from shottrainer.tracking.tracker import Tracker


def _frame_with_circle(
    cx: int,
    cy: int,
    radius: int = 25,
    width: int = 640,
    height: int = 480,
) -> np.ndarray:
    """A white frame with a single black circle. The frame centre is
    at ``(width / 2, height / 2)`` for the default 640x480 size."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.circle(img, (cx, cy), radius, (0, 0, 0), thickness=-1)
    return img


def _converge(tracker: Tracker, frame: np.ndarray, *, frames: int = 60) -> None:
    """Drive the tracker for enough frames to settle the radius EMA."""
    for _ in range(frames):
        tracker.process(frame, timestamp=0.0)


def test_returns_none_when_no_circle_visible():
    tracker = Tracker(circle_diameter_mm=60.0)
    blank = np.full((480, 640, 3), 255, dtype=np.uint8)
    assert tracker.process(blank, timestamp=0.0) is None


def test_centre_aim_reports_zero_offset():
    """Circle dead-centre in the frame means the rifle is pointing
    exactly at the circle's centre, so the aim should be (0, 0)."""
    tracker = Tracker(circle_diameter_mm=60.0)
    sample = tracker.process(_frame_with_circle(320, 240, radius=30), timestamp=0.0)
    assert sample is not None
    assert sample.x_mm == pytest.approx(0.0, abs=1.0)
    assert sample.y_mm == pytest.approx(0.0, abs=1.0)


def test_circle_left_of_centre_means_aim_right():
    """When the circle slides 100 px left of frame centre, the rifle
    is aimed 100 px worth of mm to the *right* of the circle. With a
    60 mm circle imaged at 30 px radius, mm/px is 1.0, so the aim is
    +100 mm in x."""
    tracker = Tracker(circle_diameter_mm=60.0)
    frame = _frame_with_circle(220, 240, radius=30)
    _converge(tracker, frame)

    sample = tracker.process(frame, timestamp=0.0)
    assert sample is not None
    assert sample.x_mm == pytest.approx(100.0, abs=2.0)
    assert sample.y_mm == pytest.approx(0.0, abs=2.0)


def test_circle_above_centre_means_aim_down():
    """When the camera tilts up the imaged circle slides up in pixel
    space (smaller y, since image y increases downward). With the
    rifle pointing *down*, the trace should read positive y_mm so
    the target view draws the marker below the centre."""
    tracker = Tracker(circle_diameter_mm=60.0)
    frame = _frame_with_circle(320, 180, radius=30)
    _converge(tracker, frame)

    sample = tracker.process(frame, timestamp=0.0)
    assert sample is not None
    # 60 px gap, 60 mm circle imaged at 30 px radius => 1 mm/px => 60 mm.
    assert sample.y_mm == pytest.approx(60.0, abs=2.0)


def test_scale_uses_live_radius_so_distance_changes_self_correct():
    """A circle 80 px left of frame centre at radius 40 reads the
    same mm offset as the same setup at radius 20. The live mm/px
    is derived from the radius, so the answer is invariant to distance.
    The "near" tracker reads 60 mm (80 / (2*40) * 60). The "far"
    tracker reads 120 mm (80 / (2*20) * 60). Different mm values are
    expected here because the *physical* aim offset is different.
    The property under test is that mm/px stays right when the
    distance changes."""
    near = Tracker(circle_diameter_mm=60.0)
    far = Tracker(circle_diameter_mm=60.0)

    near_frame = _frame_with_circle(240, 240, radius=40)
    far_frame = _frame_with_circle(240, 240, radius=20)
    _converge(near, near_frame)
    _converge(far, far_frame)

    near_sample = near.process(near_frame, timestamp=0.0)
    far_sample = far.process(far_frame, timestamp=0.0)
    assert near_sample is not None
    assert far_sample is not None

    assert near.mm_per_pixel == pytest.approx(0.75, abs=0.05)
    assert far.mm_per_pixel == pytest.approx(1.5, abs=0.05)
    assert near_sample.x_mm == pytest.approx(60.0, abs=3.0)
    assert far_sample.x_mm == pytest.approx(120.0, abs=3.0)


def test_diameter_change_reseeds_smoothed_radius():
    """A new diameter implies the previous EMA's radius (in pixels)
    no longer corresponds to the current target, so the EMA re-converges."""
    tracker = Tracker(circle_diameter_mm=60.0)
    _converge(tracker, _frame_with_circle(320, 240, radius=30))
    assert tracker.mm_per_pixel == pytest.approx(1.0, abs=0.05)

    tracker.set_circle_diameter_mm(120.0)
    # Until a new sample arrives the smoothed radius is None.
    assert tracker.mm_per_pixel is None

    _converge(tracker, _frame_with_circle(320, 240, radius=30))
    # 120 mm / (2 * 30 px) = 2 mm/px.
    assert tracker.mm_per_pixel == pytest.approx(2.0, abs=0.05)


def test_invert_horizontal_flips_x_only():
    tracker = Tracker(circle_diameter_mm=60.0)
    frame = _frame_with_circle(220, 240, radius=30)  # circle 100 px left of centre
    _converge(tracker, frame)
    baseline = tracker.process(frame, timestamp=0.0)
    assert baseline is not None

    tracker.set_trace_inversion(invert_x=True, invert_y=False)
    flipped = tracker.process(frame, timestamp=0.0)
    assert flipped is not None
    assert flipped.x_mm == pytest.approx(-baseline.x_mm, abs=0.5)
    assert flipped.y_mm == pytest.approx(baseline.y_mm, abs=0.5)


def test_invert_vertical_flips_y_only():
    tracker = Tracker(circle_diameter_mm=60.0)
    frame = _frame_with_circle(320, 180, radius=30)
    _converge(tracker, frame)
    baseline = tracker.process(frame, timestamp=0.0)
    assert baseline is not None

    tracker.set_trace_inversion(invert_x=False, invert_y=True)
    flipped = tracker.process(frame, timestamp=0.0)
    assert flipped is not None
    assert flipped.x_mm == pytest.approx(baseline.x_mm, abs=0.5)
    assert flipped.y_mm == pytest.approx(-baseline.y_mm, abs=0.5)


def test_zero_on_aim_pins_current_position_to_origin():
    tracker = Tracker(circle_diameter_mm=60.0)
    _converge(tracker, _frame_with_circle(220, 240, radius=30))
    tracker.process(_frame_with_circle(220, 240, radius=30), timestamp=0.0)

    assert tracker.zero_at_last_sample()

    sample = tracker.process(_frame_with_circle(220, 240, radius=30), timestamp=0.1)
    assert sample is not None
    assert sample.x_mm == pytest.approx(0.0, abs=1.0)
    assert sample.y_mm == pytest.approx(0.0, abs=1.0)


def test_zero_on_aim_returns_false_with_no_sample():
    tracker = Tracker(circle_diameter_mm=60.0)
    assert tracker.zero_at_last_sample() is False


def test_clear_zero_restores_circle_centre_origin():
    tracker = Tracker(circle_diameter_mm=60.0)
    frame = _frame_with_circle(220, 240, radius=30)
    _converge(tracker, frame)
    tracker.process(frame, timestamp=0.0)
    tracker.zero_at_last_sample()

    tracker.clear_zero_offset()
    sample = tracker.process(frame, timestamp=0.0)
    assert sample is not None
    # Without a zero offset the circle 100 px left of centre maps back
    # to "rifle aimed +100 mm right of circle centre".
    assert sample.x_mm == pytest.approx(100.0, abs=2.0)


def test_diameter_must_be_positive():
    with pytest.raises(ValueError):
        Tracker(circle_diameter_mm=0.0)
    tracker = Tracker(circle_diameter_mm=60.0)
    with pytest.raises(ValueError):
        tracker.set_circle_diameter_mm(-1.0)


def test_frame_id_strictly_increases_when_not_supplied():
    tracker = Tracker(circle_diameter_mm=60.0)
    frame = _frame_with_circle(320, 240, radius=30)
    a = tracker.process(frame, timestamp=0.0)
    b = tracker.process(frame, timestamp=0.0)
    assert a is not None and b is not None
    assert b.frame_id == a.frame_id + 1


def test_supplied_frame_id_is_recorded_verbatim():
    tracker = Tracker(circle_diameter_mm=60.0)
    sample = tracker.process(_frame_with_circle(320, 240, radius=30), timestamp=0.0, frame_id=42)
    assert sample is not None
    assert sample.frame_id == 42


def _frame_with_ellipse(
    cx: int,
    cy: int,
    semi_major: int,
    semi_minor: int,
    angle: float = 0.0,
    width: int = 640,
    height: int = 480,
) -> np.ndarray:
    """A white frame with a single black ellipse.

    OpenCV's ``ellipse`` takes *full* axis lengths and degrees. The
    helper takes semi-axes and a degrees angle to match the convention
    the rest of the tracker uses.
    """
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    cv2.ellipse(
        img,
        center=(cx, cy),
        axes=(semi_major, semi_minor),
        angle=angle,
        startAngle=0.0,
        endAngle=360.0,
        color=(0, 0, 0),
        thickness=-1,
    )
    return img


def test_horizontal_axis_unaffected_by_vertical_foreshortening():
    """A camera tilted up or down images the printed circle as an
    ellipse foreshortened along the tilt axis. The horizontal aim
    offset must still read correctly. The ellipse's wide axis sets
    the horizontal scale, which matches the printed circle's
    diameter."""
    tracker = Tracker(circle_diameter_mm=60.0)
    # Circle at radius 30 px imaged as 30 wide, 18 tall (60 % squash
    # along vertical, what a 60-degree-down tilt would look like).
    frame = _frame_with_ellipse(220, 240, semi_major=30, semi_minor=18, angle=0.0)
    _converge(tracker, frame)

    sample = tracker.process(frame, timestamp=0.0)
    assert sample is not None
    # 100 px of horizontal offset, mm/px along x = 60 / (2*30) = 1.0,
    # so the trace should read 100 mm.
    assert sample.x_mm == pytest.approx(100.0, abs=2.0)
    assert sample.y_mm == pytest.approx(0.0, abs=2.0)


def test_vertical_axis_compensates_for_foreshortening():
    """The fix the test exists for. Same foreshortened ellipse, this
    time placed 50 px below the frame centre, meaning the rifle is
    aimed up. The trace should report the *true* mm offset on the
    target plane (using the printed diameter and the minor axis), not
    the foreshortened image-plane distance.

    With the rifle-aim sign flip the result reads negative because aim
    up corresponds to negative y on the on-screen target view."""
    tracker = Tracker(circle_diameter_mm=60.0)
    frame = _frame_with_ellipse(320, 290, semi_major=30, semi_minor=18, angle=0.0)
    _converge(tracker, frame)

    sample = tracker.process(frame, timestamp=0.0)
    assert sample is not None
    # 50 px of vertical offset, mm/px along y = 60 / (2*18) ≈ 1.667,
    # so the trace should read about 83 mm in magnitude, much more
    # than the 50 mm a naive single-radius scale would give.
    assert sample.x_mm == pytest.approx(0.0, abs=2.0)
    assert sample.y_mm == pytest.approx(-83.0, abs=4.0)
