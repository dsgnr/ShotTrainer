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
    """

    def __init__(
        self,
        detector: CircleTargetDetector | None = None,
        calibration: LinearCalibration | HomographyCalibration | None = None,
    ) -> None:
        self.detector = detector or CircleTargetDetector()
        self.calibration: _Calibration | None = calibration
        self._frame_id = 0
        self._last_sample: TrackingSample | None = None
        self._manual_px: tuple[float, float] | None = None

    def set_calibration(self, calibration: LinearCalibration | HomographyCalibration | None) -> None:
        self.calibration = calibration

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

    @property
    def manual_point(self) -> tuple[float, float] | None:
        return self._manual_px

    def process(self, frame: np.ndarray, timestamp: float) -> TrackingSample | None:
        self._frame_id += 1
        if self._manual_px is not None:
            x_px, y_px = self._manual_px
            confidence = 0.0
        else:
            det: Detection = self.detector.detect(frame)
            if not det.found:
                return None
            x_px = det.x_px
            y_px = det.y_px
            confidence = det.confidence

        x_mm: float | None = None
        y_mm: float | None = None
        if self.calibration is not None:
            x_mm, y_mm = self.calibration.to_mm(x_px, y_px)

        sample = TrackingSample(
            timestamp=timestamp,
            x_px=x_px,
            y_px=y_px,
            x_mm=x_mm,
            y_mm=y_mm,
            confidence=confidence,
            frame_id=self._frame_id,
        )
        self._last_sample = sample
        return sample

    @property
    def last_sample(self) -> TrackingSample | None:
        return self._last_sample
