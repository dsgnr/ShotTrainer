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


def test_blob_outside_centre_region_is_rejected():
    img = _white_canvas()
    _draw_circle(img, 50, 50, 20)  # well outside the centre
    det = CircleTargetDetector(DetectorSettings(region_fraction=0.5)).detect(img)
    assert not det.found


def test_blob_inside_centre_region_is_accepted():
    img = _white_canvas()
    _draw_circle(img, 320, 240, 20)
    det = CircleTargetDetector(DetectorSettings(region_fraction=0.5)).detect(img)
    assert det.found


def test_full_frame_region_keeps_old_behaviour():
    img = _white_canvas()
    _draw_circle(img, 50, 50, 20)
    det = CircleTargetDetector(DetectorSettings(region_fraction=1.0)).detect(img)
    assert det.found


def test_lock_prefers_close_blob_over_distant_one():
    img = _white_canvas()
    _draw_circle(img, 320, 240, 25)
    det = CircleTargetDetector(DetectorSettings(region_fraction=1.0)).detect(img)
    assert det.found
    primary_x = det.x_px

    # Now both blobs in the same frame: a noise blob slightly closer to
    # the centre, and the original further off. With the lock active,
    # the original wins.
    detector = CircleTargetDetector(
        DetectorSettings(region_fraction=1.0, lock_radius_px=80.0)
    )
    detector.detect(img)  # establish lock at (320, 240)
    img2 = _white_canvas()
    _draw_circle(img2, 320, 240, 25)  # original
    _draw_circle(img2, 200, 240, 27)  # competing blob 120 px away
    second = detector.detect(img2)
    assert second.found
    assert abs(second.x_px - primary_x) < 5.0


def test_lock_released_after_consecutive_misses():
    detector = CircleTargetDetector(
        DetectorSettings(region_fraction=1.0, lock_release_after_misses=3)
    )
    img = _white_canvas()
    _draw_circle(img, 320, 240, 25)
    detector.detect(img)
    assert detector._lock_px is not None

    blank = _white_canvas()
    for _ in range(3):
        detector.detect(blank)
    assert detector._lock_px is None


def test_off_region_blob_is_reported_as_rejected():
    img = _white_canvas()
    _draw_circle(img, 50, 50, 20)  # outside the central region
    det = CircleTargetDetector(DetectorSettings(region_fraction=0.5)).detect(img)
    assert not det.found
    assert det.rejected_outside_region
    assert det.x_px == pytest.approx(50.0, abs=2.0)
    assert det.y_px == pytest.approx(50.0, abs=2.0)
    assert det.radius_px > 0.0


def test_blank_frame_does_not_set_rejected_flag():
    img = _white_canvas()
    det = CircleTargetDetector().detect(img)
    assert not det.found
    assert not det.rejected_outside_region


def test_rejected_flag_clears_when_blob_returns_to_region():
    detector = CircleTargetDetector(DetectorSettings(region_fraction=0.5))
    out = _white_canvas()
    _draw_circle(out, 50, 50, 20)
    rej = detector.detect(out)
    assert rej.rejected_outside_region

    inside = _white_canvas()
    _draw_circle(inside, 320, 240, 20)
    accepted = detector.detect(inside)
    assert accepted.found
    assert not accepted.rejected_outside_region


def test_morphological_opening_severs_thin_bridge_to_neighbour():
    """Adaptive thresholding can pinch the target's contour together
    with a nearby dark feature when the gap between them is small.
    Without the morphological opening pass, the merged contour's
    centroid is biased toward the neighbour. With opening, the bridge
    breaks and the target's centroid stays where it should.

    Mirrors the real-world failure where the trace drifted toward the
    centre when the target moved into a cluttered side of the frame.
    """
    img = _white_canvas()
    # Target circle and a small distractor 4 pixels away, too close
    # for the adaptive threshold to keep them visually separate.
    cv2.circle(img, (320, 240), 20, (40, 40, 40), thickness=-1)
    cv2.circle(img, (348, 240), 6, (40, 40, 40), thickness=-1)
    # A faint grey smear in the gap. With the adaptive threshold's local
    # mean dragged down by both blobs, those grey pixels go binary-on
    # and the contour bridges. Opening severs the bridge.
    cv2.line(img, (340, 240), (342, 240), (180, 180, 180), thickness=2)

    with_opening = CircleTargetDetector(DetectorSettings(opening_kernel_px=3)).detect(img)
    without_opening = CircleTargetDetector(DetectorSettings(opening_kernel_px=0)).detect(img)

    assert with_opening.found
    # Centroid should be on the target, not pulled toward the distractor
    # (which sits at x=348). The opening case stays inside ±2 px of the
    # true centre. The no-opening case is allowed to drift further as
    # documentation of the symptom this test exists to catch.
    assert abs(with_opening.x_px - 320) <= 2.0

    if without_opening.found:
        # If the no-opening detector still sees the target, its centroid
        # should be biased rightward versus the with-opening one. Doesn't
        # have to fail outright. The qualitative direction is the
        # contract.
        assert without_opening.x_px >= with_opening.x_px - 0.5



def test_busy_scene_still_finds_target_and_caps_candidates():
    """A scene full of small dark blobs should not derail the detector.

    Pathological frames (textured walls, lots of paper printed with
    small ink marks) used to expand into thousands of contours, each
    going through the full filter chain. The detector now caps the
    candidate count and prefilters by bounding rect so a busy scene
    can't stall the GUI thread, and it should still latch onto a
    real target sitting in the middle of the noise.
    """
    import numpy as np

    rng = np.random.default_rng(42)
    img = np.full((480, 640, 3), 240, dtype=np.uint8)
    for _ in range(400):
        x = int(rng.integers(0, 640 - 4))
        y = int(rng.integers(0, 480 - 4))
        side = int(rng.integers(2, 5))
        cv2.rectangle(img, (x, y), (x + side, y + side), (10, 10, 10), -1)
    cv2.circle(img, (320, 240), 25, (0, 0, 0), -1)

    detection = CircleTargetDetector().detect(img)
    assert detection.found
    assert abs(detection.x_px - 320) < 5
    assert abs(detection.y_px - 240) < 5


def test_lock_window_prefers_nearby_target_over_far_distractor():
    """With a lock established, a fresh distractor outside the search
    window should be ignored entirely. The cropped findContours loop
    means contours far from the lock never enter the candidate list,
    so even a more "circular" blob far away can't take the lock."""
    detector = CircleTargetDetector(
        DetectorSettings(region_fraction=1.0, lock_radius_px=50.0)
    )

    # Establish the lock on a centred circle.
    img = _white_canvas()
    _draw_circle(img, 320, 240, 25)
    first = detector.detect(img)
    assert first.found

    # Put a much larger distractor far away from the lock. The lock
    # window should keep the detector ignoring it.
    img2 = _white_canvas()
    _draw_circle(img2, 320, 240, 25)
    _draw_circle(img2, 60, 60, 35)
    second = detector.detect(img2)
    assert second.found
    assert abs(second.x_px - 320) < 5
    assert abs(second.y_px - 240) < 5
