"""Detect the four corners of a paper sheet (A4 by default).

The approach: threshold, find the largest convex quadrilateral, return its
corners ordered top-left, top-right, bottom-right, bottom-left.

Pure function so it can be tested with synthetic frames.
"""

from __future__ import annotations

import cv2
import numpy as np


def detect_sheet_corners(frame_bgr: np.ndarray) -> list[tuple[float, float]] | None:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    best: np.ndarray | None = None
    best_area = 0.0
    image_area = float(frame_bgr.shape[0] * frame_bgr.shape[1])

    for c in contours:
        area = cv2.contourArea(c)
        # Reject anything smaller than 5% of the frame, or essentially the
        # whole frame (likely a background blob, not a sheet).
        if area < 0.05 * image_area or area > 0.97 * image_area:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        if area > best_area:
            best = approx
            best_area = area

    if best is None:
        return None
    return _order_corners([(float(p[0][0]), float(p[0][1])) for p in best])


def _order_corners(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    arr = np.array(pts, dtype=np.float64)
    s = arr.sum(axis=1)
    diff = np.diff(arr, axis=1).ravel()
    tl = arr[np.argmin(s)]
    br = arr[np.argmax(s)]
    tr = arr[np.argmin(diff)]
    bl = arr[np.argmax(diff)]
    return [tuple(tl), tuple(tr), tuple(br), tuple(bl)]
