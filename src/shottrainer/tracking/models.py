"""Plain data types used across the tracking module.

Just dataclasses, nothing else. The tracker and the tests can
import these without dragging OpenCV or PySide6 in too.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrackingSample:
    """One sample of where the rifle was aimed at a moment in time.

    Pixel coordinates are where the target sits in the camera
    frame. Millimetre coordinates, when filled in, say where the
    rifle was pointing relative to the target's centre. Positive X
    is to the right of centre, positive Y is below.
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

    ``found`` is ``False`` when the frame had nothing circular
    enough to lock onto. The other fields are zero in that case.

    There's a special case for blobs that look like the target but
    sit outside the tracking region. ``rejected_outside_region``
    flags those, with the pixel coordinates pointing at the blob,
    so the preview can show "saw something but ignored it" without
    ``found`` going true.

    ``semi_major_px`` / ``semi_minor_px`` / ``angle_degrees``
    describe a best-fit ellipse for the contour. They're only
    filled in when the contour has at least five points (what
    ``cv2.fitEllipse`` needs). Smaller contours leave the ellipse
    fields at zero and the rest of the code falls back to treating
    the detection as a perfect circle. ``angle_degrees`` is the
    angle of the major axis from the +x image direction.
    """

    found: bool
    x_px: float = 0.0
    y_px: float = 0.0
    radius_px: float = 0.0
    confidence: float = 0.0
    rejected_outside_region: bool = False
    semi_major_px: float = 0.0
    semi_minor_px: float = 0.0
    angle_degrees: float = 0.0


@dataclass(frozen=True, slots=True)
class CameraFrame:
    """A frame plus the time it was captured."""

    frame_id: int
    timestamp: float
    width: int
    height: int
