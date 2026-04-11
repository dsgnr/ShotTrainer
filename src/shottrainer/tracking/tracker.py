"""Bridges per-frame detections to calibrated tracking samples.

The tracker assumes a barrel-mounted camera looking at a static target.
Each frame's detected target position becomes a sample of where the
rifle is currently pointing, expressed in millimetres relative to the
target centre.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from .calibration import HomographyCalibration, LinearCalibration
from .detector import CircleTargetDetector
from .models import Detection, TrackingSample


class _Calibration(Protocol):
    def to_mm(self, x_px: float, y_px: float) -> tuple[float, float]: ...


class Tracker:
    """Produces TrackingSample objects from frames.

    The tracker is deliberately small. It does not own the camera or
    the capture thread. Callers feed it frames and timestamps. This
    makes it easy to test with synthetic frames.

    Each sample's millimetre coordinates are the rifle's aim relative
    to the target centre, derived from where the target appears in the
    frame and the calibrated mm-per-pixel mapping. With a barrel-
    mounted camera, target motion in the frame is the *inverse* of the
    rifle's motion. The calibration handles that sign convention so
    callers see "rifle is aimed +X mm right of centre" without thinking
    about it.

    A manual override can be set via :meth:`set_manual_point`, which
    makes the tracker emit a synthetic sample at a fixed pixel location
    with confidence 0.0. Useful when automatic detection is unreliable.
    """

    def __init__(
        self,
        detector: CircleTargetDetector | None = None,
        calibration: LinearCalibration | HomographyCalibration | None = None,
    ) -> None:
        self.detector = detector or CircleTargetDetector()
        self.calibration: _Calibration | None = calibration
        self._calibration_is_placeholder: bool = False
        self._frame_id = 0
        self._last_sample: TrackingSample | None = None
        self._last_radius_px: float = 0.0
        self._manual_px: tuple[float, float] | None = None
        self._zero_offset_mm: tuple[float, float] = (0.0, 0.0)

    def set_calibration(
        self, calibration: LinearCalibration | HomographyCalibration | None
    ) -> None:
        self.calibration = calibration
        self._calibration_is_placeholder = False

    def set_zero_offset(self, x_mm: float, y_mm: float) -> None:
        """Set the trace's origin to ``(x_mm, y_mm)`` instead of the circle centre.

        After calling this, future samples report position relative to
        the supplied offset rather than the calibration's (0, 0).
        Useful for moving the trace's origin to match the rifle's natural
        aim point or a known impact group centre.
        """
        self._zero_offset_mm = (float(x_mm), float(y_mm))

    def clear_zero_offset(self) -> None:
        """Remove any zero offset, restoring the calibration's origin."""
        self._zero_offset_mm = (0.0, 0.0)

    @property
    def zero_offset_mm(self) -> tuple[float, float]:
        return self._zero_offset_mm

    def zero_at_last_sample(self) -> bool:
        """Use the last sample's mm position as the new origin.

        Returns ``True`` if there was a usable sample, ``False`` if no
        calibrated sample has been seen yet.
        """
        sample = self._last_sample
        if sample is None or sample.x_mm is None or sample.y_mm is None:
            return False
        # Account for any current offset so calling zero again locks
        # the new aim point rather than stacking offsets.
        ox, oy = self._zero_offset_mm
        self._zero_offset_mm = (sample.x_mm + ox, sample.y_mm + oy)
        return True

    def set_region_fraction(self, fraction: float) -> None:
        """Update the detector's centred acceptance region in place."""
        from dataclasses import replace

        self.detector.settings = replace(
            self.detector.settings, region_fraction=max(0.05, min(1.0, float(fraction)))
        )

    @property
    def calibration_is_placeholder(self) -> bool:
        return self._calibration_is_placeholder

    def ensure_default_calibration(self, frame_width: int, frame_height: int) -> bool:
        """Install a passthrough calibration centred on the frame if none is set.

        Returns ``True`` when a placeholder was installed. The placeholder
        treats one pixel as one millimetre and centres the origin on the
        middle of the frame. Both axes are inverted so the displayed trace
        moves with the user's aim: with a rifle- or scope-mounted camera
        a rightward aim moves the target left in the frame, and we want
        that to read as "aim point right of target centre". A real
        calibration set via :meth:`set_calibration` replaces the
        placeholder.
        """
        if self.calibration is not None:
            return False
        self.calibration = LinearCalibration(
            mm_per_pixel=-1.0,
            origin_px=(frame_width / 2.0, frame_height / 2.0),
        )
        self._calibration_is_placeholder = True
        return True

    def set_manual_point(self, x_px: float | None, y_px: float | None) -> None:
        """Force tracking to a fixed pixel location, ignoring the detector.

        Pass ``None`` to clear the override and resume automatic detection.
        Useful when target detection is unreliable, for example in poor
        lighting.
        """
        if x_px is None or y_px is None:
            self._manual_px = None
        else:
            self._manual_px = (float(x_px), float(y_px))
        # Either entering or leaving manual aim invalidates the soft lock;
        # the detector should re-acquire from scratch.
        self.detector.reset_lock()

    @property
    def manual_point(self) -> tuple[float, float] | None:
        return self._manual_px

    def process(
        self,
        frame: np.ndarray,
        timestamp: float,
        frame_id: int | None = None,
    ) -> TrackingSample | None:
        """Run detection (or apply manual aim) and return a sample.

        If ``frame_id`` is supplied it is recorded on the sample as-is.
        Otherwise an internal counter is used so callers without source
        ids still get strictly increasing values.
        """
        if frame_id is None:
            self._frame_id += 1
            sample_frame_id = self._frame_id
        else:
            sample_frame_id = frame_id

        if self._manual_px is not None:
            x_px, y_px = self._manual_px
            confidence = 0.0
            self._last_radius_px = 0.0
        else:
            det: Detection = self.detector.detect(frame)
            if not det.found:
                self._last_radius_px = 0.0
                return None
            x_px = det.x_px
            y_px = det.y_px
            confidence = det.confidence
            self._last_radius_px = det.radius_px

        x_mm: float | None = None
        y_mm: float | None = None
        if self.calibration is not None:
            raw_x_mm, raw_y_mm = self.calibration.to_mm(x_px, y_px)
            ox, oy = self._zero_offset_mm
            x_mm = raw_x_mm - ox
            y_mm = raw_y_mm - oy

        sample = TrackingSample(
            timestamp=timestamp,
            x_px=x_px,
            y_px=y_px,
            x_mm=x_mm,
            y_mm=y_mm,
            confidence=confidence,
            frame_id=sample_frame_id,
        )
        self._last_sample = sample
        return sample

    @property
    def last_radius_px(self) -> float:
        return self._last_radius_px

    @property
    def last_sample(self) -> TrackingSample | None:
        return self._last_sample
