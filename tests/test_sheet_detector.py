from __future__ import annotations

import cv2
import numpy as np
import pytest

from shottrainer.tracking.sheet_detector import detect_sheet_corners


def _scene_with_sheet(corners: list[tuple[int, int]], size: tuple[int, int] = (480, 640)) -> np.ndarray:
    img = np.full((size[0], size[1], 3), 30, dtype=np.uint8)  # dark background
    pts = np.array(corners, dtype=np.int32)
    cv2.fillPoly(img, [pts], (240, 240, 240))  # bright sheet
    return img


def test_detects_axis_aligned_sheet():
    corners = [(100, 80), (540, 80), (540, 400), (100, 400)]
    img = _scene_with_sheet(corners)
    detected = detect_sheet_corners(img)
    assert detected is not None
    detected_set = {(round(x), round(y)) for x, y in detected}
    expected = {(100, 80), (540, 80), (540, 400), (100, 400)}
    # Allow a few pixels of tolerance for the polygon approximation.
    for ex, ey in expected:
        assert any(abs(ex - dx) <= 3 and abs(ey - dy) <= 3 for dx, dy in detected_set)


def test_returns_none_on_blank_frame():
    blank = np.full((480, 640, 3), 30, dtype=np.uint8)
    assert detect_sheet_corners(blank) is None


def test_orders_corners_clockwise_from_top_left():
    corners = [(120, 60), (500, 90), (480, 380), (140, 360)]
    img = _scene_with_sheet(corners)
    detected = detect_sheet_corners(img)
    assert detected is not None
    tl, tr, br, bl = detected
    assert tl[0] < tr[0] and tl[1] < bl[1]
    assert br[0] > bl[0] and br[1] > tr[1]
