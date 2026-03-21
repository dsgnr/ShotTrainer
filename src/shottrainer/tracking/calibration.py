"""Pixel to millimetre conversion.

Two calibration shapes are supported:

- Linear scale: a single mm-per-pixel value, with the origin at a chosen
  pixel. Adequate when the camera is square-on to the target and the
  target plane is small relative to the focal length.
- Homography: a 3x3 matrix mapping image pixels to target millimetres,
  computed from four known correspondences (typically the corners of an
  A4 sheet).

This module is free of OpenCV at import time so the linear path is testable
without it. The homography fitter imports cv2 lazily.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0


@dataclass(frozen=True, slots=True)
class LinearCalibration:
    """Uniform scale calibration. Fast and good enough for square-on setups."""

    mm_per_pixel: float
    origin_px: tuple[float, float] = (0.0, 0.0)

    def to_mm(self, x_px: float, y_px: float) -> tuple[float, float]:
        ox, oy = self.origin_px
        return ((x_px - ox) * self.mm_per_pixel, (y_px - oy) * self.mm_per_pixel)

    def to_pixels(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        ox, oy = self.origin_px
        return (x_mm / self.mm_per_pixel + ox, y_mm / self.mm_per_pixel + oy)


@dataclass(frozen=True, slots=True)
class HomographyCalibration:
    """Perspective-aware calibration via a 3x3 matrix."""

    matrix: np.ndarray = field()
    inverse: np.ndarray = field()
    image_points: tuple[tuple[float, float], ...] = ()
    target_points_mm: tuple[tuple[float, float], ...] = ()

    def to_mm(self, x_px: float, y_px: float) -> tuple[float, float]:
        return _apply_homography(self.matrix, x_px, y_px)

    def to_pixels(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        return _apply_homography(self.inverse, x_mm, y_mm)

    def mm_per_pixel_at(self, x_px: float, y_px: float, delta: float = 1.0) -> float:
        """Local mm/pixel estimate, useful for diagnostics."""
        x0, y0 = self.to_mm(x_px, y_px)
        x1, y1 = self.to_mm(x_px + delta, y_px)
        x2, y2 = self.to_mm(x_px, y_px + delta)
        dx = float(np.hypot(x1 - x0, y1 - y0))
        dy = float(np.hypot(x2 - x0, y2 - y0))
        return (dx + dy) / 2.0

    def diagnostic_mm_per_pixel(self) -> float:
        """Average local mm/pixel at the centroid of the recorded image points.

        Falls back to the origin if no points were recorded.
        """
        if self.image_points:
            cx = sum(p[0] for p in self.image_points) / len(self.image_points)
            cy = sum(p[1] for p in self.image_points) / len(self.image_points)
        else:
            cx, cy = 0.0, 0.0
        return self.mm_per_pixel_at(cx, cy)


def _apply_homography(h: np.ndarray, x: float, y: float) -> tuple[float, float]:
    v = h @ np.array([x, y, 1.0], dtype=np.float64)
    if v[2] == 0:
        return (float("nan"), float("nan"))
    return (float(v[0] / v[2]), float(v[1] / v[2]))


def fit_homography(
    image_points: Sequence[tuple[float, float]],
    target_points_mm: Sequence[tuple[float, float]],
) -> HomographyCalibration:
    """Fit an image to target homography from at least four point pairs."""
    if len(image_points) < 4 or len(image_points) != len(target_points_mm):
        raise ValueError("Need at least four matching point pairs")

    # Lazy import: keep cv2 out of the import path of pure-numeric callers.
    import cv2  # type: ignore[import-not-found]

    src = np.asarray(image_points, dtype=np.float64).reshape(-1, 1, 2)
    dst = np.asarray(target_points_mm, dtype=np.float64).reshape(-1, 1, 2)
    h, _mask = cv2.findHomography(src, dst, method=0)
    if h is None:
        raise ValueError("Failed to fit homography from given points")
    inv = np.linalg.inv(h)
    return HomographyCalibration(
        matrix=h,
        inverse=inv,
        image_points=tuple(map(tuple, image_points)),
        target_points_mm=tuple(map(tuple, target_points_mm)),
    )


def fit_rifle_homography(
    image_points: Sequence[tuple[float, float]],
    target_points_mm: Sequence[tuple[float, float]],
) -> HomographyCalibration:
    """Fit a homography for a barrel-mounted camera looking at a static target.

    The convention this function uses: when the rifle is aimed at the
    target centre during calibration, the *target* (sheet) is centred
    in the camera frame. As the rifle pivots, the target's image moves
    opposite to the rifle's motion. Pulling the rifle right shifts the
    target left in the frame.

    To make the trace read in *aim* coordinates (positive X means the
    rifle is aimed right of the target centre) we negate the target-
    space coordinates before fitting. The resulting homography maps a
    target pixel position to the rifle's aim displacement on the
    target plane.
    """
    inverted = [(-x, -y) for x, y in target_points_mm]
    return fit_homography(image_points, inverted)


def a4_target_corners(origin: str = "centre") -> list[tuple[float, float]]:
    """Return A4 corner coordinates in millimetres.

    Order: top left, top right, bottom right, bottom left.
    Origin is the sheet centre by default so the target hit map is
    centred on (0, 0).
    """
    if origin == "centre":
        hw = A4_WIDTH_MM / 2.0
        hh = A4_HEIGHT_MM / 2.0
        return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    if origin == "top-left":
        return [(0.0, 0.0), (A4_WIDTH_MM, 0.0), (A4_WIDTH_MM, A4_HEIGHT_MM), (0.0, A4_HEIGHT_MM)]
    raise ValueError(f"Unknown origin: {origin}")
