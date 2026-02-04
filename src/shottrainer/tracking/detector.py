"""Find a black circular target on a light background.

An adaptive threshold turns the frame black and white, then the
detector looks at each contour and picks the most circular one.
``docs/engineering-notes.md`` lists the other approaches we
tried and dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .models import Detection


@dataclass(frozen=True, slots=True)
class DetectorSettings:
    min_radius_px: int = 4
    max_radius_px: int = 200
    blur_kernel: int = 5
    # A real circle scores above 0.7 here. Rectangles come in
    # much lower.
    min_circularity: float = 0.65
    # The adaptive threshold's window has to be larger than the
    # target's edge so it has enough surrounding pixels to compare
    # against.
    adaptive_block_size: int = 31
    adaptive_offset: int = 5


class CircleTargetDetector:
    """Locate the most circle-like dark blob in a frame."""

    def __init__(self, settings: DetectorSettings | None = None) -> None:
        self.settings = settings or DetectorSettings()

    def detect(self, frame_bgr: np.ndarray) -> Detection:
        s = self.settings
        if frame_bgr.ndim == 3:
            grey = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        else:
            grey = frame_bgr

        if s.blur_kernel >= 3:
            grey = cv2.GaussianBlur(grey, (s.blur_kernel, s.blur_kernel), 0)

        block = max(3, s.adaptive_block_size | 1)  # must be odd
        binary = cv2.adaptiveThreshold(
            grey,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            block,
            s.adaptive_offset,
        )

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best: Detection = Detection(found=False)
        best_score = 0.0

        for c in contours:
            area = cv2.contourArea(c)
            if area <= 0:
                continue
            perim = cv2.arcLength(c, True)
            if perim <= 0:
                continue

            radius_est = float(np.sqrt(area / np.pi))
            if radius_est < s.min_radius_px or radius_est > s.max_radius_px:
                continue

            circularity = 4.0 * np.pi * area / (perim * perim)
            if circularity < s.min_circularity:
                continue

            (cx, cy), enclosing_r = cv2.minEnclosingCircle(c)
            if enclosing_r <= 0:
                continue
            # Penalise blobs that don't fill their enclosing circle.
            fill = area / (np.pi * enclosing_r * enclosing_r)
            score = float(circularity * fill)

            if score > best_score:
                best_score = score
                best = Detection(
                    found=True,
                    x_px=float(cx),
                    y_px=float(cy),
                    radius_px=float(enclosing_r),
                    confidence=score,
                )

        return best
