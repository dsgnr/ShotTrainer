"""Works out where the rifle is aiming, in millimetres.

The detector finds the black circle in each camera frame. This
module takes that and reports the offset from the centre of the
frame to the centre of the circle, converted to millimetres using
the circle's known diameter.

The conversion from pixels to mm is recalculated every frame from
the detected circle's size, so small changes in distance (you
shift on the bench, the rifle moves a bit) don't throw the trace
off.

If the camera isn't dead square-on to the target, the circle
shows up as a slight ellipse rather than a circle. We measure
both axes of that ellipse and scale each direction separately, so
a few degrees of tilt doesn't bias the readings.

One thing worth knowing about signs. The camera looks forward
through the bore. Pivoting the rifle to the right makes the
target appear to move to the left in the camera frame. The trace
reports "aim direction", so positive x means the rifle is
pointing right. There are two preferences for users whose optics
flip the image (a magnifier, a mirror) so the trace reads the
right way round.
"""

from __future__ import annotations

import math
from dataclasses import replace as dataclass_replace

import numpy as np

from .detector import CircleTargetDetector
from .models import Detection, TrackingSample


class Tracker:
    """Takes a frame and returns where the rifle is aiming.

    Callers pass a frame and a timestamp. They get back a
    ``TrackingSample`` with the aim point in both pixels and
    millimetres, or ``None`` if there was no circle in the frame.

    The tracker keeps a running average of the circle's size so
    the mm-per-pixel scale stays stable across small detector
    jitter. There's no thread management here, the caller decides
    when to feed it frames.
    """

    # Smoothing factor for the running circle size. About 20
    # frames to converge, roughly 0.7 seconds at 30 fps. Slow
    # enough to wash out half-pixel detector wobble, fast enough
    # that an actual change in distance follows on without lag.
    _RADIUS_EMA_ALPHA = 0.1

    # Centroid smoothing. Same alpha as radius so both settle at
    # the same rate. Damps the frame-to-frame pixel jitter that
    # makes the trace "crawl" even when the rifle is still.
    _CENTROID_EMA_ALPHA = 0.1

    # Anything smaller than this is treated as noise and doesn't
    # update the running average.
    _MIN_INFORMATIVE_RADIUS_PX = 4.0

    def __init__(
        self,
        circle_diameter_mm: float,
        detector: CircleTargetDetector | None = None,
    ) -> None:
        if circle_diameter_mm <= 0:
            raise ValueError("circle_diameter_mm must be positive")

        self.detector = detector or CircleTargetDetector()
        self._diameter_mm = float(circle_diameter_mm)

        self._frame_id = 0
        self._last_sample: TrackingSample | None = None
        self._last_detection: Detection | None = None
        self._last_radius_px: float = 0.0

        # Running average of the centroid in pixels. Smooths out
        # the sub-pixel jitter that causes visible crawl.
        self._smoothed_cx_px: float | None = None
        self._smoothed_cy_px: float | None = None

        # Running average of the circle's two axes in pixels. The
        # detector falls back to setting both to the enclosing-
        # circle radius when it can't fit an ellipse, so the rest
        # of the code never has to special-case "perfectly round".
        self._smoothed_major_px: float | None = None
        self._smoothed_minor_px: float | None = None
        # Major-axis angle (radians, measured from +x). We only
        # smooth the radii. Angles wrap around and don't average
        # cleanly without extra work.
        self._last_angle_rad: float = 0.0

        self._zero_offset_mm: tuple[float, float] = (0.0, 0.0)
        self._trace_signs: tuple[float, float] = (-1.0, -1.0)

    def set_circle_diameter_mm(self, diameter_mm: float) -> None:
        """Tell the tracker the printed circle's real diameter has changed.

        The running average of the circle's pixel size gets reset
        so the next frame starts from scratch instead of blending
        the new diameter into a stale average.
        """
        if diameter_mm <= 0:
            raise ValueError("circle_diameter_mm must be positive")
        self._diameter_mm = float(diameter_mm)
        self._smoothed_major_px = None
        self._smoothed_minor_px = None
        self._smoothed_cx_px = None
        self._smoothed_cy_px = None

    def set_trace_inversion(self, invert_x: bool, invert_y: bool) -> None:
        """Flip the sign of one or both aim axes.

        The defaults expect a forward-facing barrel- or rail-
        mounted camera with no optics that flip the image. A
        magnifier or a mirror in the optical path reverses one or
        both axes for the user, so the trace ends up reading the
        wrong way round. These two preferences are the fix without
        having to retouch any tracking code.
        """
        x_sign = 1.0 if invert_x else -1.0
        y_sign = 1.0 if invert_y else -1.0
        self._trace_signs = (x_sign, y_sign)

    def set_region_fraction(self, fraction: float) -> None:
        """Pass the centred-region setting through to the detector."""
        self.detector.settings = dataclass_replace(
            self.detector.settings,
            region_fraction=max(0.05, min(1.0, float(fraction))),
        )

    def set_zero_offset(self, x_mm: float, y_mm: float) -> None:
        """Set the trace's origin to ``(x_mm, y_mm)`` instead of the circle centre.

        Used by the *Zero on aim* button. The user holds the rifle
        on whichever spot they want as the origin, the controller
        reads the last sample, and that becomes the offset. From
        then on the trace reports distance from the chosen aim
        point.
        """
        self._zero_offset_mm = (float(x_mm), float(y_mm))

    def clear_zero_offset(self) -> None:
        """Throw away any zero offset and report relative to the circle centre again."""
        self._zero_offset_mm = (0.0, 0.0)

    @property
    def zero_offset_mm(self) -> tuple[float, float]:
        """Current zero-on-aim offset in mm. ``(0, 0)`` means none is set."""
        return self._zero_offset_mm

    def zero_at_last_sample(self) -> bool:
        """Lock the most recent aim point as the trace's origin.

        Returns ``True`` if there was a usable sample to lock onto.
        ``False`` if the detector hasn't reported a hit yet, in
        which case the user needs to wait for the trace to come
        live before pressing the button.
        """
        sample = self._last_sample
        if sample is None or sample.x_mm is None or sample.y_mm is None:
            return False
        ox, oy = self._zero_offset_mm
        self._zero_offset_mm = (sample.x_mm + ox, sample.y_mm + oy)
        return True

    def zero_pixel(self) -> tuple[float, float] | None:
        """Pixel position of the chosen zero in the current camera frame.

        Returns ``None`` when no zero offset is set, no detection has
        come through yet, or the radius is too small to derive a scale.
        Uses a round-circle approximation, which is accurate enough for
        positioning a marker.
        """
        if self._zero_offset_mm == (0.0, 0.0):
            return None
        sample = self._last_sample
        if sample is None or self._last_radius_px <= 0:
            return None
        radius_mm = self._diameter_mm / 2.0
        mm_per_px = radius_mm / self._last_radius_px
        if mm_per_px <= 0:
            return None
        ox, oy = self._zero_offset_mm
        sx, sy = self._trace_signs
        dx_px = -ox / (sx * mm_per_px)
        dy_px = -oy / (sy * mm_per_px)
        return (sample.x_px + dx_px, sample.y_px + dy_px)

    def process(
        self,
        frame: np.ndarray,
        timestamp: float,
        frame_id: int | None = None,
    ) -> TrackingSample | None:
        """Run the detector on ``frame`` and return the aim point.

        Returns ``None`` when the detector can't see a circle. The
        caller treats that as "trace lost" rather than as an error.
        """
        sample_frame_id = self._next_frame_id(frame_id)

        det = self.detector.detect(frame)
        self._last_detection = det

        if not det.found:
            self._last_radius_px = 0.0
            return None

        self._last_radius_px = det.radius_px
        major_px, minor_px = self._update_smoothed_axes(det)

        # Smooth the centroid to damp sub-pixel jitter.
        cx_px, cy_px = self._update_smoothed_centroid(det.x_px, det.y_px)

        h, w = frame.shape[:2]
        x_mm, y_mm = self._aim_in_mm(
            cx_px,
            cy_px,
            major_px,
            minor_px,
            self._last_angle_rad,
            w,
            h,
        )

        sample = TrackingSample(
            timestamp=timestamp,
            x_px=cx_px,
            y_px=cy_px,
            x_mm=x_mm,
            y_mm=y_mm,
            confidence=det.confidence,
            frame_id=sample_frame_id,
        )
        self._last_sample = sample
        return sample

    @property
    def last_radius_px(self) -> float:
        """Pixel radius of the last circle the detector found."""
        return self._last_radius_px

    @property
    def last_detection(self) -> Detection | None:
        """The most recent :class:`Detection`, or ``None`` if nothing has run yet."""
        return self._last_detection

    @property
    def last_sample(self) -> TrackingSample | None:
        """The most recent :class:`TrackingSample`, or ``None`` if no detection has landed."""
        return self._last_sample

    @property
    def mm_per_pixel(self) -> float | None:
        """Average mm-per-pixel across both ellipse axes.

        Returns ``None`` until enough frames have been seen to
        converge on a stable estimate. Used by the header for
        display only. The aim coordinates are computed using each
        axis separately, so a slight ellipse converts correctly.
        """
        if (
            self._smoothed_major_px is None
            or self._smoothed_minor_px is None
            or self._smoothed_major_px <= 0
            or self._smoothed_minor_px <= 0
        ):
            return None
        major_mm_per_px = self._diameter_mm / (2.0 * self._smoothed_major_px)
        minor_mm_per_px = self._diameter_mm / (2.0 * self._smoothed_minor_px)
        return (major_mm_per_px + minor_mm_per_px) / 2.0

    @property
    def circle_diameter_mm(self) -> float:
        """The tracking-circle diameter the user configured, in mm."""
        return self._diameter_mm

    def _next_frame_id(self, frame_id: int | None) -> int:
        """Pick a frame id, using the camera's if it gave us one or counting up."""
        if frame_id is None:
            self._frame_id += 1
            return self._frame_id
        return frame_id

    def _update_smoothed_axes(self, detection: Detection) -> tuple[float, float]:
        """Fold a fresh detection into the running average.

        Falls back to the plain enclosing-circle radius when the
        detector couldn't fit an ellipse (very small contour, an
        almost-degenerate shape). Returns the values to use for
        this frame.

        The major-axis angle isn't smoothed. Angles wrap around at
        180 degrees and averaging them needs care that isn't worth
        it for the small tilt this code expects (a few degrees,
        not freely rotating).
        """
        if detection.confidence <= 0.0:
            return self._fallback_axes(detection.radius_px)

        if detection.semi_major_px > 0.0 and detection.semi_minor_px > 0.0:
            major_in = detection.semi_major_px
            minor_in = detection.semi_minor_px
            self._last_angle_rad = math.radians(detection.angle_degrees)
        else:
            major_in = detection.radius_px
            minor_in = detection.radius_px

        if major_in < self._MIN_INFORMATIVE_RADIUS_PX:
            return self._fallback_axes(detection.radius_px)

        a = self._RADIUS_EMA_ALPHA
        if self._smoothed_major_px is None:
            self._smoothed_major_px = major_in
        else:
            self._smoothed_major_px = (1.0 - a) * self._smoothed_major_px + a * major_in
        if self._smoothed_minor_px is None:
            self._smoothed_minor_px = minor_in
        else:
            self._smoothed_minor_px = (1.0 - a) * self._smoothed_minor_px + a * minor_in

        return (self._smoothed_major_px, self._smoothed_minor_px)

    def _update_smoothed_centroid(self, cx_px: float, cy_px: float) -> tuple[float, float]:
        """Fold a fresh centroid into the running average.

        Same EMA as the radius smoothing. First detection
        initialises the average, subsequent ones blend in.
        """
        a = self._CENTROID_EMA_ALPHA
        if self._smoothed_cx_px is None:
            self._smoothed_cx_px = cx_px
            self._smoothed_cy_px = cy_px
        else:
            self._smoothed_cx_px = (1.0 - a) * self._smoothed_cx_px + a * cx_px
            self._smoothed_cy_px = (1.0 - a) * self._smoothed_cy_px + a * cy_px  # type: ignore[operator]
        return (self._smoothed_cx_px, self._smoothed_cy_px)

    def _fallback_axes(self, radius_px: float) -> tuple[float, float]:
        """Pick a sensible axis pair when the current detection is too noisy.

        Sticks with the most recent running average if there is
        one, otherwise uses the raw radius for both axes. Either
        way the trace stays stable across short stretches where
        the target is partially blocked.
        """
        if self._smoothed_major_px is not None and self._smoothed_minor_px is not None:
            return (self._smoothed_major_px, self._smoothed_minor_px)
        radius = max(radius_px, self._MIN_INFORMATIVE_RADIUS_PX)
        return (radius, radius)

    def _aim_in_mm(
        self,
        circle_cx_px: float,
        circle_cy_px: float,
        major_px: float,
        minor_px: float,
        angle_rad: float,
        frame_width: int,
        frame_height: int,
    ) -> tuple[float, float]:
        """Convert the pixel offset to millimetres on the target.

        Rotates the offset into the ellipse's own frame, scales
        each axis by its mm-per-pixel, and rotates back. The
        rifle-aim sign flip and the user's invert preferences come
        last, then the zero offset is subtracted.
        """
        frame_cx = frame_width / 2.0
        frame_cy = frame_height / 2.0
        dx_px = circle_cx_px - frame_cx
        dy_px = circle_cy_px - frame_cy

        radius_mm = self._diameter_mm / 2.0
        mm_per_px_major = radius_mm / major_px
        mm_per_px_minor = radius_mm / minor_px

        cos_t = math.cos(angle_rad)
        sin_t = math.sin(angle_rad)

        # Rotate (dx_px, dy_px) into the ellipse frame, scale each
        # component by its own mm/px, then rotate back.
        local_major = dx_px * cos_t + dy_px * sin_t
        local_minor = -dx_px * sin_t + dy_px * cos_t
        local_major_mm = local_major * mm_per_px_major
        local_minor_mm = local_minor * mm_per_px_minor
        x_mm_image = local_major_mm * cos_t - local_minor_mm * sin_t
        y_mm_image = local_major_mm * sin_t + local_minor_mm * cos_t

        sx, sy = self._trace_signs
        x_mm = sx * x_mm_image
        y_mm = sy * y_mm_image

        ox, oy = self._zero_offset_mm
        return (x_mm - ox, y_mm - oy)
