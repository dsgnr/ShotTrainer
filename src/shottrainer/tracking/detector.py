"""Find a black circular target on a light background.

The approach is deliberately simple. An adaptive threshold
binarises the frame, then the detector walks the contours and
picks the most circular one. ``docs/engineering-notes.md``
lists the alternatives that were tried and discarded.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .models import Detection


@dataclass(frozen=True, slots=True)
class DetectorSettings:
    """Tunable knobs for the circle detector."""

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
    # Fraction of the frame width and height to keep when looking
    # for the target. ``1.0`` uses the whole frame. Smaller values
    # restrict the search to a centred box and reject blobs near
    # the edges.
    region_fraction: float = 0.7
    # Soft lock. Once we've found a target the detector prefers
    # candidates close to where it last sat. Inside
    # ``lock_radius_px`` the score gets a boost. Further out the
    # score gets damped, so a different blob has to be very stable
    # or very close to take the lock.
    lock_radius_px: float = 80.0
    lock_boost: float = 1.5
    # If the detector misses (or only sees off-region candidates)
    # for this many frames in a row, the lock is dropped so a
    # fresh acquisition can happen anywhere on the frame.
    lock_release_after_misses: int = 8


class CircleTargetDetector:
    """Pick out the most circle-like dark blob in a frame.

    The detector keeps a soft lock on the last accepted centroid.
    Blobs near it get a score bump, blobs further away get a
    penalty. A short noise blob can't snatch the tracker mid-trace
    that way, but a real new target still acquires after a few
    consistent frames.
    """

    def __init__(self, settings: DetectorSettings | None = None) -> None:
        self.settings = settings or DetectorSettings()
        self._lock_px: tuple[float, float] | None = None
        self._consecutive_misses: int = 0

    def reset_lock(self) -> None:
        """Drop any soft lock so the next frame is treated as a fresh start."""
        self._lock_px = None
        self._consecutive_misses = 0

    def detect(self, frame_bgr: np.ndarray) -> Detection:
        """Return the best detection in ``frame_bgr``, or one with ``found=False``."""
        s = self.settings
        grey = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY) if frame_bgr.ndim == 3 else frame_bgr

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

        # The central acceptance region. Centroids that fall
        # outside it are rejected so off-axis blobs (frame edges,
        # other papers in shot) don't capture the tracker.
        h, w = grey.shape[:2]
        region_fraction = max(0.05, min(1.0, s.region_fraction))
        half_w = w * region_fraction / 2.0
        half_h = h * region_fraction / 2.0
        cx_frame = w / 2.0
        cy_frame = h / 2.0

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

            (_, _), enclosing_r = cv2.minEnclosingCircle(c)
            if enclosing_r <= 0:
                continue
            # Use image moments for the centroid. More stable
            # than the minimum-enclosing-circle centre when the
            # contour is noisy.
            m = cv2.moments(c)
            if m["m00"] <= 0:
                continue
            cx = m["m10"] / m["m00"]
            cy = m["m01"] / m["m00"]
            if abs(cx - cx_frame) > half_w or abs(cy - cy_frame) > half_h:
                continue
            # Penalise blobs that don't fill their enclosing circle.
            fill = area / (np.pi * enclosing_r * enclosing_r)
            score = float(circularity * fill)

            # Soft-lock score adjustment. Inside
            # ``lock_radius_px`` the boost is strongest at the
            # lock centre. Outside the radius the score is damped
            # so a far-away blob has to be a lot more convincing
            # to take the lock.
            if self._lock_px is not None:
                lx, ly = self._lock_px
                d = float(np.hypot(cx - lx, cy - ly))
                radius = max(1.0, s.lock_radius_px)
                if d <= radius:
                    score *= 1.0 + (s.lock_boost - 1.0) * (1.0 - d / radius)
                else:
                    # Quadratic damping past the lock radius. At
                    # two lock radii away the score is roughly
                    # halved.
                    score *= 1.0 / (1.0 + ((d - radius) / radius) ** 2)

            if score > best_score:
                best_score = score
                best = Detection(
                    found=True,
                    x_px=float(cx),
                    y_px=float(cy),
                    radius_px=float(enclosing_r),
                    confidence=score,
                )

        if best.found:
            self._lock_px = (best.x_px, best.y_px)
            self._consecutive_misses = 0
        else:
            self._consecutive_misses += 1
            if (
                self._lock_px is not None
                and self._consecutive_misses >= s.lock_release_after_misses
            ):
                self._lock_px = None

        return best
