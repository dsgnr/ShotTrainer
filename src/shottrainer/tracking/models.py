"""Plain data types used across the tracking module.

Plain dataclasses, no Qt imports here. The tracker, calibration and tests
import import these without dragging OpenCV or PySide6 in too.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrackingSample:
    """One sample of where the rifle was aimed at a moment in time.

    Pixel coordinates are the position of the *target* in the camera
    frame at this moment. Millimetre coordinates, when present, are
    the rifle's aim relative to the target centre, expressed in the
    target's own coordinate system (positive X right of centre,
    positive Y below). Millimetres are populated only after a
    calibration has been applied.
    """

    timestamp: float
    x_px: float
    y_px: float
    x_mm: float | None = None
    y_mm: float | None = None
    confidence: float = 1.0
    frame_id: int = 0


@dataclass(frozen=True, slots=True)
class Detection:
    """What the detector saw in a single frame.

    ``found`` is ``False`` when nothing circular enough was located. The
    other fields are zero in that case.
    """

    found: bool
    x_px: float = 0.0
    y_px: float = 0.0
    radius_px: float = 0.0
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class CameraFrame:
    """A frame plus the time it was captured."""

    frame_id: int
    timestamp: float
    width: int
    height: int
