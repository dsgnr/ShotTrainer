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
    # Morphological opening kernel size in pixels, applied to the
    # binary frame before contour extraction. It severs thin
    # bridges that the adaptive threshold sometimes draws between
    # the target and a nearby dark patch. Has to be odd
    # (auto-rounded if not). Set to 0 (or any value below 3) to
    # turn it off.
    opening_kernel_px: int = 3
    # Cap on how many contours the detector inspects in detail
    # per frame. A textured wall or a stack of papers can produce
    # thousands of contours. Sorting by area descending and
    # capping the loop keeps the per-frame cost predictable so
    # the preview doesn't lag when there's no real target around.
    max_candidates: int = 200
    # Multiplier on ``lock_radius_px`` defining how big a window
    # the detector searches inside while it has a lock. Bigger
    # values cope with faster aim movement. Smaller values give a
    # bigger speedup on busy scenes. ``2.0`` covers the soft-lock
    # window plus the same again for the damped band around it.
    lock_search_radius_factor: float = 2.0


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
        # The morphology kernel only depends on its size, so
        # cache it. The detector reuses the same kernel for every
        # frame while ``opening_kernel_px`` doesn't change.
        self._cached_kernel: tuple[int, np.ndarray] | None = None

    def reset_lock(self) -> None:
        """Drop any soft lock so the next frame is treated as a fresh start."""
        self._lock_px = None
        self._consecutive_misses = 0

    def _opening_kernel(self, size: int) -> np.ndarray:
        """Return the structuring element for the morphological opening.

        Cached so we only call ``cv2.getStructuringElement`` again
        when the kernel size actually changes.
        """
        cached = self._cached_kernel
        if cached is not None and cached[0] == size:
            return cached[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        self._cached_kernel = (size, kernel)
        return kernel

    @staticmethod
    def _with_ellipse_fit(
        detection: Detection, contour: np.ndarray | None
    ) -> Detection:
        """Add ellipse parameters to ``detection`` when the contour can be fitted.

        ``cv2.fitEllipse`` needs at least five contour points, and
        can return zero-length axes for degenerate input. Both of
        those cases fall through unchanged, with the ellipse
        fields left at zero so consumers know to fall back to the
        plain ``radius_px``.

        OpenCV's ``fitEllipse`` returns
        ``((cx, cy), (axis_a, axis_b), angle)`` where the axes are
        full widths and ``angle`` is the rotation of ``axis_a``
        from the +x image direction. ``axis_a`` is not guaranteed
        to be the major axis, so this helper picks whichever is
        bigger and rotates the angle by 90 degrees if the smaller
        axis was reported first.
        """
        if contour is None or len(contour) < 5:
            return detection
        try:
            (_, _), (axis_a, axis_b), angle = cv2.fitEllipse(contour)
        except cv2.error:
            return detection
        if axis_a <= 0 or axis_b <= 0:
            return detection

        if axis_a >= axis_b:
            semi_major = axis_a / 2.0
            semi_minor = axis_b / 2.0
            major_angle = angle
        else:
            semi_major = axis_b / 2.0
            semi_minor = axis_a / 2.0
            major_angle = (angle + 90.0) % 180.0

        return Detection(
            found=detection.found,
            x_px=detection.x_px,
            y_px=detection.y_px,
            radius_px=detection.radius_px,
            confidence=detection.confidence,
            rejected_outside_region=detection.rejected_outside_region,
            semi_major_px=float(semi_major),
            semi_minor_px=float(semi_minor),
            angle_degrees=float(major_angle),
        )

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

        # Morphological opening (erode then dilate) cuts the thin
        # bridges that the adaptive threshold sometimes draws
        # between the target and a nearby dark patch. Without it,
        # when the target slides toward another dark blob, the
        # local-mean threshold can pinch the two together and
        # the merged contour's centroid drifts toward the
        # neighbour. The 3x3 kernel is small enough to sever any
        # 1-2 pixel bridge while the target itself loses at most
        # one pixel of its outline (which the dilate restores).
        if s.opening_kernel_px >= 3:
            kernel_size = s.opening_kernel_px | 1  # ensure odd
            kernel = self._opening_kernel(kernel_size)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        h, w = grey.shape[:2]

        # While the detector has a lock, only look inside a box
        # around the last hit. ``cv2.findContours`` itself walks
        # the whole image, but feeding it a cropped slice means
        # there are fewer contours to analyse afterwards. On a
        # busy scene (textured walls, lots of dark blobs) that's
        # a noticeable saving. When the lock has been dropped we
        # search the whole frame so re-acquiring the target isn't
        # restricted to where it used to be.
        offset_x, offset_y = 0, 0
        search = binary
        if self._lock_px is not None:
            radius = max(1.0, s.lock_radius_px) * max(1.0, s.lock_search_radius_factor)
            lx, ly = self._lock_px
            x0 = max(0, int(lx - radius))
            y0 = max(0, int(ly - radius))
            x1 = min(w, int(lx + radius))
            y1 = min(h, int(ly + radius))
            if x1 > x0 and y1 > y0:
                search = binary[y0:y1, x0:x1]
                offset_x, offset_y = x0, y0

        contours, _ = cv2.findContours(search, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if offset_x or offset_y:
            offset = np.array([[offset_x, offset_y]], dtype=np.int32)
            contours = [c + offset for c in contours]

        # Cap how many contours we look at so a noisy scene can't
        # stall the detector. Largest-area first means the cap
        # keeps the ones most likely to be the target. Each
        # contour's area is cached so the loop below doesn't
        # compute it again.
        contour_areas: list[tuple[np.ndarray, float]]
        if len(contours) > s.max_candidates:
            contour_areas = sorted(
                ((c, cv2.contourArea(c)) for c in contours),
                key=lambda pair: pair[1],
                reverse=True,
            )[: s.max_candidates]
        else:
            contour_areas = [(c, cv2.contourArea(c)) for c in contours]

        # The central acceptance region. Centroids that fall
        # outside it are rejected so off-axis blobs (frame edges,
        # other papers in shot) don't capture the tracker.
        region_fraction = max(0.05, min(1.0, s.region_fraction))
        half_w = w * region_fraction / 2.0
        half_h = h * region_fraction / 2.0
        cx_frame = w / 2.0
        cy_frame = h / 2.0

        best: Detection = Detection(found=False)
        best_score = 0.0
        best_contour: np.ndarray | None = None
        best_off_region: tuple[float, float, float, float] | None = None  # cx, cy, r, score

        # Bounding-rectangle prefilter. If a contour's bounding
        # box can't fit a circle within the configured radius
        # range, it's almost certainly noise. The rectangle check
        # is much cheaper than the area / circularity / moment
        # work below, so we discard the obvious rejects first.
        min_side = s.min_radius_px * 2
        max_side = s.max_radius_px * 2

        for c, area in contour_areas:
            _x, _y, cw, ch = cv2.boundingRect(c)
            if cw < min_side or ch < min_side:
                continue
            if cw > max_side and ch > max_side:
                continue

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
            # Penalise blobs that don't fill their enclosing circle.
            fill = area / (np.pi * enclosing_r * enclosing_r)
            unboosted_score = float(circularity * fill)
            if abs(cx - cx_frame) > half_w or abs(cy - cy_frame) > half_h:
                # Remember the best off-region blob so the UI can
                # show "saw something circular but ignored it".
                if best_off_region is None or unboosted_score > best_off_region[3]:
                    best_off_region = (cx, cy, float(enclosing_r), unboosted_score)
                continue
            score = unboosted_score

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
                best_contour = c
                best = Detection(
                    found=True,
                    x_px=float(cx),
                    y_px=float(cy),
                    radius_px=float(enclosing_r),
                    confidence=score,
                )

        if best.found:
            best = self._with_ellipse_fit(best, best_contour)
            self._lock_px = (best.x_px, best.y_px)
            self._consecutive_misses = 0
            return best

        # Nothing made the cut. If the best candidate sat
        # outside the tracking region, surface it so the UI can
        # show what was rejected.
        self._consecutive_misses += 1
        if (
            self._lock_px is not None
            and self._consecutive_misses >= s.lock_release_after_misses
        ):
            self._lock_px = None

        if best_off_region is not None:
            cx, cy, r, score = best_off_region
            return Detection(
                found=False,
                x_px=cx,
                y_px=cy,
                radius_px=r,
                confidence=score,
                rejected_outside_region=True,
            )
        return best
